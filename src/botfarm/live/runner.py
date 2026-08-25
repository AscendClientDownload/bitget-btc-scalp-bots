"""24/7 paper-trading runner. Polls Bitget's public API on a schedule aligned
to each strategy's candle close, evaluates the exact same Strategy code path
used by the backtester, and simulates fills via PaperBroker. Never places a
real order — see exchange_client.py.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from botfarm.backtest.costs import CostModel
from botfarm.live import ledger
from botfarm.live.exchange_client import BitgetPublicExchangeClient, ExchangeClient
from botfarm.live.paper_broker import PaperBroker
from botfarm.strategy.base import ExitReason, Strategy, StrategyContext

logger = logging.getLogger("botfarm.live.runner")

SYMBOL = "BTCUSDT"
LOOKBACK_BARS = 200  # enough for the slowest indicator warmup (e.g. EMA21, RSI14, ATR14)
DEFAULT_STARTING_CAPITAL = 10_000.0


def _now_ms() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp() * 1000)


def run_tick(
    strategy: Strategy,
    exchange: ExchangeClient,
    broker: PaperBroker,
    db_path=None,
) -> None:
    df = exchange.get_recent_candles(SYMBOL, strategy.timeframe, LOOKBACK_BARS)
    if len(df) < LOOKBACK_BARS // 2:
        logger.warning("only got %d candles, skipping tick", len(df))
        return

    full_df = strategy.compute_indicators(df) if hasattr(strategy, "compute_indicators") else df
    last_i = len(full_df) - 1
    ts_ms = int(full_df.iloc[last_i]["ts_ms"])
    close_price = float(full_df.iloc[last_i]["close"])

    with ledger.connect(db_path) if db_path else ledger.connect() as conn:
        open_row = ledger.get_open_trade(conn, strategy.id)

        if open_row is not None:
            ctx = StrategyContext(
                df=full_df, i=last_i, in_position=True,
                entry_price=open_row["entry_price"], entry_bar=None,
            )
            entry_bars_elapsed = None
            if strategy.max_holding_bars is not None:
                bars = full_df[full_df["ts_ms"] >= open_row["entry_ts_ms"]]
                entry_bars_elapsed = len(bars) - 1

            exit_reason = None
            if close_price <= open_row["stop_loss"]:
                exit_reason = ExitReason.STOP_LOSS
            elif close_price >= open_row["take_profit"]:
                exit_reason = ExitReason.TAKE_PROFIT
            elif strategy.exit_signal(ctx):
                exit_reason = ExitReason.SIGNAL
            elif (
                strategy.max_holding_bars is not None
                and entry_bars_elapsed is not None
                and entry_bars_elapsed >= strategy.max_holding_bars
            ):
                exit_reason = ExitReason.TIME_STOP

            if exit_reason is not None:
                return_pct = broker.close_position(
                    conn,
                    trade_id=open_row["id"],
                    ts_ms=ts_ms,
                    quote_price=close_price,
                    shares=open_row["shares"],
                    entry_price=open_row["entry_price"],
                    exit_reason=exit_reason.value,
                )
                logger.info("closed trade %s: %s return=%.4f%%", open_row["id"], exit_reason.value, return_pct * 100)
        else:
            ctx = StrategyContext(df=full_df, i=last_i, in_position=False)
            if strategy.entry_signal(ctx):
                state_row = conn.execute(
                    "SELECT capital FROM strategy_state WHERE strategy_id=?", (strategy.id,)
                ).fetchone()
                capital = state_row["capital"] if state_row else DEFAULT_STARTING_CAPITAL

                stop_price = strategy.stop_loss(ctx)
                target_price = strategy.take_profit(ctx)
                trade_id, fill_price, shares = broker.open_position(
                    conn,
                    strategy_id=strategy.id,
                    symbol=SYMBOL,
                    ts_ms=ts_ms,
                    quote_price=close_price,
                    notional=capital,
                    stop_loss=stop_price,
                    take_profit=target_price,
                )
                logger.info("opened trade %s at %.2f", trade_id, fill_price)

        # Recompute current capital (cash + unrealized) and persist strategy_state + equity snapshot.
        closed_capital = conn.execute(
            "SELECT COALESCE(SUM((exit_price*shares - entry_price*shares) - fees_paid), 0) as pnl "
            "FROM trades WHERE strategy_id=? AND status='closed'",
            (strategy.id,),
        ).fetchone()["pnl"]
        capital = DEFAULT_STARTING_CAPITAL + closed_capital

        still_open = ledger.get_open_trade(conn, strategy.id)
        unrealized = 0.0
        if still_open is not None:
            unrealized = still_open["shares"] * close_price - still_open["shares"] * still_open["entry_price"]

        ledger.upsert_strategy_state(
            conn,
            strategy_id=strategy.id,
            symbol=SYMBOL,
            timeframe=strategy.timeframe,
            params_json=json.dumps({}),
            capital=capital,
            updated_at_ms=ts_ms,
        )
        ledger.record_equity(conn, strategy.id, ts_ms, capital + unrealized)


def run_forever(strategy: Strategy, cost_model: CostModel | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ledger.init_db()

    exchange = BitgetPublicExchangeClient()
    broker = PaperBroker(cost_model)

    scheduler = BlockingScheduler(timezone="UTC")
    minute_step = 5 if strategy.timeframe == "5min" else 1
    # +10s past the candle-close minute so Bitget has published the closed bar.
    scheduler.add_job(
        run_tick,
        trigger=CronTrigger(minute=f"*/{minute_step}", second=10),
        args=[strategy, exchange, broker],
        id=f"tick_{strategy.id}",
        max_instances=1,
        coalesce=True,
    )
    logger.info("starting paper-trading runner for %s on %s timeframe", strategy.id, strategy.timeframe)
    scheduler.start()
