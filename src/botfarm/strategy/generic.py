"""DeclarativeStrategy: interprets a catalog.schema.StrategySpec at runtime
so any of the 100 catalog strategies can run through the same backtest/live
engine as the bespoke bot01 strategies, without bespoke code per strategy.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from botfarm.catalog.schema import IndicatorRef, StrategySpec
from botfarm.indicators import momentum, stats, trend, volatility, volume
from botfarm.strategy.base import IndicatorSpec, Strategy, StrategyContext
from botfarm.strategy.safe_eval import RuleEvalError, safe_eval
from botfarm.strategy.scalp_targets import dollar_scalp_levels


@dataclass(frozen=True)
class _IndicatorDef:
    fn: callable
    # Fixed OHLC(V) input column names, in the order `fn` expects them; None
    # means "single series" indicators that read a configurable `source`
    # column (default "close") instead.
    fixed_inputs: list[str] | None
    outputs: list[str]


INDICATOR_REGISTRY: dict[str, _IndicatorDef] = {
    "sma": _IndicatorDef(trend.sma, None, ["value"]),
    "ema": _IndicatorDef(trend.ema, None, ["value"]),
    "macd": _IndicatorDef(trend.macd, None, ["macd_line", "macd_signal", "macd_hist"]),
    "adx": _IndicatorDef(trend.adx, ["high", "low", "close"], ["adx", "plus_di", "minus_di"]),
    "rsi": _IndicatorDef(momentum.rsi, None, ["value"]),
    "stochastic": _IndicatorDef(momentum.stochastic, ["high", "low", "close"], ["stoch_k", "stoch_d"]),
    "roc": _IndicatorDef(momentum.roc, None, ["value"]),
    "williams_r": _IndicatorDef(momentum.williams_r, ["high", "low", "close"], ["value"]),
    "cci": _IndicatorDef(momentum.cci, ["high", "low", "close"], ["value"]),
    "atr": _IndicatorDef(volatility.atr, ["high", "low", "close"], ["value"]),
    "bollinger_bands": _IndicatorDef(volatility.bollinger_bands, None, ["bb_upper", "bb_middle", "bb_lower"]),
    "keltner_channels": _IndicatorDef(
        volatility.keltner_channels, ["high", "low", "close"], ["kc_upper", "kc_middle", "kc_lower"]
    ),
    "donchian_channels": _IndicatorDef(volatility.donchian_channels, ["high", "low"], ["donchian_upper", "donchian_lower"]),
    "obv": _IndicatorDef(volume.obv, ["close", "base_volume"], ["value"]),
    "rolling_vwap": _IndicatorDef(volume.rolling_vwap, ["high", "low", "close", "base_volume"], ["value"]),
    "volume_zscore": _IndicatorDef(volume.volume_zscore, ["base_volume"], ["value"]),
    "volume_sma_ratio": _IndicatorDef(volume.volume_sma_ratio, ["base_volume"], ["value"]),
    "zscore": _IndicatorDef(stats.zscore, None, ["value"]),
    "percent_b": _IndicatorDef(stats.percent_b, None, ["value"]),
}

# Auto-computed helper columns present on every declarative strategy's frame,
# regardless of what's in its indicators list -- covers the common "compare
# to the previous bar" pattern (candlestick rules, gap rules) and guarantees
# stop_loss()/take_profit() always have an ATR to use.
_AUTO_SHIFT_COLUMNS = {
    "prev_open": ("open", 1),
    "prev_high": ("high", 1),
    "prev_low": ("low", 1),
    "prev_close": ("close", 1),
    "prev_volume": ("base_volume", 1),
    "prev2_high": ("high", 2),
    "prev2_low": ("low", 2),
}


def _compute_one(ind: IndicatorRef, out: pd.DataFrame) -> dict[str, pd.Series]:
    if ind.name in ("cross_above", "cross_below"):
        a = out[ind.params["a"]] if isinstance(ind.params["a"], str) else float(ind.params["a"])
        b = out[ind.params["b"]] if isinstance(ind.params["b"], str) else float(ind.params["b"])
        a_prev = a.shift(1) if isinstance(a, pd.Series) else a
        b_prev = b.shift(1) if isinstance(b, pd.Series) else b
        if ind.name == "cross_above":
            series = (a > b) & (a_prev <= b_prev)
        else:
            series = (a < b) & (a_prev >= b_prev)
        return {ind.alias: series}

    defn = INDICATOR_REGISTRY.get(ind.name)
    if defn is None:
        raise RuleEvalError(f"unknown indicator {ind.name!r}")

    params = dict(ind.params)
    if defn.fixed_inputs is not None:
        args = [out[c] for c in defn.fixed_inputs]
    else:
        source = params.pop("source", "close")
        args = [out[source]]

    result = defn.fn(*args, **params)
    if len(defn.outputs) == 1:
        return {ind.alias: result}

    # Multi-output indicator: use its own fixed output names directly
    # (assumes at most one instance per spec, true across the catalog).
    return dict(zip(defn.outputs, result))


class DeclarativeStrategy(Strategy):
    def __init__(self, spec: StrategySpec):
        self.spec = spec
        self.id = spec.id
        self.timeframe = spec.timeframe
        self.max_holding_bars = spec.max_holding_bars

    def required_indicators(self) -> list[IndicatorSpec]:
        return [IndicatorSpec(i.name, i.alias, i.params) for i in self.spec.indicators]

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        for name, (src_col, periods) in _AUTO_SHIFT_COLUMNS.items():
            out[name] = out[src_col].shift(periods)

        for ind in self.spec.indicators:
            for col_name, series in _compute_one(ind, out).items():
                out[col_name] = series

        out["_atr"] = volatility.atr(out["high"], out["low"], out["close"], self.spec.atr_period)
        return out

    def _referenced_columns(self, df: pd.DataFrame) -> list[str]:
        base_ohlcv = {"open", "high", "low", "close", "base_volume", "quote_volume", "usdt_volume", "ts_ms"}
        return [c for c in df.columns if c not in base_ohlcv]

    def entry_signal(self, ctx: StrategyContext) -> bool:
        row = ctx.row
        cols = self._referenced_columns(ctx.df)
        if pd.isna(row[cols]).any():
            return False
        try:
            return safe_eval(self.spec.entry_rule, row)
        except RuleEvalError:
            return False

    def exit_signal(self, ctx: StrategyContext) -> bool:
        row = ctx.row
        cols = self._referenced_columns(ctx.df)
        if pd.isna(row[cols]).any():
            return False
        try:
            return safe_eval(self.spec.exit_rule, row)
        except RuleEvalError:
            return False

    def stop_loss(self, ctx: StrategyContext) -> float:
        stop, _ = dollar_scalp_levels(
            ctx.close, ctx.capital, self.spec.stop_loss_atr_mult, self.spec.take_profit_atr_mult
        )
        return stop

    def take_profit(self, ctx: StrategyContext) -> float:
        _, target = dollar_scalp_levels(
            ctx.close, ctx.capital, self.spec.stop_loss_atr_mult, self.spec.take_profit_atr_mult
        )
        return target
