"""Read-only exchange client interface.

Deliberately has NO order-placement or cancellation methods anywhere in this
module or its implementations — this project does not place real trades.
A future authenticated subclass (if ever added) would be a separate,
explicit decision, not something bolted on here.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from botfarm.data.bitget_client import BitgetPublicClient


class ExchangeClient(ABC):
    @abstractmethod
    def get_recent_candles(self, symbol: str, granularity: str, limit: int) -> pd.DataFrame:
        ...

    @abstractmethod
    def get_last_price(self, symbol: str) -> float:
        ...


class BitgetPublicExchangeClient(ExchangeClient):
    def __init__(self, client: BitgetPublicClient | None = None):
        self._client = client or BitgetPublicClient()

    def get_recent_candles(self, symbol: str, granularity: str, limit: int) -> pd.DataFrame:
        candles = self._client.get_candles(symbol=symbol, granularity=granularity, limit=limit)
        return pd.DataFrame(
            [
                {
                    "ts_ms": c.ts_ms,
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close,
                    "base_volume": c.base_volume,
                }
                for c in candles
            ]
        )

    def get_last_price(self, symbol: str) -> float:
        df = self.get_recent_candles(symbol, "1min", limit=1)
        if df.empty:
            raise RuntimeError(f"no recent candle data returned for {symbol}")
        return float(df.iloc[-1]["close"])
