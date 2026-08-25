"""Momentum/oscillator indicators: RSI, Stochastic, ROC, Williams %R, CCI."""
from __future__ import annotations

import pandas as pd

from .trend import sma


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    # Wilder's smoothing (equivalent to an EMA with alpha = 1/period).
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    result = 100 - (100 / (1 + rs))
    return result.where(avg_loss != 0, 100.0)


def stochastic(
    high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14, d_period: int = 3
) -> tuple[pd.Series, pd.Series]:
    """Returns (%K, %D)."""
    lowest_low = low.rolling(window=k_period, min_periods=k_period).min()
    highest_high = high.rolling(window=k_period, min_periods=k_period).max()
    denom = (highest_high - lowest_low).replace(0, float("nan"))
    percent_k = 100 * (close - lowest_low) / denom
    percent_d = percent_k.rolling(window=d_period, min_periods=d_period).mean()
    return percent_k, percent_d


def roc(series: pd.Series, period: int = 12) -> pd.Series:
    return 100 * (series - series.shift(period)) / series.shift(period)


def williams_r(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    highest_high = high.rolling(window=period, min_periods=period).max()
    lowest_low = low.rolling(window=period, min_periods=period).min()
    denom = (highest_high - lowest_low).replace(0, float("nan"))
    return -100 * (highest_high - close) / denom


def cci(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> pd.Series:
    typical_price = (high + low + close) / 3
    tp_sma = sma(typical_price, period)
    mean_dev = typical_price.rolling(window=period, min_periods=period).apply(
        lambda x: (x - x.mean()).abs().mean(), raw=True
    )
    return (typical_price - tp_sma) / (0.015 * mean_dev.replace(0, float("nan")))
