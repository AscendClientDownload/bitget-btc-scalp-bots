"""Simulated order execution for paper trading — applies the same CostModel
as the backtester so paper results are directly comparable to backtest
results. Never touches a real exchange account."""
from __future__ import annotations

import sqlite3

from botfarm.backtest.costs import CostModel
from botfarm.live import ledger


class PaperBroker:
    def __init__(self, cost_model: CostModel | None = None):
        self.cost_model = cost_model or CostModel()

    def open_position(
        self,
        conn: sqlite3.Connection,
        strategy_id: str,
        symbol: str,
        ts_ms: int,
        quote_price: float,
        notional: float,
        stop_loss: float,
        take_profit: float,
    ) -> tuple[int, float, float]:
        """Returns (trade_id, fill_price, shares)."""
        fill_price = self.cost_model.fill_price(quote_price, "buy")
        fee = self.cost_model.fee(notional)
        shares = (notional - fee) / fill_price
        trade_id = ledger.open_trade(
            conn,
            strategy_id=strategy_id,
            symbol=symbol,
            entry_ts_ms=ts_ms,
            entry_price=fill_price,
            shares=shares,
            stop_loss=stop_loss,
            take_profit=take_profit,
            fees_paid=fee,
            created_at_ms=ts_ms,
        )
        return trade_id, fill_price, shares

    def close_position(
        self,
        conn: sqlite3.Connection,
        trade_id: int,
        ts_ms: int,
        quote_price: float,
        shares: float,
        entry_price: float,
        exit_reason: str,
    ) -> float:
        """Returns realized return_pct."""
        fill_price = self.cost_model.fill_price(quote_price, "sell")
        gross_proceeds = shares * fill_price
        fee = self.cost_model.fee(gross_proceeds)
        net_proceeds = gross_proceeds - fee
        cost_basis = shares * entry_price
        return_pct = (net_proceeds - cost_basis) / cost_basis
        ledger.close_trade(
            conn,
            trade_id=trade_id,
            exit_ts_ms=ts_ms,
            exit_price=fill_price,
            exit_reason=exit_reason,
            exit_fees_paid=fee,
            return_pct=return_pct,
        )
        return return_pct
