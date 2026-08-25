"""Volume indicators: OBV, VWAP, volume z-score."""
from __future__ import annotations

import numpy as np
import pandas as pd


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff().fillna(0))
    return (direction * volume).cumsum()


def rolling_vwap(
    high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, period: int = 20
) -> pd.Series:
    """Rolling (not session-anchored) VWAP over `period` bars — appropriate
    for a continuously-running scalp bot with no natural session boundary."""
    typical_price = (high + low + close) / 3
    pv = typical_price * volume
    return pv.rolling(window=period, min_periods=period).sum() / volume.rolling(
        window=period, min_periods=period
    ).sum()


def volume_zscore(volume: pd.Series, period: int = 20) -> pd.Series:
    mean = volume.rolling(window=period, min_periods=period).mean()
    std = volume.rolling(window=period, min_periods=period).std(ddof=0)
    return (volume - mean) / std.replace(0, float("nan"))


def volume_sma_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    """Current bar volume divided by its trailing average — used for simple
    liquidity/participation confirmation filters."""
    avg = volume.rolling(window=period, min_periods=period).mean()
    return volume / avg.replace(0, float("nan"))
