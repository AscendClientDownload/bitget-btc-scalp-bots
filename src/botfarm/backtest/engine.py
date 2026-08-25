"""Backtest engine: vectorized indicator computation (done by the strategy)
feeding a single O(n) event-driven pass that enforces one-position-at-a-time
sequencing, intrabar stop/target ordering, and the time-stop.

Pure vectorization can't correctly express "already in a trade, skip new
signals" or "which of stop/target hit first within this bar" — hence the
event-driven pass, done once per backtest rather than per-bar reprocessing.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from botfarm.backtest.costs import CostModel
from botfarm.strategy.base import ExitReason, Strategy, StrategyContext


@dataclass
class Trade:
    strategy_id: str
    entry_bar: int
    entry_ts_ms: int
    entry_price: float
    exit_bar: int
    exit_ts_ms: int
    exit_price: float
    exit_reason: ExitReason
    stop_loss: float
    take_profit: float
    capital_before: float
    capital_after: float
    fees_paid: float
    return_pct: float


@dataclass
class BacktestResult:
    trades: list[Trade] = field(default_factory=list)
    equity_curve: pd.DataFrame = field(default_factory=pd.DataFrame)
    starting_capital: float = 0.0
    ending_capital: float = 0.0


def run_backtest(
    strategy: Strategy,
    df: pd.DataFrame,
    starting_capital: float = 10_000.0,
    position_fraction: float = 1.0,
    cost_model: CostModel | None = None,
) -> BacktestResult:
    """df must already have OHLCV columns (open/high/low/close/base_volume/ts_ms)
    plus every indicator column the strategy needs (see strategy.compute_indicators)."""
    cost_model = cost_model or CostModel()
    n = len(df)

    trades: list[Trade] = []
    capital = starting_capital
    equity_rows = []

    in_position = False
    entry_bar = entry_ts = entry_price = None
    stop_price = target_price = None
    shares = 0.0
    entry_fee = 0.0

    for i in range(n):
        row = df.iloc[i]
        ts_ms = int(row["ts_ms"])

        if in_position:
            bar_high, bar_low, bar_close = float(row["high"]), float(row["low"]), float(row["close"])
            exit_reason = None
            exit_quote_price = None

            # Conservative intrabar ordering: assume stop-loss triggers before
            # take-profit if both are within this bar's range.
            if bar_low <= stop_price:
                exit_reason = ExitReason.STOP_LOSS
                exit_quote_price = stop_price
            elif bar_high >= target_price:
                exit_reason = ExitReason.TAKE_PROFIT
                exit_quote_price = target_price
            else:
                ctx = StrategyContext(df=df, i=i, in_position=True, entry_price=entry_price, entry_bar=entry_bar)
                if strategy.exit_signal(ctx):
                    exit_reason = ExitReason.SIGNAL
                    exit_quote_price = bar_close
                elif strategy.max_holding_bars is not None and (i - entry_bar) >= strategy.max_holding_bars:
                    exit_reason = ExitReason.TIME_STOP
                    exit_quote_price = bar_close

            if exit_reason is not None:
                fill_price = cost_model.fill_price(exit_quote_price, "sell")
                gross_proceeds = shares * fill_price
                fee = cost_model.fee(gross_proceeds)
                net_proceeds = gross_proceeds - fee
                # `capital` currently holds cash left aside after this trade's
                # entry (notional was already deducted); adding net proceeds
                # from the sale settles the trade.
                capital_before_trade = capital
                capital_after_trade = capital + net_proceeds
                cost_basis = shares * entry_price
                return_pct = (net_proceeds - cost_basis) / cost_basis

                trades.append(
                    Trade(
                        strategy_id=strategy.id,
                        entry_bar=entry_bar,
                        entry_ts_ms=entry_ts,
                        entry_price=entry_price,
                        exit_bar=i,
                        exit_ts_ms=ts_ms,
                        exit_price=fill_price,
                        exit_reason=exit_reason,
                        stop_loss=stop_price,
                        take_profit=target_price,
                        capital_before=capital_before_trade,
                        capital_after=capital_after_trade,
                        fees_paid=fee + entry_fee,
                        return_pct=return_pct,
                    )
                )
                capital = capital_after_trade
                in_position = False
                entry_bar = entry_ts = entry_price = None
                stop_price = target_price = None
                shares = 0.0
                entry_fee = 0.0

        if not in_position:
            ctx = StrategyContext(df=df, i=i, in_position=False)
            if strategy.entry_signal(ctx):
                quote_price = ctx.close
                fill_price = cost_model.fill_price(quote_price, "buy")
                notional = capital * position_fraction
                entry_fee = cost_model.fee(notional)
                shares = (notional - entry_fee) / fill_price

                entry_bar = i
                entry_ts = ts_ms
                entry_price = fill_price
                stop_price = strategy.stop_loss(ctx)
                target_price = strategy.take_profit(ctx)
                capital -= notional
                in_position = True

        mark_price = float(row["close"])
        unrealized = shares * mark_price if in_position else 0.0
        equity_rows.append({"ts_ms": ts_ms, "equity": capital + unrealized})

    equity_curve = pd.DataFrame(equity_rows)
    return BacktestResult(
        trades=trades,
        equity_curve=equity_curve,
        starting_capital=starting_capital,
        ending_capital=float(equity_curve["equity"].iloc[-1]) if not equity_curve.empty else starting_capital,
    )
