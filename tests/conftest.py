"""Make the repo-root anakrisis.py importable from the tests directory."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
