"""Performance metrics computed from a BacktestResult, shared by the report
generator and by tests (so the report never hand-types a number)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from botfarm.backtest.engine import BacktestResult

BARS_PER_YEAR_5MIN = 365 * 24 * 12  # 5-minute bars in a year, for annualization


@dataclass
class Metrics:
    num_trades: int
    win_rate: float
    total_return_pct: float
    max_drawdown_pct: float
    sharpe: float
    sortino: float
    profit_factor: float
    avg_trade_return_pct: float
    avg_holding_bars: float
    expectancy_pct: float


def compute_metrics(result: BacktestResult, bars_per_year: int = BARS_PER_YEAR_5MIN) -> Metrics:
    trades = result.trades
    num_trades = len(trades)

    total_return_pct = (result.ending_capital - result.starting_capital) / result.starting_capital * 100

    if num_trades == 0:
        return Metrics(
            num_trades=0,
            win_rate=0.0,
            total_return_pct=total_return_pct,
            max_drawdown_pct=_max_drawdown_pct(result.equity_curve),
            sharpe=0.0,
            sortino=0.0,
            profit_factor=0.0,
            avg_trade_return_pct=0.0,
            avg_holding_bars=0.0,
            expectancy_pct=0.0,
        )

    returns = np.array([t.return_pct for t in trades])
    wins = returns[returns > 0]
    losses = returns[returns <= 0]

    win_rate = len(wins) / num_trades * 100
    gross_profit = wins.sum() if len(wins) else 0.0
    gross_loss = -losses.sum() if len(losses) else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0
    avg_trade_return_pct = returns.mean() * 100
    avg_holding_bars = float(np.mean([t.exit_bar - t.entry_bar for t in trades]))
    expectancy_pct = avg_trade_return_pct

    sharpe = _sharpe_ratio(result.equity_curve, bars_per_year)
    sortino = _sortino_ratio(result.equity_curve, bars_per_year)

    return Metrics(
        num_trades=num_trades,
        win_rate=win_rate,
        total_return_pct=total_return_pct,
        max_drawdown_pct=_max_drawdown_pct(result.equity_curve),
        sharpe=sharpe,
        sortino=sortino,
        profit_factor=profit_factor,
        avg_trade_return_pct=avg_trade_return_pct,
        avg_holding_bars=avg_holding_bars,
        expectancy_pct=expectancy_pct,
    )


def _bar_returns(equity_curve: pd.DataFrame) -> np.ndarray:
    if equity_curve.empty or len(equity_curve) < 2:
        return np.array([])
    equity = equity_curve["equity"].to_numpy()
    return equity[1:] / equity[:-1] - 1


def _max_drawdown_pct(equity_curve: pd.DataFrame) -> float:
    if equity_curve.empty:
        return 0.0
    equity = equity_curve["equity"].to_numpy()
    running_max = np.maximum.accumulate(equity)
    drawdown = (equity - running_max) / running_max
    return float(drawdown.min() * 100)


def _sharpe_ratio(equity_curve: pd.DataFrame, bars_per_year: int) -> float:
    returns = _bar_returns(equity_curve)
    if len(returns) < 2 or returns.std(ddof=0) == 0:
        return 0.0
    return float(returns.mean() / returns.std(ddof=0) * np.sqrt(bars_per_year))


def _sortino_ratio(equity_curve: pd.DataFrame, bars_per_year: int) -> float:
    returns = _bar_returns(equity_curve)
    downside = returns[returns < 0]
    if len(returns) < 2 or len(downside) == 0 or downside.std(ddof=0) == 0:
        return 0.0
    return float(returns.mean() / downside.std(ddof=0) * np.sqrt(bars_per_year))
