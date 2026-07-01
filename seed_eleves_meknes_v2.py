#!/usr/bin/env python3
"""
Seeding v2 — 300 élèves de Meknès, données réalistes pour la data science
=========================================================================
Améliorations vs v1 :
  • Destination commune : un ÉTABLISSEMENT scolaire central (les bus convergent vers lui).
  • Structure multi-échelle : ZONES résidentielles -> SECTEURS (poches denses : lotissements,
    résidences) au lieu de simples « blobs » uniformes.
  • Séparation géographique réaliste : corridor de l'oued Boufekrane + ceinture agricole / périph.
    => de vrais « trous » entre zones (silhouette interprétable, clusters distincts).
  • Bruit réaliste : ~5 % d'élèves « dispersés » (péri-urbain) -> outliers pour DBSCAN/HDBSCAN.
  • Attributs enrichis : quartier, zone, secteur (vérité terrain multi-niveau), niveau scolaire,
    école assignée, distance à l'école.

Sorties :
  python seed_eleves_meknes_v2.py            -> CSV (ms6-clustering/data) + SQL + school.json
  python seed_eleves_meknes_v2.py --analyse  -> diagnostic structure (silhouette / k / bruit)
  python seed_eleves_meknes_v2.py --run      -> insertion DB (psycopg2, colonnes du schéma)
"""
import random, math, argparse, json, csv, os
from datetime import datetime
from collections import Counter

DB_HOST, DB_PORT, DB_NAME = "localhost", 5432, "transport_scolaire"
DB_USER, DB_PASS = "transport_user", "transport_pass"
TOTAL_ELEVES = 300
NOISE_FRAC = 0.05                       # part d'élèves dispersés (péri-urbain)
SEED = 42

# Établissement scolaire (destination commune) — centre de Meknès, rive est de l'oued
ECOLE = {"nom": "Groupe Scolaire Al Massira — Meknès", "lat": 33.8930, "lng": -5.5455}

# Corridor de l'oued Boufekrane (séparation médina / ville nouvelle) : ~longitude, demi-largeur (deg)
OUED_LON, OUED_BUFFER = -5.5585, 0.0016     # ~150 m de part et d'autre : zone non résidentielle

M_LAT = 111_320.0                            # mètres par degré de latitude

def m_lng(lat):                              # mètres par degré de longitude à cette latitude
    return 111_320.0 * math.cos(math.radians(lat))

# ── Structure : ZONES (séparées) -> SECTEURS (poches denses) ────────────────
# Chaque secteur : (quartier, nom, lat, lng, sigma_m, poids)
ZONES = {
    "Medina-Ouest": [          # rive ouest de l'oued : vieille ville dense
        ("Medina",   "Médina Sud",      33.8928, -5.5662, 110, 16),
        ("Medina",   "Médina Nord",     33.8975, -5.5648,  95, 14),
        ("Zitoune",  "Zitoune",         33.9010, -5.5612, 100, 13),
        ("Mellah",   "Mellah",          33.8902, -5.5618,  85, 11),
    ],
    "Hamria-Centre": [         # rive est : ville nouvelle, autour de l'école
        ("Hamria",    "Hamria Centre",  33.8972, -5.5492, 110, 18),
        ("Hamria",    "Hamria Gare",    33.8948, -5.5430,  95, 14),
        ("Sidi Baba", "Sidi Baba",      33.8895, -5.5505,  90, 13),
        ("Sidi Said", "Sidi Said",      33.9005, -5.5455, 100, 12),
    ],
    "Sud-Marjane": [           # sud : lotissements récents, plus aérés
        ("Marjane",   "Marjane 1",      33.8812, -5.5300, 120, 16),
        ("Marjane",   "Marjane 2",      33.8782, -5.5258, 105, 12),
        ("Riad",      "Riad",           33.8840, -5.5360, 110, 14),
        ("Al Manzeh", "Al Manzeh",      33.8762, -5.5388, 100, 12),
    ],
    "SudEst-AinKarma": [       # sud-est : périphérie, densité moindre
        ("Ain Karma", "Ain Karma Haut", 33.8722, -5.5325, 130, 14),
        ("Ain Karma", "Ain Karma Bas",  33.8695, -5.5378, 120, 11),
        ("Nouzhat",   "Nouzhat",        33.8765, -5.5262, 110, 12),
    ],
    "Nord-Wislane": [          # nord : Wislane, séparé par ceinture agricole
        ("Wislane",   "Wislane Est",    33.9068, -5.5452, 120, 13),
        ("Wislane",   "Wislane Ouest",  33.9052, -5.5520, 110, 10),
    ],
    "Sud-HaySalam": [          # sud lointain : Hay Salam + Borj
        ("Hay Salam",        "Hay Salam",  33.8688, -5.5470, 120, 12),
        ("Borj Moulay Omar", "Borj M.O.",  33.8712, -5.5552, 110, 10),
        ("Ismailia",         "Ismailia",   33.8852, -5.5588, 100, 11),
    ],
}

