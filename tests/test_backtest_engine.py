import pandas as pd
import pytest

from botfarm.backtest.costs import CostModel
from botfarm.backtest.engine import run_backtest
from botfarm.strategy.base import ExitReason, IndicatorSpec, Strategy, StrategyContext


class AlwaysEnterFixedStop(Strategy):
    """Test-only strategy: enters on the first bar, fixed stop/target, no signal exit."""

    id = "test_fixed_stop"
    timeframe = "5min"
    max_holding_bars = None

    def __init__(self, stop_offset=2.0, target_offset=2.0):
        self.stop_offset = stop_offset
        self.target_offset = target_offset
        self._entered = False

    def required_indicators(self) -> list[IndicatorSpec]:
        return []

    def entry_signal(self, ctx: StrategyContext) -> bool:
        if self._entered:
            return False
        self._entered = True
        return True

    def exit_signal(self, ctx: StrategyContext) -> bool:
        return False

    def stop_loss(self, ctx: StrategyContext) -> float:
        return ctx.close - self.stop_offset

    def take_profit(self, ctx: StrategyContext) -> float:
        return ctx.close + self.target_offset


def _make_df(closes, highs=None, lows=None):
    n = len(closes)
    highs = highs or [c + 0.5 for c in closes]
    lows = lows or [c - 0.5 for c in closes]
    return pd.DataFrame(
        {
            "ts_ms": [1_600_000_000_000 + i * 300_000 for i in range(n)],
            "open": closes,
            "high": highs,
            "low": lows,
            "close": closes,
            "base_volume": [100.0] * n,
        }
    )


def test_no_fees_no_slippage_take_profit_hits():
    # Enter at bar0 close=100 -> target=102. Bar1 high reaches 103 -> TP fill at 102.
    df = _make_df(closes=[100, 100], highs=[100.5, 103], lows=[99.5, 99.5])
    strategy = AlwaysEnterFixedStop(stop_offset=2.0, target_offset=2.0)
    zero_cost = CostModel(fee_rate=0.0, slippage_bps=0.0)
    result = run_backtest(strategy, df, starting_capital=1000.0, position_fraction=1.0, cost_model=zero_cost)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == ExitReason.TAKE_PROFIT
    assert trade.entry_price == pytest.approx(100.0)
    assert trade.exit_price == pytest.approx(102.0)
    # 1000 shares? no: shares = notional/entry_price = 1000/100 = 10; proceeds = 10*102=1020
    assert result.ending_capital == pytest.approx(1020.0)


def test_stop_loss_hits_before_take_profit_in_same_bar():
    # Both stop (98) and target (102) are within bar1's range -> conservative
    # ordering assumes stop-loss triggers first.
    df = _make_df(closes=[100, 100], highs=[100.5, 103], lows=[99.5, 97])
    strategy = AlwaysEnterFixedStop(stop_offset=2.0, target_offset=2.0)
    zero_cost = CostModel(fee_rate=0.0, slippage_bps=0.0)
    result = run_backtest(strategy, df, starting_capital=1000.0, position_fraction=1.0, cost_model=zero_cost)

    assert len(result.trades) == 1
    assert result.trades[0].exit_reason == ExitReason.STOP_LOSS
    assert result.trades[0].exit_price == pytest.approx(98.0)


def test_fees_reduce_ending_capital():
    df = _make_df(closes=[100, 100], highs=[100.5, 103], lows=[99.5, 99.5])
    strategy = AlwaysEnterFixedStop(stop_offset=2.0, target_offset=2.0)
    cost_model = CostModel(fee_rate=0.001, slippage_bps=0.0)
    result = run_backtest(strategy, df, starting_capital=1000.0, position_fraction=1.0, cost_model=cost_model)

    trade = result.trades[0]
    # entry fee = 1000*0.001=1 -> shares=(1000-1)/100=9.99
    # exit gross = 9.99*102=1018.98, exit fee=1018.98*0.001=1.01898
    assert trade.fees_paid == pytest.approx(1.0 + 9.99 * 102 * 0.001, rel=1e-3)
    assert result.ending_capital < 1020.0  # less than the zero-fee case


def test_slippage_worsens_fills():
    df = _make_df(closes=[100, 100], highs=[100.5, 103], lows=[99.5, 99.5])
    strategy = AlwaysEnterFixedStop(stop_offset=2.0, target_offset=2.0)
    cost_model = CostModel(fee_rate=0.0, slippage_bps=100)  # 1% slippage
    result = run_backtest(strategy, df, starting_capital=1000.0, position_fraction=1.0, cost_model=cost_model)

    trade = result.trades[0]
    assert trade.entry_price == pytest.approx(101.0)  # buy fills higher
    assert trade.exit_price == pytest.approx(102 * 0.99)  # sell fills lower


def test_one_position_at_a_time_no_reentry_while_in_position():
    class AlwaysWantsToEnter(Strategy):
        id = "test_always_enter"
        timeframe = "5min"
        max_holding_bars = None

        def required_indicators(self):
            return []

        def entry_signal(self, ctx):
            return True  # would re-enter every bar if allowed

        def exit_signal(self, ctx):
            return False

        def stop_loss(self, ctx):
            return ctx.close - 100  # far away, won't hit

        def take_profit(self, ctx):
            return ctx.close + 100  # far away, won't hit

    df = _make_df(closes=[100, 101, 102, 103, 104])
    strategy = AlwaysWantsToEnter()
    result = run_backtest(strategy, df, starting_capital=1000.0, cost_model=CostModel(0.0, 0.0))
    assert len(result.trades) == 0  # never exits, so only ever enters once and stays in position
    assert len(result.equity_curve) == 5


def test_time_stop_forces_exit():
    class EntersOnceTimeStop(Strategy):
        id = "test_time_stop"
        timeframe = "5min"
        max_holding_bars = 2

        def __init__(self):
            self._entered = False

        def required_indicators(self):
            return []

        def entry_signal(self, ctx):
            if self._entered:
                return False
            self._entered = True
            return True

        def exit_signal(self, ctx):
            return False

        def stop_loss(self, ctx):
            return ctx.close - 100

        def take_profit(self, ctx):
            return ctx.close + 100

    df = _make_df(closes=[100, 100, 100, 100])
    result = run_backtest(EntersOnceTimeStop(), df, starting_capital=1000.0, cost_model=CostModel(0.0, 0.0))
    assert len(result.trades) == 1
    assert result.trades[0].exit_reason == ExitReason.TIME_STOP
    assert result.trades[0].exit_bar == 2  # entry_bar(0) + max_holding_bars(2)
