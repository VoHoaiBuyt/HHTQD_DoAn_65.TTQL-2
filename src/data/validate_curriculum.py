"""Compatibility entry point for the core curriculum validator."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.curriculum_validation import main


if __name__ == "__main__":
    main()