PRENOMS_G = ["Mohamed","Ahmed","Youssef","Omar","Ali","Hassan","Hamza","Anas","Bilal","Ibrahim",
    "Khalid","Rachid","Samir","Tarik","Karim","Mehdi","Nabil","Adil","Zakaria","Soufiane",
    "Ilyas","Ayoub","Othmane","Abdellah","Abdelkarim"]
PRENOMS_F = ["Fatima","Khadija","Aisha","Maryam","Zineb","Sara","Nadia","Hajar","Salma","Imane",
    "Dounia","Layla","Houda","Samira","Nora","Yasmine","Rania","Hind","Loubna","Soukaina",
    "Ghita","Kawtar","Meriem","Oumaima","Chaimae"]
NOMS = ["Benali","Benmoussa","Alaoui","Idrissi","Hassani","Benkirane","Tazi","Filali","Chaoui",
    "Bensouda","Amrani","Ziani","Berrada","Benomar","Sqalli","Ouazzani","Lahlou","Chraibi",
    "Benabdallah","Naciri","Rhazi","Belkadi","Mansouri","Kettani","Benjelloun","Benbrahim",
    "Senhaji","Rifai","Benhaddou","Tahiri","Kasmi","Lamrani","Bouazza","Bennouna","Sebbata",
    "Ghali","Fassi","Drissi","Mernissi","Benabdeljalil"]
NIVEAUX = [("Primaire", 0.45), ("Collège", 0.35), ("Lycée", 0.20)]


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def in_oued(lat, lon):
    return abs(lon - OUED_LON) < OUED_BUFFER


def gauss_point(lat, lng, sigma_m):
    """Point gaussien isotrope autour d'un centre, en degrés."""
    dx = random.gauss(0, sigma_m)          # est-ouest (m)
    dy = random.gauss(0, sigma_m)          # nord-sud  (m)
    return lat + dy / M_LAT, lng + dx / m_lng(lat)


def choisir_niveau():
    r, c = random.uniform(0, 1), 0
    for niv, w in NIVEAUX:
        c += w
        if r <= c:
            return niv
    return NIVEAUX[-1][0]


def generer_eleves(nb=TOTAL_ELEVES):
    random.seed(SEED)
    secteurs = [(z, *s) for z, lst in ZONES.items() for s in lst]
    poids = [s[5] for s in secteurs]
    total_w = sum(poids)
    n_noise = int(round(nb * NOISE_FRAC))
    n_struct = nb - n_noise

    eleves = []
    # --- élèves structurés (dans les secteurs denses) ---
    for _ in range(n_struct):
        r, cum = random.uniform(0, total_w), 0
        sec = secteurs[-1]
        for s in secteurs:
            cum += s[5]
            if r <= cum:
                sec = s; break
        zone, quartier, nom_sec, lat0, lng0, sigma, _ = sec
        for _try in range(20):
            lat, lng = gauss_point(lat0, lng0, sigma)
            if not in_oued(lat, lng):
                break
        eleves.append(_make(lat, lng, quartier, zone, nom_sec))

    # --- élèves dispersés (péri-urbain : bruit réaliste) ---
    lat_lo, lat_hi = 33.8660, 33.9090
    lng_lo, lng_hi = -5.5740, -5.5210
    for _ in range(n_noise):
        for _try in range(50):
            lat = random.uniform(lat_lo, lat_hi)
            lng = random.uniform(lng_lo, lng_hi)
            if in_oued(lat, lng):
                continue
            # « dispersé » = loin de tout centre de secteur (> 350 m)
            if min(haversine_m(lat, lng, s[3], s[4]) for s in secteurs) > 350:
                break
        eleves.append(_make(lat, lng, "Dispersé", "Périurbain", "Dispersé"))

    random.shuffle(eleves)
    for i, e in enumerate(eleves, 1):       # id = ordre d'insertion (= identity SQL)
        e["id"] = i
    return eleves


def _make(lat, lng, quartier, zone, secteur):
    est_g = random.random() > 0.5
    return {
        "nom": random.choice(NOMS),
        "prenom": random.choice(PRENOMS_G if est_g else PRENOMS_F),
        "latitude": round(lat, 6), "longitude": round(lng, 6),
        "quartier": quartier, "zone": zone, "secteur": secteur,
        "niveau": choisir_niveau(),
        "ecole_nom": ECOLE["nom"], "ecole_lat": ECOLE["lat"], "ecole_lng": ECOLE["lng"],
        "distance_ecole_m": round(haversine_m(lat, lng, ECOLE["lat"], ECOLE["lng"]), 1),
    }


