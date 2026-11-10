"""Compatibility imports for notebooks and scripts predating the core layout."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.plan_risk import (
    _self_test,
    credits_to_curricular_units,
    m3_prime_probability,
    plan_risk,
)

__all__ = [
    "credits_to_curricular_units",
    "m3_prime_probability",
    "plan_risk",
]


if __name__ == "__main__":
    _self_test()
