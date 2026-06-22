#!/usr/bin/env python3
"""
Simulateur de Bus — Transport Scolaire Meknès
==============================================
Simule 3 bus parcourant de vrais trajets routiers à Meknès.

Architecture :
  1. Login MS7 via Gateway → obtient JWT token
  2. Pour chaque bus : calcule trajet OSRM entre arrêts réels
  3. Publie chaque position GPS via POST /api/gps/position (Gateway)
  4. Les positions arrivent en temps réel sur le WebSocket MS3

Usage :
  pip install requests
  python bus_simulator.py
  python bus_simulator.py --interval 2   # toutes les 2 secondes
  python bus_simulator.py --loop         # tourne en boucle infinie
"""

import requests
import time
import math
import argparse
import threading
from datetime import datetime

# ─── Configuration ────────────────────────────────────────────────────────────

GATEWAY_URL  = "http://localhost:8080"
OSRM_URL     = "http://localhost:5000"
ADMIN_EMAIL  = "admin@transport.ma"
ADMIN_PASS   = "Admin123!"
INTERVAL_SEC = 3      # secondes entre chaque position publiée
VITESSE_KMH  = 40.0   # vitesse simulée des bus

# ─── Arrêts réels de Meknès ───────────────────────────────────────────────────
# Chaque bus a son propre circuit entre quartiers réels

BUS_CIRCUITS = {
    1: {
        "nom": "Circuit Médina → Marjane",
        "arrets": [
            {"nom": "Médina",           "lat": 33.8935, "lng": -5.5547},
            {"nom": "Hamria",           "lat": 33.8978, "lng": -5.5489},
            {"nom": "Zitoune",          "lat": 33.9012, "lng": -5.5523},
            {"nom": "Wislane",          "lat": 33.9067, "lng": -5.5456},
            {"nom": "Marjane",          "lat": 33.8821, "lng": -5.5234},
        ]
    },
    2: {
        "nom": "Circuit Ismailia → Nouzhat",
        "arrets": [
            {"nom": "Ismailia",         "lat": 33.8876, "lng": -5.5612},
            {"nom": "Mellah",           "lat": 33.8901, "lng": -5.5598},
            {"nom": "Sidi Baba",        "lat": 33.8845, "lng": -5.5534},
            {"nom": "Ain Karma",        "lat": 33.8712, "lng": -5.5312},
            {"nom": "Nouzhat",          "lat": 33.8789, "lng": -5.5267},
        ]
    },
    3: {
        "nom": "Circuit Al Manzeh → Hay Salam",
        "arrets": [
            {"nom": "Al Manzeh",        "lat": 33.8756, "lng": -5.5401},
            {"nom": "Riad",             "lat": 33.8834, "lng": -5.5378},
            {"nom": "Sidi Said",        "lat": 33.8956, "lng": -5.5445},
            {"nom": "Borj Moulay Omar", "lat": 33.8923, "lng": -5.5689},
            {"nom": "Hay Salam",        "lat": 33.8698, "lng": -5.5478},
        ]
    }
}

# ─── Auth ─────────────────────────────────────────────────────────────────────

def get_token() -> str:
    """Login via Gateway MS8 → MS7 → retourne JWT token."""
    print(f"[Auth] Login {ADMIN_EMAIL} via Gateway...")
    try:
        resp = requests.post(
            f"{GATEWAY_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "motDePasse": ADMIN_PASS},
            timeout=10
        )
        resp.raise_for_status()
        token = resp.json().get("token")
        if not token:
            raise ValueError(f"Token absent dans la réponse : {resp.json()}")
        print(f"[Auth] ✅ Token obtenu")
        return token
    except Exception as e:
        print(f"[Auth] ❌ Échec login : {e}")
        raise

# ─── OSRM ─────────────────────────────────────────────────────────────────────

def get_route_osrm(depart: dict, arrivee: dict) -> list[tuple[float, float]]:
    """
    Appelle OSRM pour obtenir le trajet réel entre deux points.
    Retourne une liste de (lat, lng) représentant les points du trajet.
    """
    url = (
        f"{OSRM_URL}/route/v1/driving/"
        f"{depart['lng']},{depart['lat']};"
        f"{arrivee['lng']},{arrivee['lat']}"
        f"?overview=full&geometries=geojson&steps=false"
    )

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != "Ok":
            print(f"  [OSRM] ⚠️  Code inattendu : {data.get('code')} — fallback ligne droite")
            return interpoler_ligne_droite(depart, arrivee)

        coords = data["routes"][0]["geometry"]["coordinates"]
        # OSRM retourne [lng, lat] → on inverse en (lat, lng)
        points = [(c[1], c[0]) for c in coords]
        print(f"  [OSRM] ✅ {len(points)} points de trajet")
        return points

    except requests.exceptions.ConnectionError:
        print(f"  [OSRM] ⚠️  OSRM non disponible — fallback ligne droite")
        return interpoler_ligne_droite(depart, arrivee)
    except Exception as e:
        print(f"  [OSRM] ⚠️  Erreur : {e} — fallback ligne droite")
        return interpoler_ligne_droite(depart, arrivee)


