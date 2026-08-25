"""Start the local trades dashboard at http://127.0.0.1:5000 (read-only)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

print("[run_dashboard] script started, importing botfarm.live.dashboard...", flush=True)
from botfarm.live.dashboard import main
print("[run_dashboard] import complete, calling main()...", flush=True)

if __name__ == "__main__":
    main()
