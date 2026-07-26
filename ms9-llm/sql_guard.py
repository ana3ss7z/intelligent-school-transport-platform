"""
Validateur SQL (couche 2 de défense) — le rôle read-only Postgres reste LE garde-fou.
N'autorise qu'une seule requête SELECT/WITH en lecture ; force un LIMIT ; bloque tout le reste.
"""
from __future__ import annotations

import re

from config import settings

# Mots-clés interdits (écriture, DDL, admin, fonctions dangereuses)
_BLACKLIST = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|merge|call|do|copy|"
    r"vacuum|analyze|reindex|refresh|cluster|comment|security|"
    r"pg_sleep|pg_read_file|pg_read_binary_file|pg_ls_dir|pg_stat_file|lo_import|lo_export|"
    r"dblink|current_setting|set_config)\b",
    re.IGNORECASE,
)
# Identifiants sensibles jamais interrogeables (double garde, le rôle les bloque déjà)
_SENSIBLE = re.compile(r"\b(mot_de_passe|fcm_token|contenu|geometrie|device_tokens)\b", re.IGNORECASE)


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)   # /* ... */
    sql = re.sub(r"--[^\n]*", " ", sql)                     # -- ...
    return sql


class SqlRejected(ValueError):
    pass


def valider_et_normaliser(sql: str) -> str:
    """Retourne un SQL sain (avec LIMIT) ou lève SqlRejected."""
    if not sql or not sql.strip():
        raise SqlRejected("requête vide")

    clean = _strip_comments(sql).strip().rstrip(";").strip()

    # Une seule instruction (aucun ';' interne restant)
    if ";" in clean:
        raise SqlRejected("une seule instruction SQL est autorisée")

    low = clean.lower()

    # Doit commencer par SELECT ou WITH (CTE de lecture)
    if not (low.startswith("select") or low.startswith("with")):
        raise SqlRejected("seules les requêtes SELECT sont autorisées")

    # Un WITH doit contenir un SELECT (pas de CTE d'écriture : WITH ... AS ( DELETE ... ))
    if low.startswith("with") and "select" not in low:
        raise SqlRejected("CTE non lecture refusée")

    # Blacklist mots-clés dangereux
    if _BLACKLIST.search(clean):
        raise SqlRejected("mot-clé SQL interdit détecté")

    # Colonnes/tables sensibles
    if _SENSIBLE.search(clean):
        raise SqlRejected("accès à une donnée sensible refusé")

    # Forcer un LIMIT si absent
    if not re.search(r"\blimit\b", low):
        clean = f"{clean} LIMIT {settings.sql_default_limit}"

    return clean
