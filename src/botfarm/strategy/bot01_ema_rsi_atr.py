"""Bot #1 (reference implementation): EMA(9/21) trend cross + RSI momentum
filter + volume confirmation, ATR-based stop/target, 5-minute BTCUSDT, long-only.

Chosen as the first bot because it's multi-indicator confluence (trend +
momentum + volume) rather than a single naive indicator, every parameter maps
to a named testable rule, and 5-minute bars give the trade more room than
1-minute against Bitget's ~0.2% round-trip taker fee.
"""
from __future__ import annotations

import pandas as pd

from botfarm.indicators.momentum import rsi as rsi_ind
from botfarm.indicators.trend import ema
from botfarm.indicators.volatility import atr as atr_ind
from botfarm.indicators.volume import volume_sma_ratio
from botfarm.strategy.base import IndicatorSpec, Strategy, StrategyContext

EMA_FAST_PERIOD = 9
EMA_SLOW_PERIOD = 21
RSI_PERIOD = 14
RSI_LOW = 50.0
RSI_HIGH = 70.0
VOLUME_LOOKBACK = 20
VOLUME_RATIO_MIN = 1.0
ATR_PERIOD = 14
ATR_STOP_MULT = 1.0
ATR_TARGET_MULT = 1.5
MAX_HOLDING_BARS = 24  # ~2h on 5min bars


class Bot01EmaRsiAtr(Strategy):
    id = "bot01_ema_rsi_atr"
    timeframe = "5min"
    max_holding_bars = MAX_HOLDING_BARS

    def required_indicators(self) -> list[IndicatorSpec]:
        return [
            IndicatorSpec("ema", "ema_fast", {"period": EMA_FAST_PERIOD}),
            IndicatorSpec("ema", "ema_slow", {"period": EMA_SLOW_PERIOD}),
            IndicatorSpec("rsi", "rsi", {"period": RSI_PERIOD}),
            IndicatorSpec("volume_sma_ratio", "vol_ratio", {"period": VOLUME_LOOKBACK}),
            IndicatorSpec("atr", "atr", {"period": ATR_PERIOD}),
        ]

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Vectorized indicator computation over the full OHLCV frame."""
        out = df.copy()
        out["ema_fast"] = ema(out["close"], EMA_FAST_PERIOD)
        out["ema_slow"] = ema(out["close"], EMA_SLOW_PERIOD)
        out["rsi"] = rsi_ind(out["close"], RSI_PERIOD)
        out["vol_ratio"] = volume_sma_ratio(out["base_volume"], VOLUME_LOOKBACK)
        out["atr"] = atr_ind(out["high"], out["low"], out["close"], ATR_PERIOD)
        out["ema_cross_up"] = (out["ema_fast"] > out["ema_slow"]) & (
            out["ema_fast"].shift(1) <= out["ema_slow"].shift(1)
        )
        return out

    def entry_signal(self, ctx: StrategyContext) -> bool:
        row = ctx.row
        if pd.isna(row[["ema_cross_up", "rsi", "vol_ratio"]]).any():
            return False
        return bool(
            row["ema_cross_up"]
            and RSI_LOW <= row["rsi"] <= RSI_HIGH
            and row["vol_ratio"] > VOLUME_RATIO_MIN
        )

    def exit_signal(self, ctx: StrategyContext) -> bool:
        # No standalone signal-exit for bot #1: exits are entirely governed by
        # stop_loss/take_profit/time-stop, checked independently by the engine.
        return False

    def stop_loss(self, ctx: StrategyContext) -> float:
        atr_val = float(ctx.row["atr"])
        return ctx.close - ATR_STOP_MULT * atr_val

    def take_profit(self, ctx: StrategyContext) -> float:
        atr_val = float(ctx.row["atr"])
        return ctx.close + ATR_TARGET_MULT * atr_val
