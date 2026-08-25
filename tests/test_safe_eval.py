import pandas as pd
import pytest

from botfarm.strategy.safe_eval import RuleEvalError, compile_check, safe_eval


def _row(**kwargs):
    return pd.Series(kwargs)


def test_simple_comparison():
    assert safe_eval("close > 100", _row(close=105)) is True
    assert safe_eval("close > 100", _row(close=95)) is False


def test_and_or_precedence():
    row = _row(rsi=25, close=95, bb_lower=100)
    assert safe_eval("close < bb_lower and rsi < 30", row) is True
    assert safe_eval("close > bb_lower and rsi < 30", row) is False
    assert safe_eval("close > bb_lower or rsi < 30", row) is True


def test_arithmetic_in_rule():
    row = _row(close=97, vwap=100)
    assert safe_eval("close < vwap * 0.98", row) is True
    assert safe_eval("close < vwap * 0.9", row) is False


def test_boolean_column_used_directly():
    row = _row(ema_cross_up=True, rsi=55)
    assert safe_eval("ema_cross_up and rsi > 50", row) is True
    row2 = _row(ema_cross_up=False, rsi=55)
    assert safe_eval("ema_cross_up and rsi > 50", row2) is False


def test_unknown_column_raises():
    with pytest.raises(RuleEvalError):
        safe_eval("nonexistent > 5", _row(close=100))


def test_function_calls_rejected():
    with pytest.raises(RuleEvalError):
        compile_check("__import__('os').system('echo hi')")
    with pytest.raises(RuleEvalError):
        compile_check("close.somemethod()")


def test_attribute_and_subscript_rejected():
    with pytest.raises(RuleEvalError):
        compile_check("close.real")
    with pytest.raises(RuleEvalError):
        compile_check("close[0]")


def test_compile_check_passes_valid_rule():
    compile_check("close <= bb_lower and rsi_14 <= 30")  # should not raise
