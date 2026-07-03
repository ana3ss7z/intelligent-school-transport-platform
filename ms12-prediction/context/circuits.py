"""
Table statique des circuits scolaires de Meknès — source des features structurelles.

En production, ces attributs viennent d'une **table de configuration** (ici en dur, migrable en base) :
- arrêts (coordonnées réelles, cohérentes avec html_tests/map-gps.html),
- `nb_feux` (nombre de feux du circuit), `traverse_oued` (goulot d'étranglement),
- `nb_arrets_restants` déduit de la position dans le circuit.

Partagé par `dataset.py` (génération) et `main.py` (service) → une seule source de vérité.
"""
ECOLE = {"nom": "Al Massira", "lat": 33.893, "lng": -5.5455}

CIRCUITS = {
    1: {"nom": "Médina → École", "traverse_oued": 1, "nb_feux": 9, "arrets": [
        {"nom": "Médina",  "lat": 33.8935, "lng": -5.5547},
        {"nom": "Hamria",  "lat": 33.8978, "lng": -5.5489},
        {"nom": "Zitoune", "lat": 33.9012, "lng": -5.5523},
        {"nom": "Wislane", "lat": 33.9067, "lng": -5.5456},
    ]},
    2: {"nom": "Ismailia → École", "traverse_oued": 0, "nb_feux": 6, "arrets": [
        {"nom": "Ismailia",  "lat": 33.8876, "lng": -5.5612},
        {"nom": "Mellah",    "lat": 33.8901, "lng": -5.5598},
        {"nom": "Sidi Baba", "lat": 33.8845, "lng": -5.5534},
        {"nom": "Ain Karma", "lat": 33.8712, "lng": -5.5312},
    ]},
    3: {"nom": "Al Manzeh → École", "traverse_oued": 1, "nb_feux": 11, "arrets": [
        {"nom": "Al Manzeh", "lat": 33.8756, "lng": -5.5401},
        {"nom": "Riad",      "lat": 33.8834, "lng": -5.5378},
        {"nom": "Sidi Said", "lat": 33.8956, "lng": -5.5445},
        {"nom": "Borj",      "lat": 33.8923, "lng": -5.5689},
    ]},
}


def routes_circuit(circuit: dict, moment: str) -> list[dict]:
    """Arrêts ordonnés selon le sens : matin (quartiers→école) / soir (école→quartiers)."""
    arrets = circuit["arrets"]
    if moment == "matin":
        return arrets + [ECOLE]
    return [ECOLE] + list(reversed(arrets))


def n_legs(circuit: dict) -> int:
    """Nombre de tronçons d'un circuit (points - 1)."""
    return len(circuit["arrets"])   # arrets + école = len+1 points → len tronçons


def circuit_attrs(circuit_id: int) -> dict:
    """Attributs structurels statiques d'un circuit (feux, oued)."""
    c = CIRCUITS.get(int(circuit_id))
    if not c:
        return {"nb_feux": 8, "traverse_oued": 0}
    return {"nb_feux": c["nb_feux"], "traverse_oued": c["traverse_oued"]}


def nb_arrets_restants(circuit_id: int, leg_id: int) -> int:
    """Arrêts restant à desservir après le tronçon courant."""
    c = CIRCUITS.get(int(circuit_id))
    if not c:
        return 0
    return max(0, n_legs(c) - 1 - int(leg_id))
