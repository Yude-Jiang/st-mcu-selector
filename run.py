from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "server"))
os.chdir(ROOT)

from bootstrap import main

if __name__ == "__main__":
    main()
