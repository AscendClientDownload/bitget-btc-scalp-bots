"""Fixed-dollar, fee-aware profit targets for scalp strategies.

Before this, every strategy's take_profit()/stop_loss() was a raw ATR
multiple of price -- which on BTC can mean a $5 target or a $500 target
purely depending on recent volatility, with no relation to what "scalping"
is supposed to mean (small, quick, frequent profits). That's not fixable by
just picking a smaller ATR multiple, because a tiny price-based target can
easily be smaller than round-trip trading costs, in which case the bot
would lose money on every single "winning" trade too.

This computes stop/target PRICE levels sized so that hitting the target
nets *exactly* a chosen dollar amount after fees and slippage (an exact
algebraic solve, not an approximation -- see test_scalp_targets.py, which
replays the real fill/fee sequence backtest.engine.py and
live.paper_broker.py actually use and checks the realized net P&L matches
to the cent) -- while keeping each strategy's own configured stop:target
RATIO (its designed risk:reward shape), just rescaled to a small, fee-aware
absolute distance.

Important, unavoidable arithmetic: each bot only ever deploys its own
capital (no leverage), so hitting even a small dollar target on an
expensive asset like BTC still requires a real (if small) percentage price
move -- roughly target/capital in percentage terms. Shrinking the dollar
target doesn't shrink the required move to zero; it's bounded below by fees.
"""
from __future__ import annotations

# Must track backtest.costs.CostModel's defaults and the live paper_broker's
# cost model exactly, so "net of fees" here is actually accurate, not a guess.
TAKER_FEE_RATE = 0.001  # 0.1% per side
SLIPPAGE_BPS = 5.0  # 0.05% per side
SLIPPAGE_FRACTION = SLIPPAGE_BPS / 10_000
ROUND_TRIP_FRICTION_FRACTION = 2 * TAKER_FEE_RATE + 2 * SLIPPAGE_FRACTION  # ~0.3% of notional, informational only

DEFAULT_TARGET_NET_DOLLARS = 3.0
FALLBACK_CAPITAL = 1_000.0  # used only if ctx.capital wasn't populated by the caller


def dollar_scalp_levels(
    entry_price: float,
    capital: float | None,
    stop_mult: float,
    target_mult: float,
    target_net_dollars: float = DEFAULT_TARGET_NET_DOLLARS,
) -> tuple[float, float]:
    """Returns (stop_loss_price, take_profit_price) for a long entry that
    deploys `capital` as notional, such that reaching the target price nets
    exactly target_net_dollars AFTER round-trip fees/slippage on that
    notional -- solved algebraically from the same buy-fee/shares/sell-fee
    sequence the backtest engine and live paper broker actually execute:

        fill_buy   = entry_price * (1 + slippage)
        entry_fee  = capital * fee_rate
        shares     = (capital - entry_fee) / fill_buy
        cost_basis = shares * fill_buy               # simplifies to capital*(1-fee_rate)
        fill_sell  = target_price * (1 - slippage)
        net_pnl    = shares*fill_sell*(1-fee_rate) - cost_basis

    Solving net_pnl == target_net_dollars for target_price gives the formula
    below. The stop is then the target's price *distance* scaled by the
    strategy's own stop:target ratio, so a strategy designed with a wider
    stop than target (or vice versa) keeps that same shape.
    """
    if capital is None or capital <= 0:
        capital = FALLBACK_CAPITAL

    f = TAKER_FEE_RATE
    s = SLIPPAGE_FRACTION

    fill_buy = entry_price * (1 + s)
    target_price = (target_net_dollars + capital * (1 - f)) * fill_buy / (capital * (1 - f) ** 2 * (1 - s))

    price_move_up = target_price - entry_price
    ratio = (stop_mult / target_mult) if target_mult > 0 else 1.0
    price_move_down = price_move_up * ratio

    return entry_price - price_move_down, target_price
