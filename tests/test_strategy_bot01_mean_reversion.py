import numpy as np
import pandas as pd

from botfarm.strategy.base import StrategyContext
from botfarm.strategy.bot01_mean_reversion import Bot01MeanReversion, MeanReversionParams


def _make_ranging_df(n=80):
    rng = np.random.default_rng(3)
    closes = 100 + np.cumsum(rng.normal(0, 0.5, n))
    highs = closes + rng.uniform(0.1, 0.5, n)
    lows = closes - rng.uniform(0.1, 0.5, n)
    volume = rng.uniform(50, 150, n)
    return pd.DataFrame(
        {
            "ts_ms": [1_600_000_000_000 + i * 300_000 for i in range(n)],
            "open": closes, "high": highs, "low": lows, "close": closes, "base_volume": volume,
        }
    )


def test_compute_indicators_adds_expected_columns():
    strategy = Bot01MeanReversion()
    out = strategy.compute_indicators(_make_ranging_df())
    for col in ["bb_upper", "bb_middle", "bb_lower", "rsi", "atr"]:
        assert col in out.columns


def test_stop_below_entry_target_above_entry():
    strategy = Bot01MeanReversion()
    df = strategy.compute_indicators(_make_ranging_df())
    ctx = StrategyContext(df=df, i=50, in_position=False)
    sl = strategy.stop_loss(ctx)
    tp = strategy.take_profit(ctx)
    assert sl < ctx.close < tp


def test_entry_requires_price_at_or_below_lower_band_and_oversold_rsi():
    strategy = Bot01MeanReversion()
    df = strategy.compute_indicators(_make_ranging_df())
    # Construct a row that clearly fails the entry condition (price at/above middle band).
    i = 50
    df.loc[i, "close"] = df.loc[i, "bb_upper"] + 1  # far above the bands
    df.loc[i, "rsi"] = 80  # overbought, not oversold
    ctx = StrategyContext(df=df, i=i, in_position=False)
    assert strategy.entry_signal(ctx) is False


def test_exit_signal_true_when_price_reverts_to_middle_band():
    strategy = Bot01MeanReversion()
    df = strategy.compute_indicators(_make_ranging_df())
    i = 50
    df.loc[i, "close"] = df.loc[i, "bb_middle"] + 0.01
    df.loc[i, "rsi"] = 40  # below rsi_exit, so exit must come from the price condition
    ctx = StrategyContext(df=df, i=i, in_position=True, entry_price=90.0, entry_bar=40)
    assert strategy.exit_signal(ctx) is True


def test_adx_filter_blocks_entry_when_configured():
    params = MeanReversionParams(adx_max=20.0)
    strategy = Bot01MeanReversion(params)
    df = strategy.compute_indicators(_make_ranging_df())
    i = 50
    df.loc[i, "close"] = df.loc[i, "bb_lower"] - 0.01  # satisfies price condition
    df.loc[i, "rsi"] = 20.0  # satisfies RSI condition
    df.loc[i, "adx"] = 40.0  # strongly trending -> should block a mean-reversion entry
    ctx = StrategyContext(df=df, i=i, in_position=False)
    assert strategy.entry_signal(ctx) is False