# ── Sorties ─────────────────────────────────────────────────────────────────
COLS = ["id","nom","prenom","latitude","longitude","quartier","zone","secteur",
        "niveau","ecole_nom","ecole_lat","ecole_lng","distance_ecole_m"]

def ecrire_csv(eleves, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for e in eleves:
            w.writerow({k: e[k] for k in COLS})


def ecrire_sql(eleves, path):
    lines = ["-- Seeding v2 — 300 élèves Meknès (données réalistes)",
             f"-- Généré le {datetime.now():%Y-%m-%d %H:%M:%S}", "BEGIN;", "",
             "-- TRUNCATE TABLE eleves RESTART IDENTITY CASCADE;", "",
             "INSERT INTO eleves (nom, prenom, latitude, longitude, parent_id, groupe_id, statut_presence)",
             "VALUES"]
    rows = [f"  ('{e['nom']}', '{e['prenom']}', {e['latitude']}, {e['longitude']}, NULL, NULL, false)"
            for e in eleves]
    lines.append(",\n".join(rows) + ";")
    lines += ["", "COMMIT;", f"-- Total : {len(eleves)} élèves"]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def ecrire_school(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(ECOLE, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def analyser(eleves):
    """Diagnostic de structure : silhouette / k / bruit (nécessite scikit-learn)."""
    import numpy as np
    from sklearn.cluster import KMeans, DBSCAN
    from sklearn.metrics import silhouette_score
    from sklearn.neighbors import NearestNeighbors
    lat = np.array([e["latitude"] for e in eleves]); lon = np.array([e["longitude"] for e in eleves])
    lat0, lon0 = lat.mean(), lon.mean()
    X = np.column_stack([np.radians(lon-lon0)*6371000*math.cos(math.radians(lat0)),
                         np.radians(lat-lat0)*6371000])
    print(f"\nEmprise : {np.ptp(X[:,0]):.0f} x {np.ptp(X[:,1]):.0f} m | N={len(eleves)}")
    print("Silhouette par k (espace métrique) :")
    for k in range(2, 11):
        lab = KMeans(k, random_state=42, n_init=10).fit_predict(X)
        print(f"  k={k:2d} : silhouette={silhouette_score(X, lab):.3f}")
    nn = NearestNeighbors(n_neighbors=5).fit(X); d,_ = nn.kneighbors(X)
    eps = float(np.percentile(np.sort(d[:,-1]), 92))
    lab = DBSCAN(eps=eps, min_samples=5).fit_predict(X)
    nclu = len(set(lab)) - (1 if -1 in lab else 0)
    print(f"DBSCAN (eps≈{eps:.0f} m) : {nclu} clusters, {(lab==-1).sum()} bruit")
    print("Quartiers :", dict(Counter(e["quartier"] for e in eleves)))
    print("Zones     :", dict(Counter(e["zone"] for e in eleves)))
    print("Niveaux   :", dict(Counter(e["niveau"] for e in eleves)))
    print(f"Distance école : médiane={np.median([e['distance_ecole_m'] for e in eleves]):.0f} m, "
          f"max={max(e['distance_ecole_m'] for e in eleves):.0f} m")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--analyse", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--nb", type=int, default=TOTAL_ELEVES)
    args = ap.parse_args()

    eleves = generer_eleves(args.nb)
    print(f"{len(eleves)} élèves générés (dont ~{int(args.nb*NOISE_FRAC)} dispersés).")

    if args.analyse:
        analyser(eleves); return

    root = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(root, "ms6-clustering", "data", "eleves_meknes.csv")
    ecrire_csv(eleves, csv_path)
    ecrire_school(os.path.join(root, "ms6-clustering", "data", "school.json"))
    ecrire_sql(eleves, os.path.join(root, "seed_eleves_meknes_v2.sql"))
    print(f"CSV  -> {csv_path}")
    print(f"SQL  -> seed_eleves_meknes_v2.sql")
    print(f"JSON -> ms6-clustering/data/school.json")

    if args.run:
        try:
            import psycopg2
        except ImportError:
            print("pip install psycopg2-binary"); return
        conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASS)
        cur = conn.cursor()
        for e in eleves:
            cur.execute("INSERT INTO eleves (nom,prenom,latitude,longitude,parent_id,groupe_id,statut_presence)"
                        " VALUES (%s,%s,%s,%s,NULL,NULL,false)",
                        (e["nom"], e["prenom"], e["latitude"], e["longitude"]))
        conn.commit(); cur.close(); conn.close()
        print(f"{len(eleves)} élèves insérés en base.")


if __name__ == "__main__":
    main()