def interpoler_ligne_droite(depart: dict, arrivee: dict,
                             nb_points: int = 20) -> list[tuple[float, float]]:
    """Fallback si OSRM non disponible : interpolation linéaire."""
    points = []
    for i in range(nb_points + 1):
        t = i / nb_points
        lat = depart["lat"] + t * (arrivee["lat"] - depart["lat"])
        lng = depart["lng"] + t * (arrivee["lng"] - depart["lng"])
        points.append((lat, lng))
    return points

# ─── Calcul cap ───────────────────────────────────────────────────────────────

def calculer_cap(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calcule le cap (bearing) en degrés entre deux points GPS."""
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlng_r = math.radians(lng2 - lng1)

    x = math.sin(dlng_r) * math.cos(lat2_r)
    y = (math.cos(lat1_r) * math.sin(lat2_r)
         - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(dlng_r))

    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360

# ─── Publication GPS ──────────────────────────────────────────────────────────

def publier_position(token: str, bus_id: int,
                     lat: float, lng: float, cap: float) -> bool:
    """Publie une position GPS via Gateway → MS3."""
    try:
        resp = requests.post(
            f"{GATEWAY_URL}/api/gps/position",
            json={
                "cibleType": "BUS",
                "cibleId":   bus_id,
                "latitude":  round(lat, 6),
                "longitude": round(lng, 6),
                "vitesse":   VITESSE_KMH,
                "cap":       round(cap, 1),
                "precision": 5.0
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=5
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"  [Bus {bus_id}] ❌ Erreur publication : {e}")
        return False

# ─── Simulateur par bus ───────────────────────────────────────────────────────

def simuler_bus(bus_id: int, circuit: dict, token: str,
                interval: float, loop: bool):
    """
    Thread dédié à un bus.
    Parcourt tous les arrêts du circuit, publie chaque position.
    """
    nom_circuit = circuit["nom"]
    arrets      = circuit["arrets"]
    nb_arrets   = len(arrets)

    print(f"\n[Bus {bus_id}] 🚌 Démarrage — {nom_circuit}")
    print(f"[Bus {bus_id}] Arrêts : {' → '.join(a['nom'] for a in arrets)}")

    iteration = 0
    while True:
        iteration += 1
        if loop:
            print(f"\n[Bus {bus_id}] 🔄 Tour {iteration}")

        for i in range(nb_arrets - 1):
            depart  = arrets[i]
            arrivee = arrets[i + 1]

            print(f"[Bus {bus_id}] ➜ {depart['nom']} → {arrivee['nom']}")

            # Obtenir trajet OSRM (ou fallback ligne droite)
            points = get_route_osrm(depart, arrivee)

            # Publier chaque point du trajet
            for j, (lat, lng) in enumerate(points):
                cap = 0.0
                if j < len(points) - 1:
                    next_lat, next_lng = points[j + 1]
                    cap = calculer_cap(lat, lng, next_lat, next_lng)

                ok = publier_position(token, bus_id, lat, lng, cap)
                status = "✅" if ok else "❌"
                ts = datetime.now().strftime("%H:%M:%S")
                print(f"  [{ts}] Bus {bus_id} {status} ({lat:.5f}, {lng:.5f}) cap={cap:.0f}°")

                time.sleep(interval)

        print(f"[Bus {bus_id}] 🏁 Circuit terminé — {nom_circuit}")

        if not loop:
            break

        # Pause avant de recommencer
        print(f"[Bus {bus_id}] ⏸️  Pause 5s avant prochain tour...")
        time.sleep(5)

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Simulateur Bus Meknès — MS3 GPS")
    parser.add_argument("--interval", type=float, default=INTERVAL_SEC,
                        help=f"Secondes entre chaque position (défaut: {INTERVAL_SEC})")
    parser.add_argument("--loop", action="store_true",
                        help="Tourne en boucle infinie")
    parser.add_argument("--bus", type=int, choices=[1, 2, 3], default=None,
                        help="Simuler un seul bus (1, 2 ou 3)")
    args = parser.parse_args()

    print("=" * 60)
    print("  🚌 Simulateur Bus — Transport Scolaire Meknès")
    print("=" * 60)
    print(f"  Gateway : {GATEWAY_URL}")
    print(f"  OSRM    : {OSRM_URL}")
    print(f"  Interval: {args.interval}s | Loop: {args.loop}")
    print("=" * 60)

    # Login
    try:
        token = get_token()
    except Exception:
        print("❌ Impossible d'obtenir le token — vérifier MS7 et Gateway")
        return

    # Sélection des bus
    circuits = BUS_CIRCUITS
    if args.bus:
        circuits = {args.bus: BUS_CIRCUITS[args.bus]}

    # Lancer un thread par bus
    threads = []
    for bus_id, circuit in circuits.items():
        t = threading.Thread(
            target=simuler_bus,
            args=(bus_id, circuit, token, args.interval, args.loop),
            daemon=True
        )
        threads.append(t)
        t.start()
        time.sleep(0.5)  # décalage léger entre les démarrages

    # Attendre tous les threads
    for t in threads:
        t.join()

    print("\n✅ Simulation terminée")


if __name__ == "__main__":
    main()
