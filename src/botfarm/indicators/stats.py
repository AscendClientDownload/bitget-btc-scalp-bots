"""Simple statistical helpers: rolling z-score, %B."""
from __future__ import annotations

import pandas as pd

from .volatility import bollinger_bands


def zscore(series: pd.Series, period: int = 20) -> pd.Series:
    mean = series.rolling(window=period, min_periods=period).mean()
    std = series.rolling(window=period, min_periods=period).std(ddof=0)
    return (series - mean) / std.replace(0, float("nan"))


def percent_b(series: pd.Series, period: int = 20, num_std: float = 2.0) -> pd.Series:
    """Bollinger %B: position of price within the bands, 0 = lower band, 1 = upper band."""
    upper, _, lower = bollinger_bands(series, period, num_std)
    denom = (upper - lower).replace(0, float("nan"))
    return (series - lower) / denom
