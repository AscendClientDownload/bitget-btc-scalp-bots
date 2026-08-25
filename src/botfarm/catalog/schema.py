"""Declarative strategy spec: schema, YAML loading, and validation.

A StrategySpec is a data-only description of a strategy (indicators, entry/
exit rules as restricted expression strings, stop/target as ATR multiples).
strategy/generic.py's DeclarativeStrategy interprets a spec at runtime; this
module only defines the shape and validates it -- no execution logic here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

VALID_CATEGORIES = {
    "trend_following",
    "mean_reversion",
    "breakout_volatility",
    "momentum_oscillator",
    "volume_orderflow",
    "multi_indicator_confluence",
    "candlestick_pattern",
    "statistical_zscore",
}
VALID_TIMEFRAMES = {"1min", "5min"}

SPECS_DIR = Path(__file__).resolve().parent / "specs"


class SpecValidationError(ValueError):
    pass


@dataclass(frozen=True)
class IndicatorRef:
    name: str
    alias: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StrategySpec:
    id: str
    name: str
    category: str
    timeframe: str
    indicators: list[IndicatorRef]
    entry_side: str
    entry_rule: str
    exit_rule: str
    atr_period: int
    stop_loss_atr_mult: float
    take_profit_atr_mult: float
    max_holding_bars: int
    notes: str = ""


def spec_from_dict(data: dict, source: str = "<dict>") -> StrategySpec:
    def require(key: str) -> Any:
        if key not in data:
            raise SpecValidationError(f"{source}: missing required field {key!r}")
        return data[key]

    category = require("category")
    if category not in VALID_CATEGORIES:
        raise SpecValidationError(f"{source}: invalid category {category!r}")

    timeframe = require("timeframe")
    if timeframe not in VALID_TIMEFRAMES:
        raise SpecValidationError(f"{source}: invalid timeframe {timeframe!r}")

    entry = require("entry")
    if entry.get("side") != "long":
        raise SpecValidationError(f"{source}: only side='long' is supported (spot, no shorting)")

    indicators = [
        IndicatorRef(name=i["name"], alias=i["alias"], params=i.get("params", {}) or {})
        for i in data.get("indicators", [])
    ]

    spec = StrategySpec(
        id=require("id"),
        name=require("name"),
        category=category,
        timeframe=timeframe,
        indicators=indicators,
        entry_side="long",
        entry_rule=entry["rule"],
        exit_rule=require("exit")["rule"],
        atr_period=int(require("atr_period")),
        stop_loss_atr_mult=float(require("stop_loss_atr_mult")),
        take_profit_atr_mult=float(require("take_profit_atr_mult")),
        max_holding_bars=int(require("max_holding_bars")),
        notes=data.get("notes", ""),
    )

    if spec.stop_loss_atr_mult <= 0 or spec.take_profit_atr_mult <= 0:
        raise SpecValidationError(f"{source}: stop/target ATR multiples must be positive")
    if spec.max_holding_bars <= 0:
        raise SpecValidationError(f"{source}: max_holding_bars must be positive")
    if not spec.id or not spec.id.replace("_", "").isalnum():
        raise SpecValidationError(f"{source}: id {spec.id!r} must be alphanumeric/underscore")

    return spec


def load_spec(path: Path) -> StrategySpec:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return spec_from_dict(data, source=str(path))


def load_all_specs(specs_dir: Path = SPECS_DIR) -> list[StrategySpec]:
    paths = sorted(specs_dir.glob("*/*.yaml"))
    specs = [load_spec(p) for p in paths]

    ids = [s.id for s in specs]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise SpecValidationError(f"duplicate strategy ids found: {dupes}")

    return specs
