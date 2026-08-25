import pytest

from botfarm.backtest.costs import CostModel


def test_fee_calculation():
    cost_model = CostModel(fee_rate=0.001, slippage_bps=0)
    assert cost_model.fee(1000.0) == pytest.approx(1.0)


def test_buy_slippage_increases_fill_price():
    cost_model = CostModel(fee_rate=0.0, slippage_bps=10)  # 0.1%
    assert cost_model.fill_price(100.0, "buy") == pytest.approx(100.1)


def test_sell_slippage_decreases_fill_price():
    cost_model = CostModel(fee_rate=0.0, slippage_bps=10)
    assert cost_model.fill_price(100.0, "sell") == pytest.approx(99.9)


def test_invalid_side_raises():
    cost_model = CostModel()
    with pytest.raises(ValueError):
        cost_model.fill_price(100.0, "hold")
