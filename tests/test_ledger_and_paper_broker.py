import tempfile
from pathlib import Path

import pytest

from botfarm.backtest.costs import CostModel
from botfarm.live import ledger
from botfarm.live.paper_broker import PaperBroker


@pytest.fixture
def db_path():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "test_ledger.db"
        ledger.init_db(path)
        yield path


def test_open_and_close_trade_roundtrip(db_path):
    broker = PaperBroker(CostModel(fee_rate=0.001, slippage_bps=0))
    with ledger.connect(db_path) as conn:
        trade_id, fill_price, shares = broker.open_position(
            conn, strategy_id="bot01", symbol="BTCUSDT", ts_ms=1000,
            quote_price=100.0, notional=1000.0, stop_loss=98.0, take_profit=102.0,
        )
        assert fill_price == pytest.approx(100.0)
        open_row = ledger.get_open_trade(conn, "bot01")
        assert open_row is not None
        assert open_row["id"] == trade_id

        return_pct = broker.close_position(
            conn, trade_id=trade_id, ts_ms=2000, quote_price=102.0,
            shares=shares, entry_price=fill_price, exit_reason="take_profit",
        )
        assert return_pct > 0

        assert ledger.get_open_trade(conn, "bot01") is None
        closed = conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
        assert closed["status"] == "closed"
        assert closed["exit_reason"] == "take_profit"


def test_equity_snapshot_and_strategy_state(db_path):
    with ledger.connect(db_path) as conn:
        ledger.record_equity(conn, "bot01", 1000, 10_000.0)
        ledger.upsert_strategy_state(conn, "bot01", "BTCUSDT", "5min", "{}", 10_000.0, 1000)
        ledger.upsert_strategy_state(conn, "bot01", "BTCUSDT", "5min", "{}", 10_050.0, 2000)

        state = conn.execute("SELECT * FROM strategy_state WHERE strategy_id='bot01'").fetchone()
        assert state["capital"] == pytest.approx(10_050.0)  # upsert overwrote, not duplicated

        snapshots = conn.execute("SELECT * FROM equity_snapshots").fetchall()
        assert len(snapshots) == 1
        assert snapshots[0]["equity"] == pytest.approx(10_000.0)
