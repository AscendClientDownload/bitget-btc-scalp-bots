"""Trading cost model: Bitget spot fees + a slippage assumption.

Bitget spot base rate is 0.1% maker / 0.1% taker (0.2% round trip). Scalp
entries/exits need fast fills, so both legs are modeled as taker. Slippage is
a simple fixed haircut against the trader, not a market-impact model — it's
an assumption, not a measurement, and is documented as such.
"""
from __future__ import annotations

from dataclasses import dataclass

DEFAULT_TAKER_FEE_RATE = 0.001  # 0.1% per side
DEFAULT_SLIPPAGE_BPS = 5  # 0.05% per side, against the trader


@dataclass(frozen=True)
class CostModel:
    fee_rate: float = DEFAULT_TAKER_FEE_RATE
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS

    def fill_price(self, quoted_price: float, side: str) -> float:
        """Apply slippage against the trader: buys fill higher, sells fill lower."""
        slippage_frac = self.slippage_bps / 10_000
        if side == "buy":
            return quoted_price * (1 + slippage_frac)
        if side == "sell":
            return quoted_price * (1 - slippage_frac)
        raise ValueError(f"side must be 'buy' or 'sell', got {side!r}")

    def fee(self, notional: float) -> float:
        return notional * self.fee_rate
