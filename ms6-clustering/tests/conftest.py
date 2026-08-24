"""Rend les modules de MS6 importables depuis `tests/` sans installer le service.

Même procédé que `ms9-llm/tests/conftest.py`, le seul autre dossier de tests du dépôt.
"""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
