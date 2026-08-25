"""Dev helper: load backtest trades.csv into the paper-trading ledger.

WARNING: only run this for a deliberate demo/screenshot. Doing this without
telling anyone looking at the dashboard makes it look like the live runner
has already made hundreds of real (simulated) trades when it hasn't -- that
exact confusion happened once already during development. Prefer just
letting scripts/run_paper_trading.py accumulate real trades over time.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from botfarm.live import ledger

TRADES_CSV = Path(__file__).resolve().parents[1] / "reports" / "bot01_mean_reversion" / "trades.csv"


def main() -> None:
    ledger.init_db()
    df = pd.read_csv(TRADES_CSV)
    with ledger.connect() as conn:
        conn.execute("DELETE FROM trades WHERE strategy_id=?", (df["strategy_id"].iloc[0],))
        for _, r in df.iterrows():
            shares = 1.0  # trades.csv stores capital before/after, not shares directly
            trade_id = ledger.open_trade(
                conn, strategy_id=r["strategy_id"], symbol="BTCUSDT",
                entry_ts_ms=int(r["entry_ts_ms"]), entry_price=r["entry_price"], shares=shares,
                stop_loss=r["stop_loss"], take_profit=r["take_profit"], fees_paid=0, created_at_ms=int(r["entry_ts_ms"]),
            )
            ledger.close_trade(
                conn, trade_id=trade_id, exit_ts_ms=int(r["exit_ts_ms"]), exit_price=r["exit_price"],
                exit_reason=r["exit_reason"], exit_fees_paid=r["fees_paid"], return_pct=r["return_pct"] / 100,
            )
    print(f"Seeded {len(df)} trades into the ledger.")


if __name__ == "__main__":
    main()
