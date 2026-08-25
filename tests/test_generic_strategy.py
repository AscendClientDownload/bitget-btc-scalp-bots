import numpy as np
import pandas as pd

from botfarm.catalog.schema import spec_from_dict
from botfarm.strategy.base import StrategyContext
from botfarm.strategy.generic import DeclarativeStrategy


def _make_df(n=80, seed=1):
    rng = np.random.default_rng(seed)
    closes = 100 + np.cumsum(rng.normal(0, 0.4, n))
    highs = closes + rng.uniform(0.1, 0.5, n)
    lows = closes - rng.uniform(0.1, 0.5, n)
    opens = closes + rng.uniform(-0.2, 0.2, n)
    volume = rng.uniform(50, 150, n)
    return pd.DataFrame(
        {
            "ts_ms": [1_600_000_000_000 + i * 300_000 for i in range(n)],
            "open": opens, "high": highs, "low": lows, "close": closes, "base_volume": volume,
        }
    )


MEAN_REVERSION_SPEC = {
    "id": "test_mr_bb_rsi",
    "name": "Test BB+RSI mean reversion",
    "category": "mean_reversion",
    "timeframe": "5min",
    "indicators": [
        {"name": "bollinger_bands", "alias": "bb", "params": {"period": 20, "num_std": 2.0}},
        {"name": "rsi", "alias": "rsi_14", "params": {"period": 14}},
    ],
    "entry": {"side": "long", "rule": "close <= bb_lower and rsi_14 <= 30"},
    "exit": {"rule": "close >= bb_middle or rsi_14 >= 55"},
    "atr_period": 14,
    "stop_loss_atr_mult": 1.5,
    "take_profit_atr_mult": 2.5,
    "max_holding_bars": 24,
}

CROSS_SPEC = {
    "id": "test_tf_ema_cross",
    "name": "Test EMA cross",
    "category": "trend_following",
    "timeframe": "5min",
    "indicators": [
        {"name": "ema", "alias": "ema_fast", "params": {"period": 9}},
        {"name": "ema", "alias": "ema_slow", "params": {"period": 21}},
        {"name": "cross_above", "alias": "ema_cross_up", "params": {"a": "ema_fast", "b": "ema_slow"}},
    ],
    "entry": {"side": "long", "rule": "ema_cross_up"},
    "exit": {"rule": "False"},
    "atr_period": 14,
    "stop_loss_atr_mult": 1.0,
    "take_profit_atr_mult": 1.5,
    "max_holding_bars": 24,
}


def test_compute_indicators_produces_expected_columns():
    spec = spec_from_dict(MEAN_REVERSION_SPEC)
    strategy = DeclarativeStrategy(spec)
    out = strategy.compute_indicators(_make_df())
    for col in ["bb_upper", "bb_middle", "bb_lower", "rsi_14", "_atr", "prev_close"]:
        assert col in out.columns


def test_entry_signal_fires_only_when_conditions_met():
    spec = spec_from_dict(MEAN_REVERSION_SPEC)
    strategy = DeclarativeStrategy(spec)
    df = strategy.compute_indicators(_make_df())
    i = 50
    # Force the exact entry condition.
    df.loc[i, "close"] = df.loc[i, "bb_lower"] - 0.5
    df.loc[i, "rsi_14"] = 25.0
    ctx = StrategyContext(df=df, i=i, in_position=False)
    assert strategy.entry_signal(ctx) is True

    df.loc[i, "rsi_14"] = 60.0  # no longer oversold
    ctx = StrategyContext(df=df, i=i, in_position=False)
    assert strategy.entry_signal(ctx) is False


def test_exit_signal_reverts_to_mean():
    spec = spec_from_dict(MEAN_REVERSION_SPEC)
    strategy = DeclarativeStrategy(spec)
    df = strategy.compute_indicators(_make_df())
    i = 50
    df.loc[i, "close"] = df.loc[i, "bb_middle"] + 0.1
    df.loc[i, "rsi_14"] = 40.0
    ctx = StrategyContext(df=df, i=i, in_position=True, entry_price=90.0, entry_bar=40)
    assert strategy.exit_signal(ctx) is True


def test_nan_during_warmup_blocks_entry():
    spec = spec_from_dict(MEAN_REVERSION_SPEC)
    strategy = DeclarativeStrategy(spec)
    df = strategy.compute_indicators(_make_df())
    ctx = StrategyContext(df=df, i=1, in_position=False)  # well within indicator warmup
    assert strategy.entry_signal(ctx) is False


def test_stop_and_target_bracket_entry_price():
    spec = spec_from_dict(MEAN_REVERSION_SPEC)
    strategy = DeclarativeStrategy(spec)
    df = strategy.compute_indicators(_make_df())
    ctx = StrategyContext(df=df, i=50, in_position=False)
    sl = strategy.stop_loss(ctx)
    tp = strategy.take_profit(ctx)
    assert sl < ctx.close < tp


def test_cross_above_indicator_detects_ema_crossover():
    spec = spec_from_dict(CROSS_SPEC)
    strategy = DeclarativeStrategy(spec)
    # Construct a clean upward-crossing EMA pair directly.
    df = _make_df(n=40)
    out = strategy.compute_indicators(df)
    # Force a clean cross at index 30: fast was below, now above.
    out.loc[29, "ema_fast"] = 99.0
    out.loc[29, "ema_slow"] = 100.0
    out.loc[30, "ema_fast"] = 101.0
    out.loc[30, "ema_slow"] = 100.0
    # Recompute the cross column manually the same way generic.py does, since
    # we hand-edited ema_fast/ema_slow after compute_indicators already ran.
    out["ema_cross_up"] = (out["ema_fast"] > out["ema_slow"]) & (
        out["ema_fast"].shift(1) <= out["ema_slow"].shift(1)
    )
    ctx = StrategyContext(df=out, i=30, in_position=False)
    assert strategy.entry_signal(ctx) is True
    ctx_before = StrategyContext(df=out, i=29, in_position=False)
    assert strategy.entry_signal(ctx_before) is False
