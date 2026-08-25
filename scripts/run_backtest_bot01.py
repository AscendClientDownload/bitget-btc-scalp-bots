"""Fetch real BTCUSDT 5min history from Bitget (cached locally), run bot #1's
backtest, and write reports/bot01_mean_reversion/{backtest_report.md,equity_curve.png,trades.csv}.

Bot #1 is currently the mean-reversion pivot (src/botfarm/strategy/bot01_mean_reversion.py).
An earlier trend-following version (bot01_ema_rsi_atr.py) was tested first and
showed no edge across 5 variants; mean-reversion was tried next (10 more
variants) and also showed no edge -- see reports/bot01_ema_rsi_atr/ and
docs/RISK_DISCLAIMER.md for that history. This script runs the current,
final configuration honestly: it is a reference implementation of the
framework, not a profitable strategy.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from botfarm.backtest.engine import run_backtest
from botfarm.backtest.report import write_report
from botfarm.data.bitget_client import BitgetPublicClient
from botfarm.data.cache import get_or_fetch
from botfarm.strategy.bot01_mean_reversion import Bot01MeanReversion

SYMBOL = "BTCUSDT"
GRANULARITY = "5min"
REPORT_DIR = Path(__file__).resolve().parents[1] / "reports" / "bot01_mean_reversion"


def main(days: int, position_fraction: float) -> None:
    end = datetime.now(tz=timezone.utc)
    start = end - timedelta(days=days)
    start_ms, end_ms = int(start.timestamp() * 1000), int(end.timestamp() * 1000)

    print(f"Fetching {SYMBOL} {GRANULARITY} candles from {start.date()} to {end.date()}...")
    client = BitgetPublicClient()
    df = get_or_fetch(client, SYMBOL, GRANULARITY, start_ms, end_ms)
    print(f"Got {len(df)} candles ({df['ts_ms'].min()} to {df['ts_ms'].max()})")

    if len(df) < 100:
        raise SystemExit(f"Not enough candles fetched ({len(df)}) to run a meaningful backtest.")

    strategy = Bot01MeanReversion()
    full_df = strategy.compute_indicators(df)

    result = run_backtest(strategy, full_df, starting_capital=1_000.0, position_fraction=position_fraction)
    print(f"Trades: {len(result.trades)}  Ending capital: {result.ending_capital:.2f}")

    metrics = write_report(
        result,
        strategy_id=strategy.id,
        symbol=SYMBOL,
        timeframe=GRANULARITY,
        date_range=(str(start.date()), str(end.date())),
        out_dir=REPORT_DIR,
    )
    print(f"Report written to {REPORT_DIR}")
    print(metrics)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=180, help="How many days of history to backtest over")
    parser.add_argument(
        "--position-fraction", type=float, default=0.2,
        help="Fraction of current capital risked per trade (1.0 = 100%%, unrealistically aggressive; "
        "default 0.2 is still aggressive for a scalp bot but avoids the extreme geometric-decay "
        "artifact of full-capital compounding on a negative-expectancy run).",
    )
    args = parser.parse_args()
    main(args.days, args.position_fraction)
