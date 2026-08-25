"""Local-only Flask dashboard: shows which bot is trading what, live.

Reads from the paper-trading SQLite ledger (botfarm_ledger.db). Read-only —
this process never places orders and never writes to the ledger.
"""
from __future__ import annotations

import os
import sqlite3

from flask import Flask, jsonify, render_template

from botfarm.live import ledger

app = Flask(__name__)


def _rows_as_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(r) for r in rows]


def _fetch_summary(conn: sqlite3.Connection) -> dict:
    closed = conn.execute(
        "SELECT return_pct, fees_paid, entry_ts_ms, exit_ts_ms FROM trades WHERE status='closed'"
    ).fetchall()
    open_count = conn.execute("SELECT COUNT(*) c FROM trades WHERE status='open'").fetchone()["c"]

    num_trades = len(closed)
    if num_trades == 0:
        return {
            "total_pnl_pct": 0.0, "win_rate_pct": 0.0, "profit_factor": 0.0,
            "num_closed_trades": 0, "open_positions": open_count, "avg_duration_min": 0.0,
        }

    returns = [r["return_pct"] or 0.0 for r in closed]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    gross_profit = sum(wins)
    gross_loss = -sum(losses)
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)
    durations_min = [
        (r["exit_ts_ms"] - r["entry_ts_ms"]) / 60_000 for r in closed if r["exit_ts_ms"] and r["entry_ts_ms"]
    ]

    return {
        "total_pnl_pct": sum(returns) * 100,
        "win_rate_pct": len(wins) / num_trades * 100,
        "profit_factor": profit_factor,
        "num_closed_trades": num_trades,
        "open_positions": open_count,
        "avg_duration_min": (sum(durations_min) / len(durations_min)) if durations_min else 0.0,
    }


@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/summary")
def api_summary():
    with ledger.connect() as conn:
        return jsonify(_fetch_summary(conn))


@app.route("/api/trades/open")
def api_open_trades():
    with ledger.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM trades WHERE status='open' ORDER BY entry_ts_ms DESC"
        ).fetchall()
        return jsonify(_rows_as_dicts(rows))


@app.route("/api/trades/closed")
def api_closed_trades():
    with ledger.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM trades WHERE status='closed' ORDER BY exit_ts_ms DESC LIMIT 500"
        ).fetchall()
        return jsonify(_rows_as_dicts(rows))


@app.route("/api/strategies")
def api_strategies():
    with ledger.connect() as conn:
        rows = conn.execute("SELECT * FROM strategy_state ORDER BY strategy_id").fetchall()
        return jsonify(_rows_as_dicts(rows))


def main() -> None:
    ledger.init_db()
    port = int(os.environ.get("DASHBOARD_PORT", 5000))
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
