# Risk Disclaimer

Read this before treating any output of this project as investment advice or
as a reason to risk real capital. It isn't, and it shouldn't be.

## This is not a "guaranteed profit" system

Nothing in this repository can promise consistent or "almost always"
profitable trading. Anyone claiming that about a retail scalping bot is
either wrong or selling something. What this project can honestly claim is:
a rigorous backtest of one real strategy against real historical data, a
transparent cost model, and a re-tuning process with guardrails against the
most obvious failure modes. That's it.

## This isn't theoretical — we tested it

15 variants of bot #1, across two different strategy families (trend-following
and mean-reversion, see `docs/ARCHITECTURE.md`), were backtested on a real
year of Bitget 5-minute BTCUSDT data with a chronological train/holdout
split. **None showed a validated positive edge.** Expectancy per trade
consistently landed around -0.12% to -0.20%, right around the transaction
cost floor, regardless of which indicators were used. Stacking many
confirming filters at once didn't help either — it just narrowed entries
down to zero trades in a full year. This is the concrete evidence behind
every general statement in this document, not just a theoretical warning.

## Why 1-5 minute BTC scalping is especially hard

- **Fees dominate small moves.** Bitget spot taker fees are 0.1% per side —
  0.2% round trip. A 5-minute-bar scalp targeting a small move can easily see
  its edge, if any exists, consumed entirely by fees plus slippage.
- **Noise dominates signal at short timeframes.** The shorter the bar, the
  larger the fraction of price movement that is effectively random relative
  to any true predictive signal. Indicators computed on 1-5min bars are more
  prone to false signals than the same indicators on higher timeframes.
- **Backtests overstate real-world performance.** Backtests here assume fills
  at a modeled price with a fixed slippage haircut — real fills, especially
  during volatility, can be worse. Backtest results are a upper-bound-ish
  estimate under favorable assumptions, not a prediction.

## Why daily "self-improvement" (adaptive re-tuning) is not a fix for the above

The adaptive re-tuning module (see [ADAPTIVE_RETUNING.md](ADAPTIVE_RETUNING.md))
re-tunes strategy parameters using a walk-forward process with an
out-of-sample validation split, bounded parameter drift, and a full audit
log — specifically to reduce (not eliminate) the risk of curve-fitting to
noise. But:

- A 3-day out-of-sample validation window on 5-minute bars contains very few
  *effectively independent* trades. Passing that validation bar is weak
  evidence, not proof, that a parameter change reflects a real, persistent
  edge rather than a lucky recent stretch.
- Re-tuning can, at best, help a strategy track slowly drifting market
  regime characteristics. It cannot manufacture an edge that isn't there to
  begin with.
- Every re-tune is logged specifically so a human can review whether the
  parameter history looks like sensible adaptation or like noise-chasing.

## Current status: paper trading only

No component of this project places real orders. The `live/` runner
polls Bitget's public market-data API and simulates fills using the same
cost model as the backtester — it never touches an exchange account. If and
when authenticated live trading is added, treat that as a completely
separate, much higher-stakes decision — start with small size, monitor
closely, and expect the live results to be worse than the backtest and paper
trading results, not better.

## Bottom line

Use this project to learn, to build a rigorous testing habit, and to see
honestly whether a given strategy has any real edge once costs are
accounted for. Do not treat a positive backtest number, on its own, as a
reason to risk money you can't afford to lose.
