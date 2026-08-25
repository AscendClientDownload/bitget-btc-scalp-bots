"""Strategy interface shared by the bespoke bot #1 implementation and the
declarative (YAML-driven) strategies used for the rest of the catalog."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Literal

import pandas as pd

Timeframe = Literal["1min", "5min"]


class ExitReason(str, Enum):
    SIGNAL = "signal"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TIME_STOP = "time_stop"


@dataclass(frozen=True)
class IndicatorSpec:
    """Declares one indicator column a strategy needs computed on the OHLCV frame."""
    name: str
    column: str
    params: dict


@dataclass
class StrategyContext:
    """A read-only view of one bar (and its precomputed indicator columns)
    handed to a strategy's signal methods during backtesting/live evaluation."""
    df: pd.DataFrame
    i: int  # current bar index into df
    in_position: bool
    entry_price: float | None = None
    entry_bar: int | None = None

    @property
    def row(self) -> pd.Series:
        return self.df.iloc[self.i]

    @property
    def close(self) -> float:
        return float(self.row["close"])


class Strategy(ABC):
    """Base contract every bot strategy implements.

    entry_signal/exit_signal only make trade *decisions*; stop_loss/take_profit
    return absolute price levels checked intrabar by the backtest/live engine
    independently of exit_signal (so a stop can fire even if exit_signal() is
    False on that bar).
    """

    id: str
    timeframe: Timeframe
    max_holding_bars: int | None = None

    @abstractmethod
    def required_indicators(self) -> list[IndicatorSpec]:
        ...

    @abstractmethod
    def entry_signal(self, ctx: StrategyContext) -> bool:
        ...

    @abstractmethod
    def exit_signal(self, ctx: StrategyContext) -> bool:
        ...

    @abstractmethod
    def stop_loss(self, ctx: StrategyContext) -> float:
        """Absolute price. Called once at entry; the engine holds this fixed
        for the life of the trade (no trailing, to keep semantics simple and
        auditable)."""
        ...

    @abstractmethod
    def take_profit(self, ctx: StrategyContext) -> float:
        ...
