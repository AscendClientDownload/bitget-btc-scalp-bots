# Deploying to Railway

No credit card needed to start (GitHub sign-in + a one-time $5 trial
credit). Read the cost/sleep caveats in the README's Railway section before
you begin — this isn't free forever, just free to start.

## 1. Create the project

1. Go to [railway.app](https://railway.app) and sign in with GitHub.
2. **New Project → Deploy from GitHub repo**.
3. If this is the first time, Railway will ask to install its GitHub App —
   authorize it and grant it access to the `bitget-btc-scalp-bots` repo
   (it's private, so Railway needs explicit access to just that repo, not
   your whole account).
4. Select `bitget-btc-scalp-bots`. Railway auto-detects it as a Python app
   (via `requirements.txt` and `.python-version`) and finds the `Procfile`,
   which sets the start command to `python scripts/railway_start.py` — you
   shouldn't need to configure a start command manually.

## 2. Add a persistent Volume for the ledger

Without this, every redeploy wipes the trade history (container disk is
ephemeral by default).

1. Open the service → **Volumes** tab → **+ New Volume**.
2. Mount path: `/data`
3. Size: the default (a few GB) is far more than a SQLite ledger needs.

## 3. Set the environment variable

Service → **Variables** tab → **+ New Variable**:

```
BOTFARM_DB_PATH=/data/botfarm_ledger.db
```

That's the only variable needed — there are no API keys or secrets, since
everything talks to Bitget's public (unauthenticated) market-data API only.

## 4. Deploy and generate a public domain

1. If a deploy didn't start automatically, click **Deploy**.
2. Watch the **Deploy Logs** — you should see lines like `starting
   paper-trading runner for bot01_mean_reversion on 5min timeframe` and,
   after Railway finishes building, `Serving on http://0.0.0.0:<port>`.
3. Service → **Settings → Networking → Generate Domain**. Railway gives you
   a URL like `https://bitget-btc-scalp-bots-production.up.railway.app` —
   that's your dashboard, reachable from anywhere.

## 5. Verify it's actually running

- Open the generated URL — you should see the dashboard (empty until the
  bot's first tick).
- Check **Deploy Logs** a few minutes later for `tick ok: candle=... status=...`
  heartbeat lines — proof the bot is actually polling, not just that the web
  process is up.
- Redeploy once on purpose (Settings → Redeploy) and confirm the ledger
  still shows prior trades afterward — that's the volume working.

## Notes

- **Don't enable "Serverless" mode** in service settings — that opts into
  sleep-on-inactivity, which is exactly what you don't want here. It's off
  by default; just leave it off.
- **The dashboard is public** at whatever URL Railway generates — it's
  read-only (no endpoint can place trades or modify anything) and shows
  simulated paper-trading data only, but if that URL leaks it's visible to
  anyone. Don't share it publicly if you'd rather keep it private; ask if
  you want basic-auth added on top.
- **Cost**: keep an eye on the $5 trial credit under Usage. Once it's gone,
  Railway will prompt for a card to continue on the Hobby plan (~$5/mo) —
  that's a decision for you to make when you get there, not something set
  up to happen automatically.
