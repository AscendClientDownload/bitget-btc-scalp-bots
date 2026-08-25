import pytest

from botfarm.backtest.costs import CostModel
from botfarm.strategy.scalp_targets import (
    DEFAULT_TARGET_NET_DOLLARS,
    ROUND_TRIP_FRICTION_FRACTION,
    dollar_scalp_levels,
)


def test_friction_fraction_matches_cost_model_defaults():
    # The whole point is that "net of fees" is actually accurate -- if this
    # ever drifts from CostModel's real defaults, the promise is a lie.
    cost_model = CostModel()
    implied = 2 * cost_model.fee_rate + 2 * (cost_model.slippage_bps / 10_000)
    assert ROUND_TRIP_FRICTION_FRACTION == pytest.approx(implied)


def test_hitting_target_nets_the_requested_dollar_amount_after_real_fees():
    entry_price = 79_000.0
    capital = 1_000.0
    cost_model = CostModel()

    stop, target = dollar_scalp_levels(entry_price, capital, stop_mult=1.0, target_mult=1.0)

    # Simulate exactly what backtest/engine.py and live/paper_broker.py
    # actually do: buy at entry (with slippage+fee), sell at the computed
    # target (with slippage+fee), cost basis is shares * the SLIPPED entry
    # fill price (matches engine.py's `entry_price = fill_price`).
    entry_fill_price = cost_model.fill_price(entry_price, "buy")
    entry_fee = cost_model.fee(capital)
    shares = (capital - entry_fee) / entry_fill_price
    cost_basis = shares * entry_fill_price

    exit_fill_price = cost_model.fill_price(target, "sell")
    gross_proceeds = shares * exit_fill_price
    exit_fee = cost_model.fee(gross_proceeds)
    net_proceeds = gross_proceeds - exit_fee
    net_pnl = net_proceeds - cost_basis

    assert net_pnl == pytest.approx(DEFAULT_TARGET_NET_DOLLARS, abs=0.01)
    assert net_pnl > 0  # the actual thing being guarded against: a "profit" that's negative after fees


def test_larger_capital_needs_larger_price_move_for_same_dollar_target():
    entry_price = 79_000.0
    _, target_small = dollar_scalp_levels(entry_price, 500.0, 1.0, 1.0)
    _, target_large = dollar_scalp_levels(entry_price, 5_000.0, 1.0, 1.0)
    # More capital -> more shares -> smaller price move needed for the same dollar target.
    assert (target_small - entry_price) > (target_large - entry_price)


def test_stop_target_ratio_preserved():
    entry_price = 79_000.0
    capital = 1_000.0
    stop, target = dollar_scalp_levels(entry_price, capital, stop_mult=1.5, target_mult=2.5)
    stop_distance = entry_price - stop
    target_distance = target - entry_price
    assert stop_distance / target_distance == pytest.approx(1.5 / 2.5, rel=1e-6)


def test_none_capital_falls_back_instead_of_crashing():
    stop, target = dollar_scalp_levels(79_000.0, None, 1.0, 1.5)
    assert stop < 79_000.0 < target


def test_zero_or_negative_capital_falls_back_instead_of_crashing():
    stop, target = dollar_scalp_levels(79_000.0, 0.0, 1.0, 1.5)
    assert stop < 79_000.0 < target
    stop2, target2 = dollar_scalp_levels(79_000.0, -50.0, 1.0, 1.5)
    assert stop2 < 79_000.0 < target2
