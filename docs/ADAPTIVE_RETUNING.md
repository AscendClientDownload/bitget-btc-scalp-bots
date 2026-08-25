# Adaptive Re-tuning (planned, currently paused)

This module is designed but not yet built — paused at the user's request in
favor of researching existing open-source bots and building the trades
dashboard first. This doc describes the intended design so it isn't lost,
and so anyone reading `docs/RISK_DISCLAIMER.md`'s reference to it has
context.

## Intended design

- **Cadence**: a daily job re-tunes each bot's parameters using a rolling
  window of its own recent trading data.
- **Train/validation split**: candidate parameters are searched over a
  trailing training window (e.g. 14 days), then must beat the *current live*
  parameters on a separate, non-overlapping out-of-sample validation window
  (e.g. the most recent 3 days) by a minimum margin before being adopted.
  The validation data is never used in the search itself — this is walk-forward
  validation, not in-sample optimization.
- **Bounded search**: only a small neighborhood around the current live
  parameters is searched (e.g. EMA period ±2, RSI band ±5, ATR multiple
  ±0.2) — never a full re-optimization from scratch, and a hard cap on
  maximum parameter drift per day.
- **Audit log**: every decision (old params, candidate params, train/validation
  metrics, accept/reject and why) is appended to a `retune_log` table
  (already present in `live/ledger.py`'s schema) so a human can review
  whether the parameter history looks like sensible adaptation or
  noise-chasing.

## Why this is not "guaranteed self-improvement"

See [RISK_DISCLAIMER.md](RISK_DISCLAIMER.md). A 3-day out-of-sample window on
5-minute bars has very few effectively independent trades — passing
validation is weak evidence of a real edge, not proof of one. This mechanism
is meant to reduce overfitting risk relative to naive live self-mutation,
not eliminate it, and it cannot manufacture an edge that isn't there.
