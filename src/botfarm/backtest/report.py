"""Generates backtest_report.md, equity_curve.png, and trades.csv from a
BacktestResult — every number in the report comes from metrics.py / the
result object directly, nothing is hand-typed."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from botfarm.backtest.engine import BacktestResult
from botfarm.backtest.metrics import Metrics, compute_metrics


def trades_to_df(result: BacktestResult) -> pd.DataFrame:
    rows = [
        {
            "strategy_id": t.strategy_id,
            "entry_bar": t.entry_bar,
            "entry_ts_ms": t.entry_ts_ms,
            "entry_time": pd.to_datetime(t.entry_ts_ms, unit="ms", utc=True),
            "entry_price": t.entry_price,
            "exit_bar": t.exit_bar,
            "exit_ts_ms": t.exit_ts_ms,
            "exit_time": pd.to_datetime(t.exit_ts_ms, unit="ms", utc=True),
            "exit_price": t.exit_price,
            "exit_reason": t.exit_reason.value,
            "stop_loss": t.stop_loss,
            "take_profit": t.take_profit,
            "fees_paid": t.fees_paid,
            "return_pct": t.return_pct * 100,
            "capital_before": t.capital_before,
            "capital_after": t.capital_after,
        }
        for t in result.trades
    ]
    return pd.DataFrame(rows)


def write_report(
    result: BacktestResult,
    strategy_id: str,
    symbol: str,
    timeframe: str,
    date_range: tuple[str, str],
    out_dir: Path,
) -> Metrics:
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics = compute_metrics(result)
    trades_df = trades_to_df(result)
    trades_df.to_csv(out_dir / "trades.csv", index=False)

    _write_equity_curve_png(result, out_dir / "equity_curve.png")
    _write_markdown_report(metrics, result, strategy_id, symbol, timeframe, date_range, out_dir / "backtest_report.md")

    return metrics


def _verdict_line(metrics: Metrics) -> str:
    """A verdict derived purely from the computed metrics — not a hand-typed
    claim — so a losing backtest is reported as losing, not glossed over."""
    if metrics.num_trades == 0:
        return "No trades were taken over this period — no verdict possible."
    if metrics.profit_factor < 1.0 or metrics.expectancy_pct < 0:
        return (
            f"**Negative expectancy over this period** (profit factor {metrics.profit_factor:.3f}, "
            f"expectancy {metrics.expectancy_pct:.3f}% per trade). This configuration did not show a "
            "real edge net of fees and slippage over the tested window. Do not treat this as a working "
            "bot — see docs/RISK_DISCLAIMER.md."
        )
    return (
        f"Positive expectancy over this period (profit factor {metrics.profit_factor:.3f}, "
        f"expectancy {metrics.expectancy_pct:.3f}% per trade). This does not guarantee future "
        "performance — see docs/RISK_DISCLAIMER.md before drawing conclusions from a single backtest window."
    )


def _write_equity_curve_png(result: BacktestResult, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    if not result.equity_curve.empty:
        times = pd.to_datetime(result.equity_curve["ts_ms"], unit="ms", utc=True)
        ax.plot(times, result.equity_curve["equity"], linewidth=1)
    ax.set_title("Equity Curve")
    ax.set_xlabel("Time")
    ax.set_ylabel("Equity (quote currency)")
    ax.axhline(result.starting_capital, color="gray", linestyle="--", linewidth=0.8, label="Starting capital")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _write_markdown_report(
    metrics: Metrics,
    result: BacktestResult,
    strategy_id: str,
    symbol: str,
    timeframe: str,
    date_range: tuple[str, str],
    path: Path,
) -> None:
    lines = [
        f"# Backtest Report: {strategy_id}",
        "",
        f"- **Symbol**: {symbol}",
        f"- **Timeframe**: {timeframe}",
        f"- **Date range**: {date_range[0]} to {date_range[1]}",
        f"- **Starting capital**: {result.starting_capital:,.2f}",
        f"- **Ending capital**: {result.ending_capital:,.2f}",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Total return | {metrics.total_return_pct:.2f}% |",
        f"| Number of trades | {metrics.num_trades} |",
        f"| Win rate | {metrics.win_rate:.2f}% |",
        f"| Profit factor | {metrics.profit_factor:.3f} |",
        f"| Max drawdown | {metrics.max_drawdown_pct:.2f}% |",
        f"| Sharpe (annualized) | {metrics.sharpe:.3f} |",
        f"| Sortino (annualized) | {metrics.sortino:.3f} |",
        f"| Avg trade return | {metrics.avg_trade_return_pct:.3f}% |",
        f"| Avg holding bars | {metrics.avg_holding_bars:.1f} |",
        f"| Expectancy per trade | {metrics.expectancy_pct:.3f}% |",
        "",
        "## Verdict",
        "",
        _verdict_line(metrics),
        "",
        "## Notes / assumptions",
        "",
        "- Fees: Bitget spot taker rate (0.1% per side, 0.2% round trip).",
        "- Slippage: fixed 5bps haircut against the trader per fill (assumption, not measured market impact).",
        "- One position at a time, fixed-fractional sizing, long-only (spot).",
        "- Past backtest performance on historical data does not guarantee future results. "
        "Short-timeframe (1-5min) BTC scalping is heavily affected by fees, slippage, and "
        "market noise — see docs/RISK_DISCLAIMER.md.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
