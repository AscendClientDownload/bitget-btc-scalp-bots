"""Local-only Flask dashboard: shows which bot is trading what, live.

Reads from the paper-trading SQLite ledger (botfarm_ledger.db). Read-only —
this process never places orders and never writes to the ledger.
"""
from __future__ import annotations

import os
import sqlite3
import time

from flask import Flask, jsonify, render_template

from botfarm.live import ledger
from botfarm.live.exchange_client import BitgetPublicExchangeClient
from botfarm.live.runner import DEFAULT_STARTING_CAPITAL, SYMBOL

app = Flask(__name__)
_exchange = BitgetPublicExchangeClient()

_PRICE_CACHE_TTL_SECONDS = 4.0
_price_cache: dict = {"price": None, "ts": 0.0}


def _last_price() -> float | None:
    """Cached live price so a 5s-polling dashboard with N open trades doesn't
    hit Bitget's public API more than roughly once every few seconds."""
    now = time.monotonic()
    if _price_cache["price"] is None or (now - _price_cache["ts"]) > _PRICE_CACHE_TTL_SECONDS:
        try:
            _price_cache["price"] = _exchange.get_last_price(SYMBOL)
            _price_cache["ts"] = now
        except Exception:
            pass  # keep serving the stale cached price (or None) rather than erroring the dashboard
    return _price_cache["price"]


def _rows_as_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(r) for r in rows]


def _fetch_summary(conn: sqlite3.Connection) -> dict:
    closed = conn.execute(
        "SELECT return_pct, fees_paid, entry_ts_ms, exit_ts_ms, entry_price, shares FROM trades WHERE status='closed'"
    ).fetchall()
    open_count = conn.execute("SELECT COUNT(*) c FROM trades WHERE status='open'").fetchone()["c"]
    strategy_rows = conn.execute("SELECT capital FROM strategy_state").fetchall()
    total_pnl_dollars = sum((r["capital"] - DEFAULT_STARTING_CAPITAL) for r in strategy_rows)

    num_trades = len(closed)
    if num_trades == 0:
        return {
            "total_pnl_pct": 0.0, "total_pnl_dollars": total_pnl_dollars, "win_rate_pct": 0.0,
            "profit_factor": 0.0, "num_closed_trades": 0, "open_positions": open_count,
            "avg_duration_min": 0.0,
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
        "total_pnl_dollars": total_pnl_dollars,
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
    price = _last_price()
    with ledger.connect() as conn:
        rows = _rows_as_dicts(
            conn.execute("SELECT * FROM trades WHERE status='open' ORDER BY entry_ts_ms DESC").fetchall()
        )
    for r in rows:
        if price is not None:
            r["current_price"] = price
            r["unrealized_pnl_dollars"] = r["shares"] * (price - r["entry_price"])
            r["unrealized_pnl_pct"] = (price - r["entry_price"]) / r["entry_price"]
        else:
            r["current_price"] = None
            r["unrealized_pnl_dollars"] = None
            r["unrealized_pnl_pct"] = None
    return jsonify(rows)


@app.route("/api/trades/closed")
def api_closed_trades():
    with ledger.connect() as conn:
        rows = _rows_as_dicts(
            conn.execute(
                "SELECT * FROM trades WHERE status='closed' ORDER BY exit_ts_ms DESC LIMIT 500"
            ).fetchall()
        )
    for r in rows:
        cost_basis = (r["shares"] or 0) * (r["entry_price"] or 0)
        r["realized_pnl_dollars"] = (r["return_pct"] or 0.0) * cost_basis
    return jsonify(rows)


@app.route("/api/strategies")
def api_strategies():
    with ledger.connect() as conn:
        rows = _rows_as_dicts(conn.execute("SELECT * FROM strategy_state ORDER BY strategy_id").fetchall())
    for r in rows:
        r["starting_capital"] = DEFAULT_STARTING_CAPITAL
        r["pnl_dollars"] = r["capital"] - DEFAULT_STARTING_CAPITAL
        r["pnl_pct"] = (r["capital"] - DEFAULT_STARTING_CAPITAL) / DEFAULT_STARTING_CAPITAL * 100
    return jsonify(rows)


def main() -> None:
    print("[dashboard] main() started", flush=True)
    ledger.init_db()
    print("[dashboard] ledger.init_db() returned", flush=True)
    # Railway (and most PaaS hosts) inject PORT and expect a bind on 0.0.0.0;
    # local dev has no PORT set, so it stays on localhost-only by default.
    on_paas = "PORT" in os.environ
    port = int(os.environ.get("PORT", os.environ.get("DASHBOARD_PORT", 5000)))
    host = "0.0.0.0" if on_paas else "127.0.0.1"

    print(f"[dashboard] on_paas={on_paas} host={host} port={port}", flush=True)

    if on_paas:
        print(f"[dashboard] importing waitress...", flush=True)
        from waitress import serve
        print(f"[dashboard] calling waitress.serve(host={host!r}, port={port})...", flush=True)
        try:
            serve(app, host=host, port=port)
        except Exception:
            import traceback
            print("[dashboard] waitress.serve() raised:", flush=True)
            traceback.print_exc()
            raise
        print("[dashboard] waitress.serve() returned (unexpected -- it should block forever)", flush=True)
    else:
        app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
