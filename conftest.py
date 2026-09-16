"""Shared test support; production skills do not depend on this module."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "tests"))
