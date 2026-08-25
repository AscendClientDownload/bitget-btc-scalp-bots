"""SQLite ledger for paper-trading: trades, equity snapshots, and per-bot
live strategy state. Read by the dashboard and the live runner; written by
the live runner and the daily retune job."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

_DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "botfarm_ledger.db"
# On a host with an ephemeral filesystem (e.g. Railway without this pointed
# at a mounted Volume), the ledger would silently reset on every redeploy.
DB_PATH = Path(os.environ["BOTFARM_DB_PATH"]) if os.environ.get("BOTFARM_DB_PATH") else _DEFAULT_DB_PATH

# Diagnostic: printed once at import time so deploy logs show exactly what
# path was resolved and whether BOTFARM_DB_PATH was actually read, rather
# than a bare "unable to open database file" with no context.
print(f"[ledger] BOTFARM_DB_PATH env = {os.environ.get('BOTFARM_DB_PATH')!r}", flush=True)
print(f"[ledger] resolved DB_PATH = {DB_PATH}", flush=True)
print(f"[ledger] DB_PATH.parent = {DB_PATH.parent}  exists={DB_PATH.parent.exists()}", flush=True)
if DB_PATH.parent.exists():
    print(f"[ledger] DB_PATH.parent writable = {os.access(DB_PATH.parent, os.W_OK)}", flush=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('open', 'closed')),
    entry_ts_ms INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    shares REAL NOT NULL,
    stop_loss REAL,
    take_profit REAL,
    exit_ts_ms INTEGER,
    exit_price REAL,
    exit_reason TEXT,
    fees_paid REAL DEFAULT 0,
    return_pct REAL,
    created_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS equity_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id TEXT NOT NULL,
    ts_ms INTEGER NOT NULL,
    equity REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS strategy_state (
    strategy_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    params_json TEXT NOT NULL,
    capital REAL NOT NULL,
    updated_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS retune_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id TEXT NOT NULL,
    ts_ms INTEGER NOT NULL,
    old_params_json TEXT NOT NULL,
    candidate_params_json TEXT NOT NULL,
    train_metric REAL,
    validation_metric REAL,
    decision TEXT NOT NULL CHECK(decision IN ('accepted', 'rejected')),
    reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_trades_strategy_status ON trades(strategy_id, status);
CREATE INDEX IF NOT EXISTS idx_equity_strategy_ts ON equity_snapshots(strategy_id, ts_ms);
"""


@contextmanager
def connect(db_path: Path = DB_PATH):
    try:
        conn = sqlite3.connect(db_path)
    except sqlite3.OperationalError as e:
        parent = Path(db_path).parent
        raise sqlite3.OperationalError(
            f"{e} -- path={db_path!r} parent={parent!r} "
            f"parent_exists={parent.exists()} "
            f"parent_writable={os.access(parent, os.W_OK) if parent.exists() else 'N/A (parent missing)'}"
        ) from e
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path = DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def open_trade(
    conn: sqlite3.Connection,
    strategy_id: str,
    symbol: str,
    entry_ts_ms: int,
    entry_price: float,
    shares: float,
    stop_loss: float,
    take_profit: float,
    fees_paid: float,
    created_at_ms: int,
) -> int:
    cur = conn.execute(
        """INSERT INTO trades
        (strategy_id, symbol, status, entry_ts_ms, entry_price, shares, stop_loss, take_profit,
         fees_paid, created_at_ms)
        VALUES (?, ?, 'open', ?, ?, ?, ?, ?, ?, ?)""",
        (strategy_id, symbol, entry_ts_ms, entry_price, shares, stop_loss, take_profit, fees_paid, created_at_ms),
    )
    return cur.lastrowid


def get_open_trade(conn: sqlite3.Connection, strategy_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM trades WHERE strategy_id=? AND status='open' ORDER BY id DESC LIMIT 1",
        (strategy_id,),
    ).fetchone()


def close_trade(
    conn: sqlite3.Connection,
    trade_id: int,
    exit_ts_ms: int,
    exit_price: float,
    exit_reason: str,
    exit_fees_paid: float,
    return_pct: float,
) -> None:
    conn.execute(
        """UPDATE trades SET status='closed', exit_ts_ms=?, exit_price=?, exit_reason=?,
           fees_paid = fees_paid + ?, return_pct=? WHERE id=?""",
        (exit_ts_ms, exit_price, exit_reason, exit_fees_paid, return_pct, trade_id),
    )


def record_equity(conn: sqlite3.Connection, strategy_id: str, ts_ms: int, equity: float) -> None:
    conn.execute(
        "INSERT INTO equity_snapshots (strategy_id, ts_ms, equity) VALUES (?, ?, ?)",
        (strategy_id, ts_ms, equity),
    )


def upsert_strategy_state(
    conn: sqlite3.Connection,
    strategy_id: str,
    symbol: str,
    timeframe: str,
    params_json: str,
    capital: float,
    updated_at_ms: int,
) -> None:
    conn.execute(
        """INSERT INTO strategy_state (strategy_id, symbol, timeframe, params_json, capital, updated_at_ms)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(strategy_id) DO UPDATE SET
             symbol=excluded.symbol, timeframe=excluded.timeframe, params_json=excluded.params_json,
             capital=excluded.capital, updated_at_ms=excluded.updated_at_ms""",
        (strategy_id, symbol, timeframe, params_json, capital, updated_at_ms),
    )
