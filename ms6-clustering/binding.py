"""
Liaison groupe (clustering MS6) ↔ bus physique (MS1) — intégration B1.

Le clustering produit des `groupeId` (1..k) ; les notifications (MS4), l'ETA temps réel (MS12) et le GPS
travaillent par `busId` (entité Bus de MS1). Sans ce pont, `findByBusId` renvoie vide → aucun parent notifié.

`appliquer_bus(mapping)` résout chaque groupe vers un bus MS1 actif (1-1 par id ; les bus sont de capacité
uniforme et les clusters ≤ capacité par construction) et propage `busId` aux élèves via un bulk MS2.
Les dispersés (groupe 999) ne reçoivent pas de bus (ramassage individuel). Dégradé si MS1 indispo / flotte trop petite.
"""
import logging

from ms1_client import get_bus_actifs
from ms2_client import assigner_bus_bulk

logger = logging.getLogger(__name__)

DISPERSE = 999


async def appliquer_bus(mapping: dict[int, int]) -> dict:
    """
    mapping : {eleveId: groupeId} (999 = dispersé). Écrit busId sur les élèves.
    Retourne un rapport {groupe_to_bus, n_lies, k, n_bus_actifs, manque_bus}.
    """
    groupes = sorted({g for g in mapping.values() if g and g != DISPERSE})
    k = len(groupes)

    try:
        bus = await get_bus_actifs()
    except Exception as exc:
        logger.warning("[MS6] Liaison groupe↔bus impossible — MS1 indisponible (%s)", exc)
        return {"groupe_to_bus": {}, "n_lies": 0, "k": k, "n_bus_actifs": 0,
                "manque_bus": k, "erreur": "MS1 indisponible"}

    # Mapping 1-1 par ordre d'id (capacité uniforme → l'appariement fin est inutile)
    groupe_to_bus: dict[int, dict] = {}
    for i, g in enumerate(groupes):
        if i < len(bus):
            groupe_to_bus[g] = {"busId": int(bus[i]["id"]),
                                "matricule": bus[i].get("matricule")}

    eleve_bus = {int(eid): groupe_to_bus[g]["busId"]
                 for eid, g in mapping.items()
                 if g in groupe_to_bus}

    n_lies = 0
    if eleve_bus:
        try:
            n_lies = await assigner_bus_bulk(eleve_bus)
        except Exception as exc:
            logger.warning("[MS6] Propagation busId échouée (%s)", exc)

    manque = max(0, k - len(bus))
    if manque:
        logger.warning("[MS6] Flotte insuffisante : %d groupes mais %d bus actifs — %d groupe(s) sans bus",
                       k, len(bus), manque)
    logger.info("[MS6] Liaison groupe↔bus : %d élèves liés, %d/%d groupes couverts",
                n_lies, len(groupe_to_bus), k)
    return {"groupe_to_bus": {str(g): v for g, v in groupe_to_bus.items()},
            "n_lies": n_lies, "k": k, "n_bus_actifs": len(bus), "manque_bus": manque}
