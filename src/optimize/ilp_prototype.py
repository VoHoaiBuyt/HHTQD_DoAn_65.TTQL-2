"""Compatibility imports for notebooks and scripts predating the core layout."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.ilp import compute_unlock_values, solve_plan

__all__ = ["compute_unlock_values", "solve_plan"]
