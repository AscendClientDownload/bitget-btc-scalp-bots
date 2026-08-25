"""Generates the 100 catalog/specs/<category>/*.yaml files from the strategy
definitions below. Run this once to (re)produce the committed YAML files --
the YAML files themselves are what the rest of the system reads; this script
is the record of how they were constructed and how to regenerate them.

Each entry is deliberately a distinct rule/indicator combination, not a bare
parameter sweep of an identical rule -- see docs/STRATEGY_CATALOG.md (generated
separately by generate_catalog_md.py) for the rendered, browsable version.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from botfarm.catalog.schema import SPECS_DIR, spec_from_dict  # noqa: E402
from botfarm.strategy.safe_eval import compile_check  # noqa: E402

DEFAULT_TIMEFRAME = "5min"
DEFAULT_ATR_PERIOD = 14
DEFAULT_MAX_HOLDING = 24


def spec(
    id: str,
    name: str,
    category: str,
    indicators: list[dict],
    entry_rule: str,
    exit_rule: str,
    stop_mult: float,
    target_mult: float,
    notes: str,
    timeframe: str = DEFAULT_TIMEFRAME,
    atr_period: int = DEFAULT_ATR_PERIOD,
    max_holding_bars: int = DEFAULT_MAX_HOLDING,
) -> dict:
    return {
        "id": id,
        "name": name,
        "category": category,
        "timeframe": timeframe,
        "indicators": indicators,
        "entry": {"side": "long", "rule": entry_rule},
        "exit": {"rule": exit_rule},
        "atr_period": atr_period,
        "stop_loss_atr_mult": stop_mult,
        "take_profit_atr_mult": target_mult,
        "max_holding_bars": max_holding_bars,
        "notes": notes,
    }


def ema(alias: str, period: int) -> dict:
    return {"name": "ema", "alias": alias, "params": {"period": period}}


def sma(alias: str, period: int) -> dict:
    return {"name": "sma", "alias": alias, "params": {"period": period}}


def cross_above(alias: str, a, b) -> dict:
    return {"name": "cross_above", "alias": alias, "params": {"a": a, "b": b}}


SPECS: list[dict] = []

# ============================== trend_following (14) ==============================
SPECS += [
    spec(
        "tf_001_ema9_21_cross", "EMA 9/21 Cross", "trend_following",
        [ema("ema_fast", 9), ema("ema_slow", 21), cross_above("ema_cross_up", "ema_fast", "ema_slow")],
        "ema_cross_up", "False", 1.0, 1.5,
        "Classic fast/slow EMA crossover, the textbook trend-following entry.",
    ),
    spec(
        "tf_002_ema5_13_cross", "EMA 5/13 Cross (fast)", "trend_following",
        [ema("ema_fast", 5), ema("ema_slow", 13), cross_above("ema_cross_up", "ema_fast", "ema_slow")],
        "ema_cross_up", "False", 1.0, 1.5,
        "Faster EMA pair for quicker (noisier) trend entries.",
    ),
    spec(
        "tf_003_ema13_34_cross", "EMA 13/34 Cross", "trend_following",
        [ema("ema_fast", 13), ema("ema_slow", 34), cross_above("ema_cross_up", "ema_fast", "ema_slow")],
        "ema_cross_up", "False", 1.2, 1.8,
        "Fibonacci-spaced EMA pair, slower than the 9/21 baseline.",
    ),
    spec(
        "tf_004_ema21_55_cross", "EMA 21/55 Cross (slow)", "trend_following",
        [ema("ema_fast", 21), ema("ema_slow", 55), cross_above("ema_cross_up", "ema_fast", "ema_slow")],
        "ema_cross_up", "False", 1.5, 2.2,
        "Slow EMA pair aimed at fewer, larger trend moves.",
    ),
    spec(
        "tf_005_sma10_30_cross", "SMA 10/30 Cross", "trend_following",
        [sma("sma_fast", 10), sma("sma_slow", 30), cross_above("sma_cross_up", "sma_fast", "sma_slow")],
        "sma_cross_up", "False", 1.0, 1.5,
        "Simple (not exponential) moving average crossover.",
    ),
    spec(
        "tf_006_sma20_50_cross", "SMA 20/50 Cross", "trend_following",
        [sma("sma_fast", 20), sma("sma_slow", 50), cross_above("sma_cross_up", "sma_fast", "sma_slow")],
        "sma_cross_up", "False", 1.3, 2.0,
        "Slower SMA pair, a classic \"golden cross\" style signal at scalp scale.",
    ),
    spec(
        "tf_007_sma5_20_cross", "SMA 5/20 Cross (fast)", "trend_following",
        [sma("sma_fast", 5), sma("sma_slow", 20), cross_above("sma_cross_up", "sma_fast", "sma_slow")],
        "sma_cross_up", "False", 0.9, 1.4,
        "Fast SMA pair for quick trend catches.",
    ),
    spec(
        "tf_008_macd_signal_cross", "MACD Signal Line Cross", "trend_following",
        [{"name": "macd", "alias": "macd", "params": {"fast": 12, "slow": 26, "signal": 9}},
         cross_above("macd_cross_up", "macd_line", "macd_signal")],
        "macd_cross_up", "False", 1.2, 1.8,
        "MACD line crossing above its signal line.",
    ),
    spec(
        "tf_009_macd_zero_cross", "MACD Zero-Line Cross", "trend_following",
        [{"name": "macd", "alias": "macd", "params": {"fast": 12, "slow": 26, "signal": 9}},
         cross_above("macd_zero_up", "macd_line", 0)],
        "macd_zero_up", "False", 1.2, 1.8,
        "MACD line crossing above zero -- a coarser, less frequent trend signal.",
    ),
    spec(
        "tf_010_ema_cross_adx_filter", "EMA Cross + ADX Trend Filter", "trend_following",
        [ema("ema_fast", 9), ema("ema_slow", 21), cross_above("ema_cross_up", "ema_fast", "ema_slow"),
         {"name": "adx", "alias": "adx", "params": {"period": 14}}],
        "ema_cross_up and adx >= 20", "False", 1.0, 1.5,
        "EMA cross gated by ADX>=20 so it only fires in confirmed-trending conditions.",
    ),
    spec(
        "tf_011_ema_cross_vol_filter", "EMA Cross + Volume Confirmation", "trend_following",
        [ema("ema_fast", 9), ema("ema_slow", 21), cross_above("ema_cross_up", "ema_fast", "ema_slow"),
         {"name": "volume_sma_ratio", "alias": "vol_ratio", "params": {"period": 20}}],
        "ema_cross_up and vol_ratio > 1.2", "False", 1.0, 1.5,
        "EMA cross requiring above-average volume on the crossing bar.",
    ),
    spec(
        "tf_012_dual_ema_ribbon", "Triple EMA Ribbon Alignment", "trend_following",
        [ema("ema9", 9), ema("ema21", 21), ema("ema50", 50)],
        "close > ema9 and ema9 > ema21 and ema21 > ema50", "close < ema21", 1.3, 2.0,
        "No single cross event -- entry requires price and three EMAs already stacked in trend order.",
    ),
    spec(
        "tf_013_adx_di_cross", "+DI/-DI Directional Cross", "trend_following",
        [{"name": "adx", "alias": "adx", "params": {"period": 14}},
         cross_above("di_cross_up", "plus_di", "minus_di")],
        "di_cross_up and adx >= 15", "False", 1.2, 1.8,
        "+DI crossing above -DI (directional movement flip), gated by a minimum ADX.",
    ),
    spec(
        "tf_014_sma_slope_alignment", "SMA20 above SMA50 Alignment", "trend_following",
        [sma("sma20", 20), sma("sma50", 50)],
        "close > sma20 and sma20 > sma50", "close < sma20", 1.3, 2.0,
        "Price/short-MA/long-MA alignment filter, a slope proxy without an explicit cross event.",
    ),
]

# ============================== mean_reversion (14) ==============================
def bb(alias_prefix: str, period: int, num_std: float) -> dict:
    return {"name": "bollinger_bands", "alias": alias_prefix, "params": {"period": period, "num_std": num_std}}


def rsi(alias: str, period: int) -> dict:
    return {"name": "rsi", "alias": alias, "params": {"period": period}}


SPECS += [
    spec(
        "mr_001_bb_rsi_classic", "Bollinger + RSI Classic Reversion", "mean_reversion",
        [bb("bb", 20, 2.0), rsi("rsi_14", 14)],
        "close <= bb_lower and rsi_14 <= 30", "close >= bb_middle or rsi_14 >= 55", 1.5, 2.5,
        "The textbook BB-touch + RSI-oversold mean-reversion entry.",
    ),
    spec(
        "mr_002_bb_wide_rsi_deep", "Wide Bands + Deep RSI Oversold", "mean_reversion",
        [bb("bb", 20, 2.5), rsi("rsi_14", 14)],
        "close <= bb_lower and rsi_14 <= 25", "close >= bb_middle or rsi_14 >= 50", 1.5, 2.5,
        "Wider bands (2.5 std) and a stricter RSI threshold for rarer, more extreme entries.",
    ),
    spec(
        "mr_003_vwap_reversion", "VWAP Deviation Reversion", "mean_reversion",
        [{"name": "rolling_vwap", "alias": "vwap", "params": {"period": 20}}, rsi("rsi_14", 14)],
        "close < vwap * 0.998 and rsi_14 <= 35", "close > vwap or rsi_14 >= 55", 1.5, 2.5,
        "Price deviated 0.2% below its rolling VWAP with RSI confirmation.",
    ),
    spec(
        "mr_004_zscore_reversion_20", "Z-Score Reversion (20-bar)", "mean_reversion",
        [{"name": "zscore", "alias": "z", "params": {"period": 20}}],
        "z <= -2.0", "z >= 0", 1.5, 2.5,
        "Pure statistical deviation entry: price 2 standard deviations below its 20-bar mean.",
    ),
    spec(
        "mr_005_percent_b_reversion", "Bollinger %B Reversion", "mean_reversion",
        [{"name": "percent_b", "alias": "pct_b", "params": {"period": 20, "num_std": 2.0}}],
        "pct_b <= 0.05", "pct_b >= 0.5", 1.5, 2.5,
        "Entry via %B (position within the bands) instead of a raw band-touch comparison.",
    ),
    spec(
        "mr_006_bb_rsi_adx_filter", "BB+RSI with Range-Bound Filter", "mean_reversion",
        [bb("bb", 20, 2.0), rsi("rsi_14", 14), {"name": "adx", "alias": "adx", "params": {"period": 14}}],
        "close <= bb_lower and rsi_14 <= 30 and adx <= 20", "close >= bb_middle or rsi_14 >= 55", 1.5, 2.5,
        "Classic BB+RSI entry gated by ADX<=20 to avoid mean-reverting into a strong trend.",
    ),
    spec(
        "mr_007_double_bb_tight", "Tight Bollinger Bands (1.5 std)", "mean_reversion",
        [bb("bb", 20, 1.5), rsi("rsi_14", 14)],
        "close <= bb_lower and rsi_14 <= 30", "close >= bb_middle or rsi_14 >= 55", 1.2, 2.0,
        "Narrower bands trade more often on smaller deviations.",
    ),
    spec(
        "mr_008_vwap_zscore_combo", "VWAP + Z-Score Confluence", "mean_reversion",
        [{"name": "rolling_vwap", "alias": "vwap", "params": {"period": 20}},
         {"name": "zscore", "alias": "z", "params": {"period": 20}}],
        "close < vwap and z <= -1.5", "close > vwap", 1.5, 2.5,
        "Two independent deviation measures (VWAP and z-score) must agree.",
    ),
    spec(
        "mr_009_rsi_extreme_fast", "Fast RSI Extreme (no bands)", "mean_reversion",
        [rsi("rsi_7", 7)],
        "rsi_7 <= 20", "rsi_7 >= 50", 1.3, 2.0,
        "Momentum-only entry via a fast 7-period RSI extreme, no price-band requirement.",
    ),
    spec(
        "mr_010_bb_volume_climax", "BB Reversion + Volume Climax", "mean_reversion",
        [bb("bb", 20, 2.0), {"name": "volume_sma_ratio", "alias": "vol_ratio", "params": {"period": 20}}],
        "close <= bb_lower and vol_ratio > 1.5", "close >= bb_middle", 1.5, 2.5,
        "Band touch plus a volume spike, betting on capitulation-driven reversals.",
    ),
    spec(
        "mr_011_percent_b_rsi_combo", "%B + RSI Combo", "mean_reversion",
        [{"name": "percent_b", "alias": "pct_b", "params": {"period": 20, "num_std": 2.0}}, rsi("rsi_14", 14)],
        "pct_b <= 0.1 and rsi_14 <= 35", "pct_b >= 0.5 or rsi_14 >= 55", 1.5, 2.5,
        "%B and RSI both required to confirm the same oversold state.",
    ),
    spec(
        "mr_012_vwap_bb_confluence", "VWAP + Bollinger Confluence", "mean_reversion",
        [{"name": "rolling_vwap", "alias": "vwap", "params": {"period": 20}}, bb("bb", 20, 2.0)],
        "close < vwap and close <= bb_lower", "close > vwap and close >= bb_middle", 1.5, 2.5,
        "Two independent mean levels (VWAP, Bollinger middle) must both be breached.",
    ),
    spec(
        "mr_013_zscore_short_window", "Z-Score Reversion (14-bar, tight)", "mean_reversion",
        [{"name": "zscore", "alias": "z", "params": {"period": 14}}],
        "z <= -1.8", "z >= 0.3", 1.3, 2.2,
        "Shorter lookback z-score for a more reactive statistical entry, exits on overshoot past the mean.",
    ),
    spec(
        "mr_014_bb_stoch_reversion", "BB + Stochastic Reversion", "mean_reversion",
        [bb("bb", 20, 2.0), {"name": "stochastic", "alias": "stoch", "params": {"k_period": 14, "d_period": 3}}],
        "close <= bb_lower and stoch_k <= 20", "close >= bb_middle or stoch_k >= 50", 1.5, 2.5,
        "Band touch confirmed by an oversold stochastic reading instead of RSI.",
    ),
]

# ============================== breakout_volatility (12) ==============================
SPECS += [
    spec(
        "bo_001_donchian20_breakout", "Donchian 20 Breakout", "breakout_volatility",
        [{"name": "donchian_channels", "alias": "dc", "params": {"period": 20}}],
        "close > donchian_upper", "False", 1.5, 3.0,
        "Classic 20-bar channel breakout (Turtle-style, shorter window).",
    ),
    spec(
        "bo_002_donchian10_breakout", "Donchian 10 Breakout (fast)", "breakout_volatility",
        [{"name": "donchian_channels", "alias": "dc", "params": {"period": 10}}],
        "close > donchian_upper", "False", 1.3, 2.5,
        "Shorter 10-bar channel for more frequent breakout signals.",
    ),
    spec(
        "bo_003_donchian55_breakout", "Donchian 55 Breakout (slow)", "breakout_volatility",
        [{"name": "donchian_channels", "alias": "dc", "params": {"period": 55}}],
        "close > donchian_upper", "False", 1.8, 3.5,
        "Classic 55-bar Turtle-system channel, fewer and larger breakout signals.",
    ),
    spec(
        "bo_004_keltner_breakout", "Keltner Channel Breakout", "breakout_volatility",
        [{"name": "keltner_channels", "alias": "kc", "params": {"ema_period": 20, "atr_period": 10, "atr_mult": 2.0}}],
        "close > kc_upper", "close < kc_middle", 1.5, 2.5,
        "Volatility-normalized (ATR-based) channel breakout instead of a raw price channel.",
    ),
    spec(
        "bo_005_atr_range_breakout", "ATR Range Breakout", "breakout_volatility",
        [],
        "close > prev_close + 1.5 * _atr", "False", 1.5, 2.5,
        "A single bar moving more than 1.5x ATR from the prior close -- a raw volatility-expansion breakout.",
    ),
    spec(
        "bo_006_bb_squeeze_breakout", "Bollinger Squeeze Breakout", "breakout_volatility",
        [bb("bb", 20, 2.0)],
        "(bb_upper - bb_lower) / bb_middle < 0.02 and close > bb_upper",
        "False", 1.5, 2.8,
        "Requires a prior volatility contraction (narrow bands) before the breakout above the upper band.",
    ),
    spec(
        "bo_007_donchian20_volume_confirm", "Donchian 20 + Volume Confirmation", "breakout_volatility",
        [{"name": "donchian_channels", "alias": "dc", "params": {"period": 20}},
         {"name": "volume_sma_ratio", "alias": "vol_ratio", "params": {"period": 20}}],
        "close > donchian_upper and vol_ratio > 1.3", "False", 1.5, 3.0,
        "20-bar channel breakout that also requires above-average volume on the breakout bar.",
    ),
    spec(
        "bo_008_keltner_wide_breakout", "Wide Keltner Breakout (2.5x ATR)", "breakout_volatility",
        [{"name": "keltner_channels", "alias": "kc", "params": {"ema_period": 20, "atr_period": 10, "atr_mult": 2.5}}],
        "close > kc_upper", "close < kc_middle", 1.8, 3.0,
        "Wider Keltner multiple for a stronger, less frequent breakout signal.",
    ),
    spec(
        "bo_009_donchian_adx_confirm", "Donchian 20 + ADX Confirmation", "breakout_volatility",
        [{"name": "donchian_channels", "alias": "dc", "params": {"period": 20}},
         {"name": "adx", "alias": "adx", "params": {"period": 14}}],
        "close > donchian_upper and adx >= 20", "False", 1.5, 3.0,
        "Channel breakout that also requires ADX>=20, avoiding breakouts in a directionless market.",
    ),
    spec(
        "bo_010_double_breakout_confluence", "Donchian + Keltner Double Breakout", "breakout_volatility",
        [{"name": "donchian_channels", "alias": "dc", "params": {"period": 20}},
         {"name": "keltner_channels", "alias": "kc", "params": {"ema_period": 20, "atr_period": 10, "atr_mult": 2.0}}],
        "close > donchian_upper and close > kc_upper", "False", 1.6, 3.0,
        "Requires both a price-channel breakout and a volatility-channel breakout to agree.",
    ),
    spec(
        "bo_011_wide_range_breakout", "Wide-Range Bar Breakout", "breakout_volatility",
        [{"name": "donchian_channels", "alias": "dc", "params": {"period": 10}}],
        "(high - low) > 1.5 * _atr and close > donchian_upper", "False", 1.5, 2.8,
        "Requires today's own bar to be unusually wide (range expansion) in addition to the channel breakout.",
    ),
    spec(
        "bo_012_keltner_donchian_tight_confluence", "Keltner + Donchian10 Tight Confluence", "breakout_volatility",
        [{"name": "donchian_channels", "alias": "dc", "params": {"period": 10}},
         {"name": "keltner_channels", "alias": "kc", "params": {"ema_period": 20, "atr_period": 10, "atr_mult": 1.5}}],
        "close > donchian_upper and close > kc_upper", "False", 1.4, 2.6,
        "A tighter (1.5x ATR) Keltner combined with a fast 10-bar Donchian, for more frequent confluence signals.",
    ),
]

# ============================== momentum_oscillator (13) ==============================
SPECS += [
    spec(
        "mo_001_rsi_cross_50", "RSI Crosses Above 50", "momentum_oscillator",
        [rsi("rsi_14", 14), cross_above("rsi_cross_up", "rsi_14", 50)],
        "rsi_cross_up", "rsi_14 < 45", 1.3, 2.0,
        "RSI turning positive (crossing its own 50 midline) rather than an oversold-extreme entry.",
    ),
    spec(
        "mo_002_stoch_cross_20", "Stochastic %K Crosses Above 20", "momentum_oscillator",
        [{"name": "stochastic", "alias": "stoch", "params": {"k_period": 14, "d_period": 3}},
         cross_above("stoch_cross_up", "stoch_k", 20)],
        "stoch_cross_up", "stoch_k > 80", 1.3, 2.0,
        "Stochastic %K leaving the oversold zone from below 20.",
    ),
    spec(
        "mo_003_stoch_kd_cross", "Stochastic %K/%D Cross", "momentum_oscillator",
        [{"name": "stochastic", "alias": "stoch", "params": {"k_period": 14, "d_period": 3}},
         cross_above("stoch_kd_cross", "stoch_k", "stoch_d")],
        "stoch_kd_cross and stoch_k < 50", "stoch_k > 80", 1.3, 2.0,
        "Classic %K crossing above %D, restricted to the lower half of the range (early-momentum entries).",
    ),
    spec(
        "mo_004_roc_positive_cross", "Rate of Change Crosses Above Zero", "momentum_oscillator",
        [{"name": "roc", "alias": "roc_12", "params": {"period": 12}},
         cross_above("roc_cross_up", "roc_12", 0)],
        "roc_cross_up", "roc_12 < 0", 1.3, 2.0,
        "12-bar rate of change turning positive.",
    ),
    spec(
        "mo_005_williams_r_reversal", "Williams %R Reversal", "momentum_oscillator",
        [{"name": "williams_r", "alias": "wr", "params": {"period": 14}},
         cross_above("wr_cross_up", "wr", -80)],
        "wr_cross_up", "wr > -20", 1.3, 2.0,
        "Williams %R crossing back above -80 (leaving the oversold extreme).",
    ),
    spec(
        "mo_006_cci_zero_cross", "CCI Crosses Above Zero", "momentum_oscillator",
        [{"name": "cci", "alias": "cci", "params": {"period": 20}},
         cross_above("cci_cross_up", "cci", 0)],
        "cci_cross_up", "cci < -50", 1.3, 2.0,
        "Commodity Channel Index turning positive.",
    ),
    spec(
        "mo_007_cci_extreme_reversal", "CCI Extreme Reversal", "momentum_oscillator",
        [{"name": "cci", "alias": "cci", "params": {"period": 20}},
         cross_above("cci_cross_up", "cci", -100)],
        "cci_cross_up", "cci > 100", 1.4, 2.2,
        "CCI recovering from an extreme oversold reading below -100.",
    ),
    spec(
        "mo_008_rsi_stoch_combo", "RSI + Stochastic Momentum Combo", "momentum_oscillator",
        [rsi("rsi_14", 14), {"name": "stochastic", "alias": "stoch", "params": {"k_period": 14, "d_period": 3}}],
        "rsi_14 > 50 and stoch_k > stoch_d", "rsi_14 < 45", 1.3, 2.0,
        "Two independent momentum oscillators (RSI, Stochastic) must both confirm.",
    ),
    spec(
        "mo_009_roc_rsi_combo", "ROC + RSI Not-Yet-Overbought Combo", "momentum_oscillator",
        [{"name": "roc", "alias": "roc_12", "params": {"period": 12}}, rsi("rsi_14", 14)],
        "roc_12 > 0 and rsi_14 >= 45 and rsi_14 <= 65", "roc_12 < 0", 1.3, 2.0,
        "Positive momentum while RSI is in a neutral band, avoiding entries already near overbought.",
    ),
    spec(
        "mo_010_williams_cci_combo", "Williams %R + CCI Combo", "momentum_oscillator",
        [{"name": "williams_r", "alias": "wr", "params": {"period": 14}},
         {"name": "cci", "alias": "cci", "params": {"period": 20}},
         cross_above("wr_cross_up", "wr", -80)],
        "wr_cross_up and cci < -50", "wr > -20", 1.4, 2.2,
        "Williams %R reversal while CCI is still in oversold territory (early-stage recovery).",
    ),
    spec(
        "mo_011_stoch_slow_21", "Slow Stochastic (21-period)", "momentum_oscillator",
        [{"name": "stochastic", "alias": "stoch", "params": {"k_period": 21, "d_period": 5}},
         cross_above("stoch_cross_up", "stoch_k", 20)],
        "stoch_cross_up", "stoch_k > 80", 1.4, 2.2,
        "Longer-period stochastic for a smoother, less noisy signal.",
    ),
    spec(
        "mo_012_rsi_fast_7_cross", "Fast RSI(7) Crosses 50", "momentum_oscillator",
        [rsi("rsi_7", 7), cross_above("rsi_cross_up", "rsi_7", 50)],
        "rsi_cross_up", "rsi_7 < 40", 1.2, 1.8,
        "Faster 7-period RSI for quicker momentum-turn signals.",
    ),
    spec(
        "mo_013_triple_momentum_confluence", "Triple Momentum Confluence", "momentum_oscillator",
        [rsi("rsi_14", 14), {"name": "stochastic", "alias": "stoch", "params": {"k_period": 14, "d_period": 3}},
         {"name": "roc", "alias": "roc_12", "params": {"period": 12}}],
        "rsi_14 > 50 and stoch_k > stoch_d and roc_12 > 0", "rsi_14 < 45", 1.4, 2.2,
        "Three independent momentum measures (RSI, Stochastic, ROC) all agreeing.",
    ),
]

# ============================== volume_orderflow (11) ==============================
def obv() -> dict:
    return {"name": "obv", "alias": "obv", "params": {}}


def vol_ratio(period: int = 20) -> dict:
    return {"name": "volume_sma_ratio", "alias": "vol_ratio", "params": {"period": period}}


SPECS += [
    spec(
        "vo_001_obv_sma_cross", "OBV Crosses Above its SMA", "volume_orderflow",
        [obv(), {"name": "sma", "alias": "obv_sma", "params": {"period": 20, "source": "obv"}},
         cross_above("obv_cross_up", "obv", "obv_sma")],
        "obv_cross_up", "False", 1.4, 2.2,
        "On-Balance Volume crossing above its own 20-bar moving average -- a volume-trend turn.",
    ),
    spec(
        "vo_002_vwap_price_cross", "Price Crosses Above VWAP", "volume_orderflow",
        [{"name": "rolling_vwap", "alias": "vwap", "params": {"period": 20}},
         cross_above("vwap_cross_up", "close", "vwap")],
        "vwap_cross_up", "close < vwap", 1.3, 2.0,
        "Close price crossing above its rolling VWAP.",
    ),
    spec(
        "vo_003_volume_spike_up_bar", "Volume Spike on an Up Bar", "volume_orderflow",
        [vol_ratio(20)],
        "vol_ratio > 2.0 and close > open", "False", 1.5, 2.5,
        "A bar with 2x average volume that also closes higher than it opened.",
    ),
    spec(
        "vo_004_obv_rsi_combo", "OBV Trend + RSI Combo", "volume_orderflow",
        [obv(), {"name": "sma", "alias": "obv_sma", "params": {"period": 10, "source": "obv"}}, rsi("rsi_14", 14)],
        "obv > obv_sma and rsi_14 > 50", "rsi_14 < 45", 1.3, 2.0,
        "OBV above its short-term average, confirmed by RSI momentum.",
    ),
    spec(
        "vo_005_vwap_dip_volume", "VWAP Dip on Heavy Volume", "volume_orderflow",
        [{"name": "rolling_vwap", "alias": "vwap", "params": {"period": 20}}, vol_ratio(20)],
        "close < vwap * 0.995 and vol_ratio > 1.3", "close > vwap", 1.4, 2.2,
        "Price dipping below VWAP on above-average volume -- a volume-driven dip-buy.",
    ),
    spec(
        "vo_006_volume_zscore_spike", "Volume Z-Score Spike", "volume_orderflow",
        [{"name": "volume_zscore", "alias": "vol_z", "params": {"period": 20}}],
        "vol_z > 2.0 and close > open", "False", 1.5, 2.5,
        "Statistically extreme volume (z-score > 2) on an up bar.",
    ),
    spec(
        "vo_007_obv_breakout_confirm", "OBV Breakout Confirmation (30-bar)", "volume_orderflow",
        [obv(), {"name": "sma", "alias": "obv_sma", "params": {"period": 30, "source": "obv"}},
         {"name": "rolling_vwap", "alias": "vwap", "params": {"period": 20}},
         cross_above("obv_cross_up", "obv", "obv_sma")],
        "obv_cross_up and close > vwap", "False", 1.5, 2.4,
        "OBV trend turn (longer 30-bar average) combined with price above VWAP.",
    ),
    spec(
        "vo_008_low_volume_pullback", "Low-Volume Pullback in Uptrend", "volume_orderflow",
        [ema("ema_trend", 20), vol_ratio(20), rsi("rsi_14", 14)],
        "close > ema_trend and vol_ratio < 0.8 and rsi_14 >= 40 and rsi_14 <= 55",
        "close < ema_trend", 1.3, 2.0,
        "A quiet, low-volume pullback within an established uptrend -- a continuation entry, not a breakout.",
    ),
    spec(
        "vo_009_vwap_obv_confluence", "VWAP + OBV Confluence", "volume_orderflow",
        [{"name": "rolling_vwap", "alias": "vwap", "params": {"period": 20}}, obv(),
         {"name": "sma", "alias": "obv_sma", "params": {"period": 20, "source": "obv"}}],
        "close > vwap and obv > obv_sma", "close < vwap", 1.4, 2.2,
        "Two independent volume-based signals (VWAP position, OBV trend) both confirming.",
    ),
    spec(
        "vo_010_volume_climax_reversal", "Volume Climax Reversal", "volume_orderflow",
        [{"name": "volume_zscore", "alias": "vol_z", "params": {"period": 20}},
         {"name": "rolling_vwap", "alias": "vwap", "params": {"period": 20}}],
        "vol_z > 2.5 and close < open and close < vwap", "close > vwap", 1.6, 2.5,
        "Contrarian entry: an extreme-volume down bar below VWAP, betting on capitulation exhaustion.",
    ),
    spec(
        "vo_011_accumulation_obv_slope", "Steady Accumulation (OBV + Volume)", "volume_orderflow",
        [obv(), {"name": "sma", "alias": "obv_sma", "params": {"period": 30, "source": "obv"}}, vol_ratio(20)],
        "obv > obv_sma and vol_ratio > 1.1", "obv < obv_sma", 1.4, 2.2,
        "OBV above its longer average with modestly elevated volume -- steady accumulation rather than a spike.",
    ),
]

# ============================== multi_indicator_confluence (12) ==============================
SPECS += [
    spec(
        "mi_001_ema_rsi_volume", "EMA Cross + RSI + Volume", "multi_indicator_confluence",
        [ema("ema_fast", 9), ema("ema_slow", 21), cross_above("ema_cross_up", "ema_fast", "ema_slow"),
         rsi("rsi_14", 14), vol_ratio(20)],
        "ema_cross_up and rsi_14 >= 50 and rsi_14 <= 70 and vol_ratio > 1.0", "False", 1.0, 1.5,
        "The bot #1 reference pattern: trend cross + momentum band + volume confirmation, as a catalog entry.",
    ),
    spec(
        "mi_002_ema_rsi_adx", "EMA Cross + RSI + ADX", "multi_indicator_confluence",
        [ema("ema_fast", 9), ema("ema_slow", 21), cross_above("ema_cross_up", "ema_fast", "ema_slow"),
         rsi("rsi_14", 14), {"name": "adx", "alias": "adx", "params": {"period": 14}}],
        "ema_cross_up and rsi_14 >= 50 and rsi_14 <= 70 and adx >= 20", "False", 1.2, 1.8,
        "Trend cross + momentum band + trend-strength filter.",
    ),
    spec(
        "mi_003_macd_rsi_volume", "MACD Cross + RSI + Volume", "multi_indicator_confluence",
        [{"name": "macd", "alias": "macd", "params": {"fast": 12, "slow": 26, "signal": 9}},
         cross_above("macd_cross_up", "macd_line", "macd_signal"), rsi("rsi_14", 14), vol_ratio(20)],
        "macd_cross_up and rsi_14 > 50 and vol_ratio > 1.1", "False", 1.2, 1.8,
        "MACD signal cross confirmed by RSI momentum and above-average volume.",
    ),
    spec(
        "mi_004_bb_rsi_volume_mr", "BB + RSI + Volume Mean-Reversion", "multi_indicator_confluence",
        [bb("bb", 20, 2.0), rsi("rsi_14", 14), vol_ratio(20)],
        "close <= bb_lower and rsi_14 <= 30 and vol_ratio > 1.3", "close >= bb_middle or rsi_14 >= 55", 1.5, 2.5,
        "Full mean-reversion confluence: band touch, RSI oversold, and a volume spike, all three required.",
    ),
    spec(
        "mi_005_triple_ma_rsi", "Triple MA Alignment + RSI", "multi_indicator_confluence",
        [sma("sma20", 20), sma("sma50", 50), rsi("rsi_14", 14)],
        "close > sma20 and sma20 > sma50 and rsi_14 >= 50 and rsi_14 <= 65", "close < sma20", 1.3, 2.0,
        "MA alignment filter combined with a momentum band, not just a bare crossover.",
    ),
    spec(
        "mi_006_donchian_adx_volume", "Donchian Breakout + ADX + Volume", "multi_indicator_confluence",
        [{"name": "donchian_channels", "alias": "dc", "params": {"period": 20}},
         {"name": "adx", "alias": "adx", "params": {"period": 14}}, vol_ratio(20)],
        "close > donchian_upper and adx >= 20 and vol_ratio > 1.2", "False", 1.6, 3.0,
        "Channel breakout confirmed by both trend strength and volume.",
    ),
    spec(
        "mi_007_stoch_macd_confirm", "Stochastic + MACD Dual Cross", "multi_indicator_confluence",
        [{"name": "stochastic", "alias": "stoch", "params": {"k_period": 14, "d_period": 3}},
         {"name": "macd", "alias": "macd", "params": {"fast": 12, "slow": 26, "signal": 9}}],
        "stoch_k > stoch_d and macd_line > macd_signal", "stoch_k > 80", 1.3, 2.0,
        "Two independent crossing systems (Stochastic %K/%D, MACD/signal) both bullish simultaneously.",
    ),
    spec(
        "mi_008_vwap_rsi_adx", "VWAP + RSI + ADX Confluence", "multi_indicator_confluence",
        [{"name": "rolling_vwap", "alias": "vwap", "params": {"period": 20}}, rsi("rsi_14", 14),
         {"name": "adx", "alias": "adx", "params": {"period": 14}}],
        "close > vwap and rsi_14 > 50 and adx >= 15", "close < vwap", 1.3, 2.0,
        "VWAP position, momentum, and a mild trend-strength filter combined.",
    ),
    spec(
        "mi_009_cci_ema_volume", "CCI Reversal + EMA Trend + Volume", "multi_indicator_confluence",
        [{"name": "cci", "alias": "cci", "params": {"period": 20}}, ema("ema_trend", 50), vol_ratio(20),
         cross_above("cci_cross_up", "cci", -100)],
        "cci_cross_up and close > ema_trend and vol_ratio > 1.0", "cci > 150", 1.4, 2.2,
        "Momentum reversal (CCI) only taken in the direction of the longer-term EMA trend, with volume.",
    ),
    spec(
        "mi_010_bb_stoch_adx_mr", "BB + Stochastic + ADX Mean-Reversion", "multi_indicator_confluence",
        [bb("bb", 20, 2.0), {"name": "stochastic", "alias": "stoch", "params": {"k_period": 14, "d_period": 3}},
         {"name": "adx", "alias": "adx", "params": {"period": 14}}],
        "close <= bb_lower and stoch_k <= 20 and adx <= 20", "close >= bb_middle or stoch_k >= 50", 1.5, 2.5,
        "Full mean-reversion confluence with a regime filter: band touch, oversold stochastic, non-trending ADX.",
    ),
    spec(
        "mi_011_keltner_rsi_volume", "Keltner Breakout + RSI + Volume", "multi_indicator_confluence",
        [{"name": "keltner_channels", "alias": "kc", "params": {"ema_period": 20, "atr_period": 10, "atr_mult": 2.0}},
         rsi("rsi_14", 14), vol_ratio(20)],
        "close > kc_upper and rsi_14 > 55 and vol_ratio > 1.3", "close < kc_middle", 1.5, 2.5,
        "Volatility-channel breakout confirmed by both momentum and volume.",
    ),
    spec(
        "mi_012_five_factor_confluence", "Four-Factor High-Conviction Confluence", "multi_indicator_confluence",
        [ema("ema_fast", 9), ema("ema_slow", 21), cross_above("ema_cross_up", "ema_fast", "ema_slow"),
         rsi("rsi_14", 14), {"name": "adx", "alias": "adx", "params": {"period": 14}}, vol_ratio(20)],
        "ema_cross_up and rsi_14 >= 50 and rsi_14 <= 68 and adx >= 18 and vol_ratio > 1.1",
        "False", 1.2, 2.0,
        "The \"kitchen sink\" variant: trend cross, momentum band, trend strength, and volume all required together.",
    ),
]

# ============================== candlestick_pattern (13) ==============================
SPECS += [
    spec(
        "cp_001_bullish_engulfing", "Bullish Engulfing", "candlestick_pattern",
        [],
        "close > open and prev_close < prev_open and close > prev_open and open < prev_close",
        "False", 1.3, 2.0,
        "Classic two-bar bullish engulfing pattern using only raw OHLC (no indicators needed).",
    ),
    spec(
        "cp_002_hammer", "Hammer / Pin Bar", "candlestick_pattern",
        [],
        "(close - low) > 0.6 * (high - low) and (open - low) > 0.6 * (high - low) and close >= open",
        "False", 1.3, 2.0,
        "Small body near the top of the bar's range with a long lower wick -- a single-bar rejection pattern.",
    ),
    spec(
        "cp_003_bullish_engulfing_rsi", "Bullish Engulfing at Pullback (RSI filter)", "candlestick_pattern",
        [rsi("rsi_14", 14)],
        "close > open and prev_close < prev_open and close > prev_open and open < prev_close and rsi_14 <= 40",
        "rsi_14 >= 60", 1.3, 2.0,
        "Engulfing pattern restricted to a pullback context (RSI<=40) rather than any location.",
    ),
    spec(
        "cp_004_inside_bar_breakout", "Inside Bar Breakout", "candlestick_pattern",
        [],
        "prev_high < prev2_high and prev_low > prev2_low and close > prev2_high",
        "False", 1.3, 2.0,
        "Three-bar pattern: an inside bar followed by a breakout above the \"mother bar\" high.",
    ),
    spec(
        "cp_005_pin_bar_trend_filter", "Pin Bar Rejection in Uptrend", "candlestick_pattern",
        [ema("ema_trend", 20)],
        "(close - low) > 0.6 * (high - low) and close > open and close > ema_trend",
        "close < ema_trend", 1.3, 2.0,
        "Same rejection-wick pattern as the plain hammer, but only taken above the trend EMA.",
    ),
    spec(
        "cp_006_three_bar_higher_lows", "Three-Bar Higher Lows", "candlestick_pattern",
        [],
        "low > prev_low and prev_low > prev2_low and close > open",
        "False", 1.2, 1.8,
        "A simple ascending-lows continuation pattern over three bars.",
    ),
    spec(
        "cp_007_engulfing_volume", "Bullish Engulfing + Volume", "candlestick_pattern",
        [vol_ratio(20)],
        "close > open and prev_close < prev_open and close > prev_open and open < prev_close and vol_ratio > 1.3",
        "False", 1.3, 2.0,
        "Engulfing pattern that also requires above-average volume on the engulfing bar.",
    ),
    spec(
        "cp_008_doji_reversal", "Doji at Oversold RSI", "candlestick_pattern",
        [rsi("rsi_14", 14)],
        "(high - low) > 0 and (close - open) < 0.15 * (high - low) and (open - close) < 0.15 * (high - low) and rsi_14 <= 35",
        "rsi_14 >= 55", 1.3, 2.0,
        "A small-bodied (indecision) bar occurring while RSI is oversold.",
    ),
    spec(
        "cp_009_gap_up_continuation", "Gap-Up Continuation", "candlestick_pattern",
        [],
        "open > prev_close and close > open",
        "False", 1.4, 2.2,
        "A bar that opens above the prior close and then continues higher through the bar.",
    ),
    spec(
        "cp_010_engulfing_adx_filter", "Engulfing in Early Trend (low ADX)", "candlestick_pattern",
        [{"name": "adx", "alias": "adx", "params": {"period": 14}}],
        "close > open and prev_close < prev_open and close > prev_open and open < prev_close and adx <= 25",
        "adx >= 40", 1.3, 2.0,
        "Engulfing pattern restricted to a not-yet-strongly-trending regime, catching earlier reversals.",
    ),
    spec(
        "cp_011_hammer_volume_confirm", "Hammer + Volume Confirmation", "candlestick_pattern",
        [vol_ratio(20)],
        "(close - low) > 0.6 * (high - low) and (open - low) > 0.6 * (high - low) and close >= open and vol_ratio > 1.2",
        "False", 1.3, 2.0,
        "Hammer/pin-bar pattern with an added volume-confirmation requirement.",
    ),
    spec(
        "cp_012_three_bar_higher_lows_rsi", "Higher Lows + Neutral RSI", "candlestick_pattern",
        [rsi("rsi_14", 14)],
        "low > prev_low and prev_low > prev2_low and close > open and rsi_14 >= 45 and rsi_14 <= 60",
        "rsi_14 >= 70", 1.2, 1.8,
        "Ascending-lows pattern restricted to a neutral (not-yet-overbought) RSI band.",
    ),
    spec(
        "cp_013_inside_bar_breakout_volume", "Inside Bar Breakout + Volume", "candlestick_pattern",
        [vol_ratio(20)],
        "prev_high < prev2_high and prev_low > prev2_low and close > prev2_high and vol_ratio > 1.3",
        "False", 1.3, 2.0,
        "Inside-bar breakout pattern that also requires a volume spike on the breakout bar.",
    ),
]

# ============================== statistical_zscore (11) ==============================
SPECS += [
    spec(
        "sz_001_zscore_reversion_20", "Z-Score Reversion (20-bar)", "statistical_zscore",
        [{"name": "zscore", "alias": "z", "params": {"period": 20}}],
        "z <= -2.0", "z >= 0", 1.5, 2.5,
        "Baseline statistical mean-reversion entry: 2 standard deviations below the 20-bar mean.",
    ),
    spec(
        "sz_002_zscore_reversion_10", "Z-Score Reversion (10-bar, reactive)", "statistical_zscore",
        [{"name": "zscore", "alias": "z", "params": {"period": 10}}],
        "z <= -1.8", "z >= 0.2", 1.3, 2.2,
        "Shorter lookback for a more reactive, higher-frequency statistical entry.",
    ),
    spec(
        "sz_003_zscore_reversion_30", "Z-Score Reversion (30-bar, strict)", "statistical_zscore",
        [{"name": "zscore", "alias": "z", "params": {"period": 30}}],
        "z <= -2.2", "z >= -0.2", 1.6, 2.8,
        "Longer lookback and a stricter threshold for rarer, higher-conviction deviations.",
    ),
    spec(
        "sz_004_percent_b_low", "%B Extreme Low", "statistical_zscore",
        [{"name": "percent_b", "alias": "pct_b", "params": {"period": 20, "num_std": 2.0}}],
        "pct_b <= 0.02", "pct_b >= 0.5", 1.5, 2.5,
        "%B expressed as a near-zero extreme rather than a raw band-touch comparison.",
    ),
    spec(
        "sz_005_zscore_volume_confirm", "Z-Score + Volume Confirmation", "statistical_zscore",
        [{"name": "zscore", "alias": "z", "params": {"period": 20}}, vol_ratio(20)],
        "z <= -2.0 and vol_ratio > 1.3", "z >= 0", 1.5, 2.5,
        "Statistical deviation entry that also requires a volume spike.",
    ),
    spec(
        "sz_006_zscore_rsi_combo", "Z-Score + RSI Combo", "statistical_zscore",
        [{"name": "zscore", "alias": "z", "params": {"period": 20}}, rsi("rsi_14", 14)],
        "z <= -1.5 and rsi_14 <= 35", "z >= 0 or rsi_14 >= 55", 1.4, 2.4,
        "Statistical deviation confirmed by a classical momentum oscillator.",
    ),
    spec(
        "sz_007_spread_from_sma50", "Percent Spread from SMA50", "statistical_zscore",
        [sma("sma50", 50)],
        "(close - sma50) / sma50 <= -0.02", "close >= sma50", 1.4, 2.3,
        "Mean reversion via a raw percentage spread from a 50-bar SMA rather than a z-score.",
    ),
    spec(
        "sz_008_zscore_extreme_adx_filter", "Extreme Z-Score + Non-Trending Filter", "statistical_zscore",
        [{"name": "zscore", "alias": "z", "params": {"period": 20}},
         {"name": "adx", "alias": "adx", "params": {"period": 14}}],
        "z <= -2.5 and adx <= 20", "z >= 0", 1.6, 2.8,
        "A very extreme deviation combined with a regime filter to avoid fading an established trend.",
    ),
    spec(
        "sz_009_percent_b_zscore_combo", "%B + Z-Score Confluence", "statistical_zscore",
        [{"name": "percent_b", "alias": "pct_b", "params": {"period": 20, "num_std": 2.0}},
         {"name": "zscore", "alias": "z", "params": {"period": 20}}],
        "pct_b <= 0.05 and z <= -1.8", "pct_b >= 0.5", 1.5, 2.5,
        "Two independent statistical measures of the same deviation must agree.",
    ),
    spec(
        "sz_010_spread_from_ema30", "Percent Spread from EMA30", "statistical_zscore",
        [ema("ema30", 30)],
        "(close - ema30) / ema30 <= -0.015", "close >= ema30", 1.4, 2.3,
        "Percentage-spread mean reversion using an EMA instead of an SMA as the reference level.",
    ),
    spec(
        "sz_011_zscore_overshoot_exit", "Z-Score Reversion, Overshoot Exit", "statistical_zscore",
        [{"name": "zscore", "alias": "z", "params": {"period": 14}}],
        "z <= -1.6", "z >= 0.5", 1.3, 2.2,
        "Shorter-window z-score entry that holds until price overshoots back past the mean, not just reaches it.",
    ),
]


def main() -> None:
    assert len(SPECS) == 100, f"expected 100 specs, got {len(SPECS)}"

    by_category: dict[str, int] = {}
    for raw in SPECS:
        by_category[raw["category"]] = by_category.get(raw["category"], 0) + 1
    print("Category counts:", by_category)

    for raw in SPECS:
        # Validate (schema shape + entry/exit rule syntax) before writing.
        from botfarm.catalog.schema import spec_from_dict
        parsed = spec_from_dict(raw, source=raw["id"])
        compile_check(parsed.entry_rule)
        compile_check(parsed.exit_rule)

        out_dir = SPECS_DIR / raw["category"]
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{raw['id']}.yaml"
        with open(out_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(raw, f, sort_keys=False, default_flow_style=False)

    print(f"Wrote {len(SPECS)} strategy specs to {SPECS_DIR}")


if __name__ == "__main__":
    main()
