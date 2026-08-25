"""Restricted expression evaluator for declarative strategy rule strings.

Deliberately NOT `eval()`: rule strings come from YAML config files (the
strategy catalog), and while these files are authored by us today, a
declarative-rules system is exactly the kind of thing that could later take
input from elsewhere. This walks the AST and only allows a small whitelist
of node types (comparisons, boolean/unary logic, arithmetic, column-name
lookups, numeric/bool literals) -- no function calls, no attribute access,
no subscripting, nothing that could execute arbitrary code.

Rules are evaluated one row (one bar) at a time against scalar values, not
vectorized across a whole column -- matching how the bespoke strategies
(bot01_*.py) evaluate entry_signal/exit_signal via StrategyContext.row.
"""
from __future__ import annotations

import ast
import operator

import pandas as pd

_COMPARE_OPS = {
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}
_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


class RuleEvalError(ValueError):
    pass


def _eval_node(node: ast.AST, row: pd.Series):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, row)

    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            result = True
            for v in node.values:
                result = result and _eval_node(v, row)
            return result
        if isinstance(node.op, ast.Or):
            result = False
            for v in node.values:
                result = result or _eval_node(v, row)
            return result
        raise RuleEvalError(f"unsupported bool op {type(node.op).__name__}")

    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            return not _eval_node(node.operand, row)
        if isinstance(node.op, ast.USub):
            return -_eval_node(node.operand, row)
        raise RuleEvalError(f"unsupported unary op {type(node.op).__name__}")

    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, row)
        result = True
        for op, comparator in zip(node.ops, node.comparators):
            op_fn = _COMPARE_OPS.get(type(op))
            if op_fn is None:
                raise RuleEvalError(f"unsupported comparison op {type(op).__name__}")
            right = _eval_node(comparator, row)
            result = result and op_fn(left, right)
            left = right
        return result

    if isinstance(node, ast.BinOp):
        op_fn = _BIN_OPS.get(type(node.op))
        if op_fn is None:
            raise RuleEvalError(f"unsupported binary op {type(node.op).__name__}")
        return op_fn(_eval_node(node.left, row), _eval_node(node.right, row))

    if isinstance(node, ast.Name):
        if node.id not in row.index:
            raise RuleEvalError(f"unknown column {node.id!r} referenced in rule")
        return row[node.id]

    if isinstance(node, ast.Constant):
        if not isinstance(node.value, (int, float, bool)):
            raise RuleEvalError(f"unsupported constant {node.value!r}")
        return node.value

    raise RuleEvalError(f"unsupported expression node {type(node).__name__}")


def compile_check(rule: str) -> None:
    """Parse-and-walk without a row, to validate a rule string at load time
    (catches typos/disallowed syntax before any backtest runs)."""
    tree = ast.parse(rule, mode="eval")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Call, ast.Attribute, ast.Subscript, ast.Lambda)):
            raise RuleEvalError(f"disallowed syntax in rule: {rule!r}")


def safe_eval(rule: str, row: pd.Series) -> bool:
    tree = ast.parse(rule, mode="eval")
    return bool(_eval_node(tree, row))
