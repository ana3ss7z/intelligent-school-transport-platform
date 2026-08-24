"""
Mémoire du dernier nombre de bus retenu — support de l'hystérésis.

Pourquoi une mémoire
--------------------
MS6 recalcule à chaque inscription d'élève. Sans mémoire, la règle de parcimonie bascule vers tout
`k` plus petit dès qu'il devient faisable (au franchissement de ⌈n/capacité⌉), et **chaque bascule
redistribue toute l'école** : mesuré, 12 à 17 % des élèves changent de bus pour une seule
inscription. L'hystérésis consiste à garder le `k` en place tant qu'il tient et qu'il n'est pas
nettement battu.

Pourquoi un fichier dédié, et pas `quality_baseline.json`
---------------------------------------------------------
Ce dernier ne contient ni `k`, ni `n`, ni la capacité, ni le rayon — et il n'est écrit que sur les
runs de verdict **OK**. Une mémoire qui se périme en silence est pire que pas de mémoire.

Pourquoi le contexte est enregistré avec le `k`
-----------------------------------------------
Un `k` n'a de sens que pour un effectif, une capacité de bus et un rayon donnés. Si la capacité
passe de 50 à 60 places, « 7 bus » ne veut plus rien dire et **doit** être ignoré. C'est ce que
vérifie `contexte_compatible`.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

FICHIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "last_selection.json")


def ecrire_json_atomique(chemin: str, donnees: dict) -> None:
    """Écrit un JSON sans jamais laisser de fichier tronqué.

    Deux chemins de code peuvent lancer un clustering en parallèle (l'endpoint HTTP et le consumer
    RabbitMQ), et un `open(..., "w")` interrompu laisse un fichier illisible que le service relira
    au démarrage suivant. On écrit donc dans un temporaire du même dossier, puis on renomme :
    `os.replace` est atomique sur le même système de fichiers.
    """
    dossier = os.path.dirname(chemin) or "."
    os.makedirs(dossier, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dossier, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(donnees, f, indent=2, ensure_ascii=False)
        os.replace(tmp, chemin)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def charger(chemin: str = FICHIER) -> dict | None:
    """Relit la mémoire. Retourne `None` si absente ou illisible — jamais d'exception.

    Un service qui refuse de démarrer parce qu'un fichier de confort est corrompu serait pire que
    le problème qu'on corrige : on repart simplement sans hystérésis.
    """
    try:
        with open(chemin, encoding="utf-8") as f:
            etat = json.load(f)
        if isinstance(etat, dict) and isinstance(etat.get("k"), int):
            return etat
        logger.warning("[MS6] Mémoire de sélection mal formée — ignorée")
    except FileNotFoundError:
        pass
    except Exception as exc:
        logger.warning("[MS6] Mémoire de sélection illisible (%s) — ignorée", exc)
    return None


def enregistrer(k: int, n: int, capacity: int, rayon_max_m: float,
                chemin: str = FICHIER) -> None:
    """Mémorise le `k` retenu **et son contexte**."""
    ecrire_json_atomique(chemin, {
        "k": int(k), "n": int(n), "capacity": int(capacity),
        "rayon_max_m": float(rayon_max_m),
        "dateMAJ": datetime.now(timezone.utc).isoformat(),
    })


def contexte_compatible(etat: dict | None, capacity: int, rayon_max_m: float,
                        n_bus_actifs: int | None = None) -> int | None:
    """Retourne le `k` mémorisé s'il est encore comparable à la situation actuelle, sinon `None`.

    Trois raisons de l'oublier :
    - **la capacité des bus a changé** → le nombre de bus n'est plus la même grandeur ;
    - **le rayon maximal a changé** → la contrainte géographique n'est plus la même ;
    - **la flotte a rétréci** sous le `k` mémorisé → garder 7 bus quand il n'en reste 6 n'a pas de
      sens, et `binding.py` laisserait silencieusement des élèves sans bus.
    """
    if not etat:
        return None
    if int(etat.get("capacity", -1)) != int(capacity):
        logger.info("[MS6] Mémoire ignorée : capacité %s → %s", etat.get("capacity"), capacity)
        return None
    if abs(float(etat.get("rayon_max_m", -1.0)) - float(rayon_max_m)) > 1e-9:
        logger.info("[MS6] Mémoire ignorée : rayon %s → %s", etat.get("rayon_max_m"), rayon_max_m)
        return None
    k = int(etat["k"])
    if n_bus_actifs is not None and k > n_bus_actifs:
        logger.warning("[MS6] Mémoire ignorée : k=%d mémorisé pour une flotte de %d bus",
                       k, n_bus_actifs)
        return None
    return k
