"""Root conftest: inject project root into sys.path so pytest works without PYTHONPATH=."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
