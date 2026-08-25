"""Bot #1, mean-reversion pivot: Bollinger Band + RSI oversold entry, betting
on a bounce back toward the mean rather than following a trend.

The EMA-cross trend-following version (bot01_ema_rsi_atr.py) was tested
across 5 filtered variants on a train/holdout split and showed no real edge
on 5-minute BTCUSDT in any configuration — trend-following needs a market
that actually trends, and most 5-minute BTC price action is range-bound
noise (confirmed by the ADX research: ADX >= 20 held on a minority of bars).
Mean-reversion is the natural strategy family for range-bound conditions, so
bot #1 pivots here rather than continuing to tune a strategy family that
doesn't fit this timeframe's typical regime.

Entry: price closes at/below the lower Bollinger Band while RSI is oversold
(optionally only when ADX confirms the market is NOT strongly trending, since
buying a dip into a strong downtrend is the classic mean-reversion failure
mode — "catching a falling knife"). Exit: price reverts to the middle band
(the mean) or RSI recovers, with an ATR-based stop-loss as a hard backstop
against a reversion that doesn't happen.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from botfarm.indicators.momentum import rsi as rsi_ind
from botfarm.indicators.trend import adx as adx_ind
from botfarm.indicators.volatility import atr as atr_ind
from botfarm.indicators.volatility import bollinger_bands
from botfarm.indicators.volume import volume_sma_ratio
from botfarm.strategy.base import IndicatorSpec, Strategy, StrategyContext


@dataclass(frozen=True)
class MeanReversionParams:
    bb_period: int = 20
    bb_std: float = 2.0
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_exit: float = 50.0
    atr_period: int = 14
    atr_stop_mult: float = 1.5
    atr_target_mult: float = 3.0  # generous backstop; exit_signal should fire first on a real reversion
    max_holding_bars: int = 24  # ~2h on 5min bars
    adx_period: int = 14
    adx_max: float | None = None  # only long if ADX <= adx_max (avoid buying dips in a strong downtrend)
    # Extra confluence filters, for fewer/higher-conviction entries (None disables each):
    volume_lookback: int = 20
    volume_ratio_min: float | None = None  # require a volume spike (capitulation) on the entry bar
    min_close_position: float | None = None  # require close in the upper X% of the bar's range (rejection wick)


DEFAULT_PARAMS = MeanReversionParams(adx_max=20.0)
# Chosen from scripts/research_mean_reversion_variants.py's train/holdout
# comparison (variant B): the ADX<=20 "don't fight a strong trend" filter was
# the single biggest lever for reducing losses across every variant tested,
# and it's a simple, explainable rule rather than a heavily-tuned one. It is
# NOT a profitable configuration -- see reports/bot01_mean_reversion/ and
# docs/RISK_DISCLAIMER.md. Stacking further filters (tighter RSI, volume
# spike, rejection candle, or all of them at once) was also tested and did
# not turn expectancy positive; the "max confluence" combination produced
# zero trades across the entire year of data.


class Bot01MeanReversion(Strategy):
    id = "bot01_mean_reversion"
    timeframe = "5min"

    def __init__(self, params: MeanReversionParams | None = None):
        self.params = params or DEFAULT_PARAMS
        self.max_holding_bars = self.params.max_holding_bars

    def required_indicators(self) -> list[IndicatorSpec]:
        p = self.params
        specs = [
            IndicatorSpec("bollinger_bands", "bb", {"period": p.bb_period, "num_std": p.bb_std}),
            IndicatorSpec("rsi", "rsi", {"period": p.rsi_period}),
            IndicatorSpec("atr", "atr", {"period": p.atr_period}),
        ]
        if p.adx_max is not None:
            specs.append(IndicatorSpec("adx", "adx", {"period": p.adx_period}))
        if p.volume_ratio_min is not None:
            specs.append(IndicatorSpec("volume_sma_ratio", "vol_ratio", {"period": p.volume_lookback}))
        return specs

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        out = df.copy()
        out["bb_upper"], out["bb_middle"], out["bb_lower"] = bollinger_bands(
            out["close"], p.bb_period, p.bb_std
        )
        out["rsi"] = rsi_ind(out["close"], p.rsi_period)
        out["atr"] = atr_ind(out["high"], out["low"], out["close"], p.atr_period)
        if p.adx_max is not None:
            out["adx"], _, _ = adx_ind(out["high"], out["low"], out["close"], p.adx_period)
        if p.volume_ratio_min is not None:
            out["vol_ratio"] = volume_sma_ratio(out["base_volume"], p.volume_lookback)
        if p.min_close_position is not None:
            bar_range = (out["high"] - out["low"]).replace(0, float("nan"))
            out["close_position"] = (out["close"] - out["low"]) / bar_range
        return out

    def entry_signal(self, ctx: StrategyContext) -> bool:
        p = self.params
        row = ctx.row
        required_cols = ["bb_lower", "rsi", "atr"]
        if p.adx_max is not None:
            required_cols.append("adx")
        if p.volume_ratio_min is not None:
            required_cols.append("vol_ratio")
        if p.min_close_position is not None:
            required_cols.append("close_position")
        if pd.isna(row[required_cols]).any():
            return False

        if not (row["close"] <= row["bb_lower"]):
            return False
        if not (row["rsi"] <= p.rsi_oversold):
            return False
        if p.adx_max is not None and not (row["adx"] <= p.adx_max):
            return False
        if p.volume_ratio_min is not None and not (row["vol_ratio"] > p.volume_ratio_min):
            return False
        if p.min_close_position is not None and not (row["close_position"] >= p.min_close_position):
            return False
        return True

    def exit_signal(self, ctx: StrategyContext) -> bool:
        p = self.params
        row = ctx.row
        if pd.isna(row[["bb_middle", "rsi"]]).any():
            return False
        return bool(row["close"] >= row["bb_middle"] or row["rsi"] >= p.rsi_exit)

    def stop_loss(self, ctx: StrategyContext) -> float:
        atr_val = float(ctx.row["atr"])
        return ctx.close - self.params.atr_stop_mult * atr_val

    def take_profit(self, ctx: StrategyContext) -> float:
        atr_val = float(ctx.row["atr"])
        return ctx.close + self.params.atr_target_mult * atr_val
