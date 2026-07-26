"""
Accès Postgres READ-ONLY pour le NL2SQL admin (Phase B).
Connexion via le rôle dédié `ms9_readonly` (lecture seule + grants colonne au niveau DB).
"""
from __future__ import annotations

import logging

import asyncpg

from config import settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


class DBUnavailable(Exception):
    """Le pool read-only n'a pas pu être initialisé (rôle/DB absent)."""


async def init_pool() -> bool:
    """Initialise le pool read-only. Retourne False si indisponible (mode dégradé)."""
    global _pool
    if _pool is not None:
        return True
    if not settings.db_ro_password:
        logger.warning("[MS9] DB_RO_PASSWORD non défini — NL2SQL admin désactivé.")
        return False
    try:
        _pool = await asyncpg.create_pool(
            host=settings.db_ro_host, port=settings.db_ro_port, database=settings.db_ro_name,
            user=settings.db_ro_user, password=settings.db_ro_password,
            min_size=1, max_size=4, command_timeout=settings.sql_timeout_ms / 1000.0,
        )
        logger.info("[MS9] Pool Postgres read-only initialisé (%s@%s).", settings.db_ro_user, settings.db_ro_name)
        return True
    except Exception as exc:
        logger.error("[MS9] Pool read-only indisponible : %s", exc)
        _pool = None
        return False


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def available() -> bool:
    return _pool is not None


async def run_readonly(sql: str) -> dict:
    """Exécute une requête SELECT en transaction READ ONLY. Retourne {colonnes, lignes} (capées).

    Lève une exception (message DB) en cas d'erreur SQL — l'appelant gère l'auto-correction.
    """
    if _pool is None:
        raise DBUnavailable("pool read-only non initialisé")
    async with _pool.acquire() as conn:
        # Double garde : transaction read-only + timeout (le rôle les impose déjà, on renforce)
        tr = conn.transaction(readonly=True)
        await tr.start()
        try:
            await conn.execute(f"SET LOCAL statement_timeout = {int(settings.sql_timeout_ms)}")
            rows = await conn.fetch(sql)
        finally:
            await tr.rollback()   # aucune écriture possible de toute façon
    capped = rows[: settings.sql_max_rows]
    colonnes = list(capped[0].keys()) if capped else []
    lignes = [list(r.values()) for r in capped]
    return {"colonnes": colonnes, "lignes": lignes, "n": len(rows), "tronque": len(rows) > len(capped)}
