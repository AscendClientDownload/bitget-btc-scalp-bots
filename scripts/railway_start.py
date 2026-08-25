"""Railway entrypoint (see Procfile).

Runs the paper-trading bot as a supervised background process (restarted if
it ever crashes) and the dashboard as the foreground process -- Railway
watches the foreground process to decide whether the service is healthy, and
routes the public domain's HTTP traffic to whatever binds $PORT, which is
the dashboard.
"""
from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def supervise_bot() -> None:
    while True:
        proc = subprocess.run([PYTHON, str(ROOT / "scripts" / "run_paper_trading.py")])
        print(f"[railway_start] bot exited (code {proc.returncode}), restarting in 10s", flush=True)
        time.sleep(10)


if __name__ == "__main__":
    threading.Thread(target=supervise_bot, daemon=True).start()
    subprocess.run([PYTHON, str(ROOT / "scripts" / "run_dashboard.py")], check=True)
