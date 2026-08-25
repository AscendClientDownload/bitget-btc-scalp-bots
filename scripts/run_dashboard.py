"""Start the local trades dashboard at http://127.0.0.1:5000 (read-only)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from botfarm.live.dashboard import main

if __name__ == "__main__":
    main()
