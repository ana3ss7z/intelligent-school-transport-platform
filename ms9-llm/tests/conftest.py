"""Rend les modules de MS9 importables depuis `tests/` sans installer le service."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
