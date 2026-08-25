import numpy as np
import pandas as pd
import pytest

from botfarm.indicators.momentum import rsi, roc, williams_r
from botfarm.indicators.trend import adx, ema, macd, sma
from botfarm.indicators.volatility import atr, bollinger_bands, true_range
from botfarm.indicators.volume import obv, volume_sma_ratio


def test_sma_hand_computed():
    s = pd.Series([1, 2, 3, 4, 5], dtype=float)
    result = sma(s, 3)
    # First two are NaN (min_periods=3); then (1+2+3)/3, (2+3+4)/3, (3+4+5)/3
    assert result.iloc[:2].isna().all()
    assert result.iloc[2] == pytest.approx(2.0)
    assert result.iloc[3] == pytest.approx(3.0)
    assert result.iloc[4] == pytest.approx(4.0)


def test_ema_hand_computed():
    # span=3 -> alpha = 2/(3+1) = 0.5
    s = pd.Series([1, 2, 3], dtype=float)
    result = ema(s, 3)
    assert result.iloc[:2].isna().all()
    # seed = mean of first `period` values per pandas ewm(adjust=False) with min_periods
    # pandas computes the full recursive EMA from index 0 regardless of min_periods,
    # it just masks early values as NaN. EMA0=1, EMA1=1+0.5*(2-1)=1.5, EMA2=1.5+0.5*(3-1.5)=2.25
    assert result.iloc[2] == pytest.approx(2.25)


def test_rsi_all_gains_is_100():
    s = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16], dtype=float)
    result = rsi(s, period=14)
    assert result.iloc[-1] == pytest.approx(100.0)


def test_rsi_all_losses_is_0():
    s = pd.Series(list(range(20, 0, -1)), dtype=float)
    result = rsi(s, period=14)
    assert result.iloc[-1] == pytest.approx(0.0)


def test_true_range_hand_computed():
    high = pd.Series([10, 12, 11], dtype=float)
    low = pd.Series([8, 9, 9], dtype=float)
    close = pd.Series([9, 11, 10], dtype=float)
    tr = true_range(high, low, close)
    assert tr.iloc[0] == pytest.approx(2.0)  # high-low, no prev close
    # bar 1: max(12-9, |12-9|, |9-9|) = max(3,3,0) = 3
    assert tr.iloc[1] == pytest.approx(3.0)
    # bar 2: max(11-9, |11-11|, |9-11|) = max(2,0,2) = 2
    assert tr.iloc[2] == pytest.approx(2.0)


def test_bollinger_bands_hand_computed():
    s = pd.Series([2, 4, 6, 8, 10], dtype=float)
    upper, middle, lower = bollinger_bands(s, period=5, num_std=2.0)
    mean = 6.0
    std = np.std([2, 4, 6, 8, 10])  # population std, ddof=0
    assert middle.iloc[-1] == pytest.approx(mean)
    assert upper.iloc[-1] == pytest.approx(mean + 2 * std)
    assert lower.iloc[-1] == pytest.approx(mean - 2 * std)


def test_macd_hand_computed_matches_component_emas():
    s = pd.Series(np.linspace(100, 150, 40), dtype=float)
    macd_line, signal_line, hist = macd(s, fast=12, slow=26, signal=9)
    expected_macd = ema(s, 12) - ema(s, 26)
    pd.testing.assert_series_equal(macd_line, expected_macd, check_names=False)
    expected_hist = (macd_line - signal_line).dropna().to_numpy()
    assert hist.dropna().to_numpy() == pytest.approx(expected_hist)


def test_obv_hand_computed():
    close = pd.Series([10, 11, 10, 12], dtype=float)
    volume = pd.Series([100, 200, 150, 300], dtype=float)
    result = obv(close, volume)
    # bar0: diff=0 (fillna) -> sign 0 -> 0
    # bar1: up -> +200 -> cum 200
    # bar2: down -> -150 -> cum 50
    # bar3: up -> +300 -> cum 350
    assert result.iloc[0] == pytest.approx(0.0)
    assert result.iloc[1] == pytest.approx(200.0)
    assert result.iloc[2] == pytest.approx(50.0)
    assert result.iloc[3] == pytest.approx(350.0)


def test_volume_sma_ratio_hand_computed():
    volume = pd.Series([10, 10, 10, 10, 40], dtype=float)
    result = volume_sma_ratio(volume, period=4)
    # avg of first 4 = 10, ratio at idx3 = 10/10 = 1.0
    assert result.iloc[3] == pytest.approx(1.0)
    # avg of idx1..4 = (10+10+10+40)/4 = 17.5, ratio = 40/17.5
    assert result.iloc[4] == pytest.approx(40 / 17.5)


def test_roc_hand_computed():
    s = pd.Series([10, 11, 12, 15], dtype=float)
    result = roc(s, period=3)
    assert result.iloc[3] == pytest.approx(100 * (15 - 10) / 10)


def test_williams_r_bounds():
    high = pd.Series(np.linspace(10, 20, 20), dtype=float)
    low = pd.Series(np.linspace(5, 15, 20), dtype=float)
    close = high  # close at the high -> %R should be 0 (top of range)
    result = williams_r(high, low, close, period=14)
    assert result.iloc[-1] == pytest.approx(0.0)


def test_adx_high_for_strong_uptrend_low_for_chop():
    n = 60
    # Strong, steady uptrend: ADX should end up clearly elevated and +DI > -DI.
    trend_close = pd.Series(np.linspace(100, 160, n))
    trend_high = trend_close + 0.3
    trend_low = trend_close - 0.3
    adx_trend, plus_di_trend, minus_di_trend = adx(trend_high, trend_low, trend_close, period=14)
    assert adx_trend.iloc[-1] > 25
    assert plus_di_trend.iloc[-1] > minus_di_trend.iloc[-1]

    # Flat/choppy oscillation around a fixed level: ADX should stay low.
    rng = np.random.default_rng(7)
    chop_close = pd.Series(100 + rng.normal(0, 0.3, n))
    chop_high = chop_close + 0.4
    chop_low = chop_close - 0.4
    adx_chop, _, _ = adx(chop_high, chop_low, chop_close, period=14)
    assert adx_chop.iloc[-1] < 20
    assert adx_chop.iloc[-1] < adx_trend.iloc[-1]


def test_atr_positive_and_defined_after_warmup():
    high = pd.Series(np.random.default_rng(0).uniform(100, 110, 30))
    low = high - np.random.default_rng(1).uniform(1, 5, 30)
    close = (high + low) / 2
    result = atr(high, low, close, period=14)
    assert result.iloc[:13].isna().all()
    assert (result.dropna() > 0).all()
