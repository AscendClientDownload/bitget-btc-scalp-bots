import numpy as np
import pandas as pd

from botfarm.strategy.base import StrategyContext
from botfarm.strategy.bot01_ema_rsi_atr import Bot01EmaRsiAtr


def _make_uptrend_df(n=60):
    rng = np.random.default_rng(42)
    closes = 100 + np.cumsum(rng.normal(0.05, 0.2, n))
    highs = closes + rng.uniform(0.1, 0.5, n)
    lows = closes - rng.uniform(0.1, 0.5, n)
    volume = rng.uniform(50, 150, n)
    return pd.DataFrame(
        {
            "ts_ms": [1_600_000_000_000 + i * 300_000 for i in range(n)],
            "open": closes,
            "high": highs,
            "low": lows,
            "close": closes,
            "base_volume": volume,
        }
    )


def test_compute_indicators_adds_expected_columns():
    strategy = Bot01EmaRsiAtr()
    df = _make_uptrend_df()
    out = strategy.compute_indicators(df)
    for col in ["ema_fast", "ema_slow", "rsi", "vol_ratio", "atr", "ema_cross_up"]:
        assert col in out.columns


def test_entry_signal_false_during_warmup():
    strategy = Bot01EmaRsiAtr()
    df = strategy.compute_indicators(_make_uptrend_df())
    ctx = StrategyContext(df=df, i=1, in_position=False)
    assert strategy.entry_signal(ctx) is False


def test_stop_below_and_target_above_entry():
    strategy = Bot01EmaRsiAtr()
    df = strategy.compute_indicators(_make_uptrend_df())
    ctx = StrategyContext(df=df, i=40, in_position=False)
    sl = strategy.stop_loss(ctx)
    tp = strategy.take_profit(ctx)
    assert sl < ctx.close < tp


def test_exit_signal_always_false_governed_by_engine():
    strategy = Bot01EmaRsiAtr()
    df = strategy.compute_indicators(_make_uptrend_df())
    ctx = StrategyContext(df=df, i=40, in_position=True, entry_price=100.0, entry_bar=30)
    assert strategy.exit_signal(ctx) is False
