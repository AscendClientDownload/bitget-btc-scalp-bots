"""Bot #1 (reference implementation): EMA(9/21) trend cross + RSI momentum
filter + volume confirmation, ATR-based stop/target, 5-minute BTCUSDT, long-only.

Chosen as the first bot because it's multi-indicator confluence (trend +
momentum + volume) rather than a single naive indicator, every parameter maps
to a named testable rule, and 5-minute bars give the trade more room than
1-minute against Bitget's ~0.2% round-trip taker fee.

Parameters live on a `Bot01Params` dataclass (not module constants) so
alternative configurations can be backtested side-by-side without copy-pasting
the strategy — see scripts/research_bot01_variants.py, which is how the
current defaults below were chosen (evaluated on a training slice, then
validated on a held-out slice — not fit directly on the numbers reported in
reports/bot01_ema_rsi_atr/).
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from botfarm.indicators.momentum import rsi as rsi_ind
from botfarm.indicators.trend import adx as adx_ind
from botfarm.indicators.trend import ema
from botfarm.indicators.volatility import atr as atr_ind
from botfarm.indicators.volume import volume_sma_ratio
from botfarm.strategy.base import IndicatorSpec, Strategy, StrategyContext


@dataclass(frozen=True)
class Bot01Params:
    ema_fast_period: int = 9
    ema_slow_period: int = 21
    rsi_period: int = 14
    rsi_low: float = 50.0
    rsi_high: float = 70.0
    volume_lookback: int = 20
    volume_ratio_min: float = 1.0
    atr_period: int = 14
    atr_stop_mult: float = 1.0
    atr_target_mult: float = 1.5
    max_holding_bars: int = 24  # ~2h on 5min bars
    # Trend/regime filters (None disables the filter):
    trend_ema_period: int | None = None  # only long if close > EMA(trend_ema_period)
    adx_period: int = 14
    adx_min: float | None = None  # only long if ADX >= adx_min (trending, not choppy)


DEFAULT_PARAMS = Bot01Params(
    trend_ema_period=100,
    adx_min=20.0,
    atr_stop_mult=1.5,
    atr_target_mult=2.5,
)


class Bot01EmaRsiAtr(Strategy):
    id = "bot01_ema_rsi_atr"
    timeframe = "5min"

    def __init__(self, params: Bot01Params | None = None):
        self.params = params or DEFAULT_PARAMS
        self.max_holding_bars = self.params.max_holding_bars

    def required_indicators(self) -> list[IndicatorSpec]:
        p = self.params
        specs = [
            IndicatorSpec("ema", "ema_fast", {"period": p.ema_fast_period}),
            IndicatorSpec("ema", "ema_slow", {"period": p.ema_slow_period}),
            IndicatorSpec("rsi", "rsi", {"period": p.rsi_period}),
            IndicatorSpec("volume_sma_ratio", "vol_ratio", {"period": p.volume_lookback}),
            IndicatorSpec("atr", "atr", {"period": p.atr_period}),
        ]
        if p.trend_ema_period is not None:
            specs.append(IndicatorSpec("ema", "ema_trend", {"period": p.trend_ema_period}))
        if p.adx_min is not None:
            specs.append(IndicatorSpec("adx", "adx", {"period": p.adx_period}))
        return specs

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Vectorized indicator computation over the full OHLCV frame."""
        p = self.params
        out = df.copy()
        out["ema_fast"] = ema(out["close"], p.ema_fast_period)
        out["ema_slow"] = ema(out["close"], p.ema_slow_period)
        out["rsi"] = rsi_ind(out["close"], p.rsi_period)
        out["vol_ratio"] = volume_sma_ratio(out["base_volume"], p.volume_lookback)
        out["atr"] = atr_ind(out["high"], out["low"], out["close"], p.atr_period)
        out["ema_cross_up"] = (out["ema_fast"] > out["ema_slow"]) & (
            out["ema_fast"].shift(1) <= out["ema_slow"].shift(1)
        )
        if p.trend_ema_period is not None:
            out["ema_trend"] = ema(out["close"], p.trend_ema_period)
        if p.adx_min is not None:
            out["adx"], _, _ = adx_ind(out["high"], out["low"], out["close"], p.adx_period)
        return out

    def entry_signal(self, ctx: StrategyContext) -> bool:
        p = self.params
        row = ctx.row
        required_cols = ["ema_cross_up", "rsi", "vol_ratio"]
        if p.trend_ema_period is not None:
            required_cols.append("ema_trend")
        if p.adx_min is not None:
            required_cols.append("adx")
        if pd.isna(row[required_cols]).any():
            return False

        if not row["ema_cross_up"]:
            return False
        if not (p.rsi_low <= row["rsi"] <= p.rsi_high):
            return False
        if not (row["vol_ratio"] > p.volume_ratio_min):
            return False
        if p.trend_ema_period is not None and not (row["close"] > row["ema_trend"]):
            return False
        if p.adx_min is not None and not (row["adx"] >= p.adx_min):
            return False
        return True

    def exit_signal(self, ctx: StrategyContext) -> bool:
        # No standalone signal-exit for bot #1: exits are entirely governed by
        # stop_loss/take_profit/time-stop, checked independently by the engine.
        return False

    def stop_loss(self, ctx: StrategyContext) -> float:
        atr_val = float(ctx.row["atr"])
        return ctx.close - self.params.atr_stop_mult * atr_val

    def take_profit(self, ctx: StrategyContext) -> float:
        atr_val = float(ctx.row["atr"])
        return ctx.close + self.params.atr_target_mult * atr_val
