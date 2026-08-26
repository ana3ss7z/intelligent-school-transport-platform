#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recette finale — Phase 2 : contrats HTTP et RBAC contre la stack VIVANTE.

Vérifie, endpoint par endpoint et rôle par rôle, le code HTTP réellement obtenu,
et non celui que la documentation annonce. Trois sections :

  A. Les 11 écarts relevés à la lecture du code (chacun une assertion nommée).
  B. La matrice RBAC : chaque @PreAuthorize / dépendance FastAPI confrontée aux
     rôles NON autorisés (attendu 403). Les cas autorisés en écriture ne sont pas
     exécutés — cette phase reste en lecture seule (voir NOTE ci-dessous).
  C. Absence de jeton : Java répond 401, Python 403 (HTTPBearer). On l'asserte
     PAR PILE, jamais globalement.

NOTE écriture : la seule écriture est l'assertion A3 (auto-promotion ADMIN via
/register), qui crée un compte `recette.escalade@transport.ma`. Il est supprimé
en fin de script s'il a été créé.

Prérequis : stack complète lancée + comptes_utilisateurs.json à la racine.
Usage     : python scripts/recette/contrats.py
Sortie    : tableau Markdown sur stdout + scripts/recette/resultats/contrats.json
Exit      : 0 si aucun écart INATTENDU, 2 sinon.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

import requests

# La console Windows est en cp1252 : sans cela, le premier caractère accentué tue le script.
for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

RACINE = pathlib.Path(__file__).resolve().parents[2]
SORTIE = RACINE / "scripts" / "recette" / "resultats" / "contrats.json"

GW = "http://localhost:8080"
DIRECT = {  # accès direct aux services, hors passerelle
    "ms1": "http://localhost:8081",
    "ms2": "http://localhost:8082",
    "ms3": "http://localhost:8083",
    "ms4": "http://localhost:8084",
    "ms5": "http://localhost:8085",
    "ms6": "http://localhost:8086",
    "ms7": "http://localhost:8087",
    "ms12": "http://localhost:8088",
    "ms9": "http://localhost:8089",
    "ms10": "http://localhost:8090",
    "ms11": "http://localhost:8091",
    "ms13": "http://localhost:8092",
}

ADMIN = {"email": "admin@transport.ma", "motDePasse": "Admin123!"}
PAUSE = 0.07  # le limiteur de la passerelle est à 20 req/s — on s'auto-bride

resultats: list[dict] = []
_ecarts = 0


def note(section: str, nom: str, attendu, obtenu, ok: bool, commentaire: str = "") -> bool:
    """Enregistre une assertion. `attendu` peut être un int, une liste ou un texte."""
    global _ecarts
    _ecarts += (not ok)
    resultats.append({
        "section": section, "nom": nom, "attendu": attendu,
        "obtenu": obtenu, "ok": ok, "commentaire": commentaire,
    })
    marque = "OK  " if ok else "ECART"
    print(f"  [{marque}] {nom} — attendu {attendu}, obtenu {obtenu}"
          + (f"  ({commentaire})" if commentaire else ""))
    return ok


def appel(methode: str, url: str, jeton: str | None = None, **kw) -> int:
    """Renvoie le code HTTP, ou 0 si le service est injoignable."""
    time.sleep(PAUSE)
    en_tetes = {"Authorization": f"Bearer {jeton}"} if jeton else {}
    en_tetes.update(kw.pop("headers", {}))
    try:
        return requests.request(methode, url, headers=en_tetes, timeout=30, **kw).status_code
    except Exception:
        return 0


def corps(methode: str, url: str, jeton: str | None = None, **kw):
    time.sleep(PAUSE)
    en_tetes = {"Authorization": f"Bearer {jeton}"} if jeton else {}
    try:
        r = requests.request(methode, url, headers=en_tetes, timeout=30, **kw)
        return r.status_code, (r.json() if r.content else None)
    except Exception as e:
        return 0, str(e)


def connexion(email: str, mdp: str):
    time.sleep(PAUSE)
    r = requests.post(f"{GW}/api/auth/login", json={"email": email, "motDePasse": mdp}, timeout=20)
    if r.status_code != 200:
        raise SystemExit(f"Connexion impossible pour {email} : HTTP {r.status_code} — {r.text[:200]}")
    return r.json()


def main() -> int:
    print("\n=== Recette Phase 2 — contrats & RBAC ===\n")

    comptes = json.loads((RACINE / "comptes_utilisateurs.json").read_text(encoding="utf-8"))
    p1, p2 = comptes["parents"][0], comptes["parents"][1]

    # chauffeur : le CSV porte les comptes chauffeur
    import csv
    with (RACINE / "comptes_utilisateurs.csv").open(encoding="utf-8-sig") as f:
        chauffeurs = [l for l in csv.DictReader(f) if l["role"] == "CHAUFFEUR"]
    ch = chauffeurs[0]

    a = connexion(ADMIN["email"], ADMIN["motDePasse"])
    c = connexion(ch["email"], ch["motDePasse"])
    u1 = connexion(p1["email"], p1["motDePasse"])
    u2 = connexion(p2["email"], p2["motDePasse"])
    TA, TC, TP1, TP2 = a["token"], c["token"], u1["token"], u2["token"]
    print(f"Jetons obtenus — ADMIN #{a['userId']} · CHAUFFEUR #{c['userId']} "
          f"· PARENT #{u1['userId']} · PARENT tiers #{u2['userId']}\n")

    # ══════════════════════════════════════════════════════════════════
    print("── Section A — les 11 écarts relevés dans le code ──")

    # A1/A2 — la route interne de MS13 ne doit pas être joignable par la passerelle
    note("A", "A1 · GET :8080/api/parametres/internal (non routée)",
         404, appel("GET", f"{GW}/api/parametres/internal", TA),
         appel("GET", f"{GW}/api/parametres/internal", TA) == 404,
         "la protection est le routage, pas un rôle")

    s, b = corps("GET", f"{DIRECT['ms13']}/api/parametres/internal")
    secrets_en_clair = isinstance(b, dict) and any(
        isinstance(v, str) and v and not v.startswith("•") for k, v in b.items() if "key" in k.lower())
    note("A", "A2 · GET :8092/api/parametres/internal (direct, permitAll)",
         "200 + secrets en clair", f"{s} / secrets_en_clair={secrets_en_clair}",
         s == 200, "sert MS9 ; jamais exposée au web")

    # A3 — /register accepte le rôle depuis le CORPS de la requête
    esc = {"nom": "Recette Escalade", "email": "recette.escalade@transport.ma",
           "motDePasse": "Escalade123!", "role": "ADMIN"}
    s_esc, b_esc = corps("POST", f"{GW}/api/auth/register", json=esc)
    role_obtenu = (b_esc or {}).get("role") if isinstance(b_esc, dict) else None
    if s_esc == 409 or (s_esc == 400 and role_obtenu is None):
        s_esc2, b_esc2 = corps("POST", f"{GW}/api/auth/login",
                               json={"email": esc["email"], "motDePasse": esc["motDePasse"]})
        role_obtenu = (b_esc2 or {}).get("role") if isinstance(b_esc2, dict) else None
    note("A", "A3 · POST /register avec role:\"ADMIN\" (auto-promotion)",
         "403/400 si contrôlé", f"HTTP {s_esc}, rôle attribué = {role_obtenu}",
         role_obtenu != "ADMIN",
         "ECART DE SECURITE si le rôle attribué est ADMIN : n'importe qui devient administrateur")

    # A3bis — l'escalade est-elle EXPLOITABLE, ou le rôle n'est-il qu'un écho ?
    # C'est la différence entre un champ mal recopié et une prise de contrôle.
    if role_obtenu == "ADMIN":
        s_tok, b_tok = corps("POST", f"{GW}/api/auth/login",
                             json={"email": esc["email"], "motDePasse": esc["motDePasse"]})
        jeton_intrus = (b_tok or {}).get("token") if isinstance(b_tok, dict) else None
        surfaces = {
            "GET /api/auth/users (tous les comptes)": ("GET", f"{GW}/api/auth/users"),
            "GET /api/eleves (300 domiciles GPS)": ("GET", f"{GW}/api/eleves"),
            "GET /api/notifications (journal complet)": ("GET", f"{GW}/api/notifications?page=0&size=5"),
            "GET /api/parametres/schema (MS13)": ("GET", f"{GW}/api/parametres/schema"),
            "POST /api/llm/admin/query (NL2SQL sur la base)": ("POST", f"{GW}/api/llm/admin/query"),
            "GET /api/trajets/actifs (toute la flotte)": ("GET", f"{GW}/api/trajets/actifs"),
        }
        ouvertes = []
        for libelle, (meth, url) in surfaces.items():
            kw = {"json": {"question": "combien d'élèves"}} if meth == "POST" else {}
            if appel(meth, url, jeton_intrus, **kw) == 200:
                ouvertes.append(libelle)
        note("A", "A3bis · Le compte auto-promu exerce-t-il réellement les pouvoirs ADMIN ?",
             "0 surface ouverte", f"{len(ouvertes)}/{len(surfaces)} surfaces ouvertes",
             len(ouvertes) == 0,
             "PRISE DE CONTROLE COMPLETE : " + " · ".join(ouvertes) if ouvertes else "")

    # A5 — pas de contrôle de propriété sur les élèves d'un autre parent
    enfant_tiers = p2["enfants"][0]["id"]
    s, b = corps("GET", f"{GW}/api/eleves/parent/{u2['userId']}", TP1)
    fuite = s == 200 and isinstance(b, list) and len(b) > 0
    note("A", "A5 · PARENT lit /api/eleves/parent/{autre_parent}",
         "403 si contrôle de propriété", f"HTTP {s}, {len(b) if isinstance(b, list) else '-'} élève(s)",
         not fuite, "ECART : aucun contrôle de propriété, un parent lit la fratrie d'autrui")

    # A6 — idem sur les positions GPS d'un élève tiers
    s_d = appel("GET", f"{GW}/api/gps/eleve/{enfant_tiers}/derniere", TP1)
    s_h = appel("GET", f"{GW}/api/gps/eleve/{enfant_tiers}/historique", TP1)
    # Ces deux routes ont été SUPPRIMÉES le 26/08 : elles servaient l'historique de
    # géolocalisation d'un élève à tout parent sans vérifier qu'il s'agissait du sien, et
    # aucun client ne les appelait. Un chemin inconnu ressort en 401 (la chaîne de sécurité
    # précède le routage) — c'est un refus au même titre qu'un 404.
    note("A", "A6 · PARENT lit le GPS d'un élève tiers (routes retirées)",
         "refus (401/403/404)", f"derniere={s_d}, historique={s_h}",
         s_d in (401, 403, 404) and s_h in (401, 403, 404),
         "ECART si 200 : géolocalisation de l'enfant d'une autre famille")

    # A2bis/ter — l'effectif complet n'est plus servi sans jeton (défaut critique n° 2).
    # Les services sans jeton utilisateur (MS5, MS6, MS12) passent désormais par
    # /internal/eleves, hors de /api/eleves/** donc non routée par la passerelle.
    s_ouvert = appel("GET", f"{DIRECT['ms2']}/api/eleves")
    note("A", "A2bis · GET :8082/api/eleves sans jeton (301 élèves + domiciles GPS)",
         401, s_ouvert, s_ouvert == 401,
         "c'est l'assertion Newman n° 13 ; elle doit repasser au vert")

    s_int_gw = appel("GET", f"{GW}/internal/eleves")
    s_int_direct = appel("GET", f"{DIRECT['ms2']}/internal/eleves")
    note("A", "A2ter · /internal/eleves — 404 par la passerelle, 200 en direct",
         "passerelle 404 / direct 200", f"passerelle={s_int_gw}, direct={s_int_direct}",
         s_int_gw == 404 and s_int_direct == 200,
         "la protection est le routage, pas un rôle — ne jamais router /internal/**")

    # A7 — routes internes MS2 : sans JWT en direct, JWT exigé via la passerelle
    d_sg = appel("GET", f"{DIRECT['ms2']}/api/eleves/sans-groupe")
    g_sg = appel("GET", f"{GW}/api/eleves/sans-groupe")
    note("A", "A7 · MS2 /sans-groupe — direct sans jeton vs passerelle sans jeton",
         "direct 200 / passerelle 401", f"direct={d_sg}, passerelle={g_sg}",
         d_sg == 200 and g_sg == 401,
         "la passerelle est la frontière ; le port de service est réputé privé")

    # A8 — MS1 routes internes permitAll
    d_act = appel("GET", f"{DIRECT['ms1']}/api/bus/actifs")
    d_chf = appel("GET", f"{DIRECT['ms1']}/api/bus/14/chauffeur")
    note("A", "A8 · MS1 /bus/actifs et /bus/{id}/chauffeur en direct sans jeton",
         "200 (permitAll interne)", f"actifs={d_act}, chauffeur={d_chf}",
         d_act == 200 and d_chf in (200, 404))

    # A9 — en-tête absent : Java 401 vs Python 403. Se mesure EN DIRECT :
    # via la passerelle, JwtAuthFilter rejette en 401 avant d'atteindre FastAPI.
    java_direct = appel("GET", f"{DIRECT['ms1']}/api/bus")
    py_direct = appel("POST", f"{DIRECT['ms12']}/api/eta/predict", json={})
    java_gw = appel("GET", f"{GW}/api/bus")
    py_gw = appel("POST", f"{GW}/api/eta/predict", json={})
    note("A", "A9 · En-tête absent — pile Java (401) vs pile Python (403), EN DIRECT",
         "java=401 / python=403", f"java={java_direct}, python={py_direct}",
         java_direct == 401 and py_direct == 403,
         "HTTPBearer de FastAPI répond 403 ; ne jamais asserter globalement")
    note("A", "A9bis · La passerelle uniformise à 401 (elle rejette avant le service)",
         "java=401 / python=401", f"java={java_gw}, python={py_gw}",
         java_gw == 401 and py_gw == 401,
         "conséquence : la distinction 401/403 n'est visible que sur le port du service")

    # A10 — /validate sans en-tête. La lecture du code laissait attendre 400
    # (@RequestHeader obligatoire) ; en réalité `anyRequest().authenticated()`
    # rejette AVANT que le contrôleur soit atteint. 401 est donc le bon code.
    val_direct = appel("GET", f"{DIRECT['ms7']}/api/auth/validate")
    val_gw = appel("GET", f"{GW}/api/auth/validate")
    note("A", "A10 · GET /api/auth/validate sans en-tête — direct et passerelle",
         "401 des deux côtés", f"direct={val_direct}, passerelle={val_gw}",
         val_direct == 401 and val_gw == 401,
         "la chaîne de sécurité précède @RequestHeader : le 400 supposé n'existe pas")

    # A11 — auto-suppression refusée
    s_self = appel("DELETE", f"{GW}/api/auth/users/{a['userId']}", TA)
    note("A", "A11 · DELETE /api/auth/users/{soi-même}", 409, s_self, s_self == 409)

    # ══════════════════════════════════════════════════════════════════
    print("\n── Section B — matrice RBAC (rôles NON autorisés → 403) ──")

    # Corps VALIDES : en Spring, @Valid s'exécute à la résolution des arguments,
    # donc AVANT @PreAuthorize. Un corps vide renvoie 400 et le contrôle de rôle
    # n'est jamais atteint — le test ne prouverait rien.
    CORPS = {
        f"{GW}/api/bus": {"matricule": "RECETTE-000", "capacite": 50, "statut": "ACTIF"},
        f"{GW}/api/eleves": {"nom": "Recette", "prenom": "Test", "latitude": 33.89, "longitude": -5.54},
        f"{GW}/api/incidents/1/statut": {"statut": "RESOLU"},
        f"{GW}/api/gps/position": {"cibleType": "BUS", "cibleId": 14, "latitude": 33.89,
                                   "longitude": -5.54, "vitesse": 40.0, "cap": 90.0, "precision": 5.0},
        f"{GW}/api/parametres": {"valeurs": {"ms11.seuil_vitesse_kmh": "90"}},
        f"{GW}/api/messages/diffusion?busId=14": {"destinataireId": None, "contenu": "recette"},
        f"{GW}/api/llm/chat": {"message": "test"},
        f"{GW}/api/llm/admin/query": {"question": "test"},
    }

    matrice = [
        # (nom, méthode, url, jeton, rôle testé, attendu)
        ("MS6 /production interdit au CHAUFFEUR", "POST", f"{GW}/api/clustering/production?appliquer=false", TC, "CHAUFFEUR", 403),
        ("MS6 /production interdit au PARENT", "POST", f"{GW}/api/clustering/production?appliquer=false", TP1, "PARENT", 403),
        ("MS5 /tournee interdit au PARENT (fuite domiciles)", "POST", f"{GW}/api/planification/tournee?groupeId=1&sens=matin", TP1, "PARENT", 403),
        ("MS5 /tournees interdit au PARENT", "POST", f"{GW}/api/planification/tournees?sens=matin", TP1, "PARENT", 403),
        ("MS5 /mes-enfants interdit à l'ADMIN", "POST", f"{GW}/api/planification/mes-enfants?sens=matin", TA, "ADMIN", 403),
        ("MS5 /mes-enfants interdit au CHAUFFEUR", "POST", f"{GW}/api/planification/mes-enfants?sens=matin", TC, "CHAUFFEUR", 403),
        ("MS9 /chat interdit à l'ADMIN (PARENT seulement)", "POST", f"{GW}/api/llm/chat", TA, "ADMIN", 403),
        ("MS9 /chat interdit au CHAUFFEUR", "POST", f"{GW}/api/llm/chat", TC, "CHAUFFEUR", 403),
        ("MS9 /admin/query interdit au PARENT", "POST", f"{GW}/api/llm/admin/query", TP1, "PARENT", 403),
        ("MS11 /anomalies/scan interdit au CHAUFFEUR", "GET", f"{GW}/api/analytique/anomalies/scan?limit=5", TC, "CHAUFFEUR", 403),
        ("MS11 /anomalies/scan interdit au PARENT", "GET", f"{GW}/api/analytique/anomalies/scan?limit=5", TP1, "PARENT", 403),
        ("MS13 /schema interdit au PARENT", "GET", f"{GW}/api/parametres/schema", TP1, "PARENT", 403),
        ("MS13 PUT interdit au CHAUFFEUR", "PUT", f"{GW}/api/parametres", TC, "CHAUFFEUR", 403),
        ("MS7 /users interdit au CHAUFFEUR", "GET", f"{GW}/api/auth/users", TC, "CHAUFFEUR", 403),
        ("MS7 /users interdit au PARENT", "GET", f"{GW}/api/auth/users", TP1, "PARENT", 403),
        ("MS1 /trajets/actifs interdit au CHAUFFEUR", "GET", f"{GW}/api/trajets/actifs", TC, "CHAUFFEUR", 403),
        ("MS1 /trajets/mon-actif interdit au PARENT", "GET", f"{GW}/api/trajets/mon-actif", TP1, "PARENT", 403),
        ("MS2 /eleves/bus/{id} interdit au PARENT", "GET", f"{GW}/api/eleves/bus/14", TP1, "PARENT", 403),
        ("MS2 PATCH présence interdit au PARENT", "PATCH", f"{GW}/api/eleves/1/presence?present=true", TP1, "PARENT", 403),
        ("MS3 POST position interdit au PARENT", "POST", f"{GW}/api/gps/position", TP1, "PARENT", 403),
        ("MS3 /gps/stats interdit au CHAUFFEUR", "GET", f"{GW}/api/gps/stats", TC, "CHAUFFEUR", 403),
        ("MS4 /notifications (journal) interdit au CHAUFFEUR", "GET", f"{GW}/api/notifications?page=0&size=5", TC, "CHAUFFEUR", 403),
        ("MS4 /notifications/stats interdit au PARENT", "GET", f"{GW}/api/notifications/stats", TP1, "PARENT", 403),
        ("MS4 /messages/diffusion interdit à l'ADMIN (CHAUFFEUR seul)", "POST", f"{GW}/api/messages/diffusion?busId=14", TA, "ADMIN", 403),
        ("MS4 /messages/ma-conversation interdit au PARENT", "GET", f"{GW}/api/messages/ma-conversation", TP1, "PARENT", 403),
        ("MS4 /messages/conversations interdit au CHAUFFEUR", "GET", f"{GW}/api/messages/conversations", TC, "CHAUFFEUR", 403),
        ("MS10 /incidents (liste) interdit au CHAUFFEUR", "GET", f"{GW}/api/incidents", TC, "CHAUFFEUR", 403),
        ("MS10 PATCH statut interdit au CHAUFFEUR", "PATCH", f"{GW}/api/incidents/1/statut", TC, "CHAUFFEUR", 403),
        ("MS1 POST /bus interdit au CHAUFFEUR", "POST", f"{GW}/api/bus", TC, "CHAUFFEUR", 403),
        ("MS2 POST /eleves interdit au CHAUFFEUR", "POST", f"{GW}/api/eleves", TC, "CHAUFFEUR", 403),
    ]
    for nom, meth, url, jeton, role, attendu in matrice:
        kw = {"json": CORPS.get(url, {})} if meth in ("POST", "PUT", "PATCH") else {}
        s = appel(meth, url, jeton, **kw)
        commentaire = ("400 = la validation du corps précède le contrôle de rôle"
                       if s == 400 else
                       "401 au lieu de 403 : refus d'autorisation déguisé en échec d'authentification"
                       if s == 401 else "")
        note("B", f"{nom} [{role}]", attendu, s, s == attendu, commentaire)

    # ── Accès légitimes en lecture (doivent PASSER) ──
    print("\n── Section B bis — accès légitimes en lecture (attendu 200) ──")
    legitimes = [
        ("ADMIN lit /api/bus", "GET", f"{GW}/api/bus", TA),
        ("ADMIN lit /api/eleves", "GET", f"{GW}/api/eleves", TA),
        ("ADMIN lit /api/auth/users", "GET", f"{GW}/api/auth/users", TA),
        ("ADMIN lit /api/notifications/stats", "GET", f"{GW}/api/notifications/stats", TA),
        ("ADMIN lit /api/parametres/schema", "GET", f"{GW}/api/parametres/schema", TA),
        ("ADMIN lit /api/trajets/actifs", "GET", f"{GW}/api/trajets/actifs", TA),
        ("ADMIN lit /api/incidents", "GET", f"{GW}/api/incidents", TA),
        ("CHAUFFEUR lit /api/eleves/bus/14", "GET", f"{GW}/api/eleves/bus/14", TC),
        ("CHAUFFEUR lit /api/trajets/mon-actif", "GET", f"{GW}/api/trajets/mon-actif", TC),
        ("CHAUFFEUR lit /api/messages/ma-conversation", "GET", f"{GW}/api/messages/ma-conversation", TC),
        ("CHAUFFEUR lit /api/notifications/mes-notifications", "GET", f"{GW}/api/notifications/mes-notifications", TC),
        ("PARENT lit /api/messages/parent", "GET", f"{GW}/api/messages/parent", TP1),
        ("PARENT lit /api/notifications/mes-notifications", "GET", f"{GW}/api/notifications/mes-notifications", TP1),
        ("PARENT lit /api/messages/non-lus", "GET", f"{GW}/api/messages/non-lus", TP1),
        ("PARENT lit /api/parametres", "GET", f"{GW}/api/parametres", TP1),
    ]
    for nom, meth, url, jeton in legitimes:
        s = appel(meth, url, jeton)
        note("Bbis", nom, "200/204", s, s in (200, 204))

    # ── Les endpoints « publics » des services Python ne le sont PAS via la passerelle ──
    print("\n── Section B ter — endpoints déclarés « Public » : direct vs passerelle ──")
    publics = [
        ("MS11 /api/analytique/live", DIRECT["ms11"], "/api/analytique/live?limit=3"),
        ("MS6 /api/clustering/health", DIRECT["ms6"], "/api/clustering/health"),
        ("MS12 /api/eta/health", DIRECT["ms12"], "/api/eta/health"),
        ("MS5 /api/planification/health", DIRECT["ms5"], "/api/planification/health"),
        ("MS9 /api/llm/health", DIRECT["ms9"], "/api/llm/health"),
        ("MS6 /api/clustering/quality", DIRECT["ms6"], "/api/clustering/quality"),
    ]
    for nom, base, chemin in publics:
        s_d = appel("GET", f"{base}{chemin}")
        s_g = appel("GET", f"{GW}{chemin}")
        note("Bter", f"{nom} — public en direct, fermé par la passerelle",
             "direct 200 / passerelle 401", f"direct={s_d}, passerelle={s_g}",
             s_d == 200 and s_g == 401,
             "la doc les annonce « Public » : vrai sur le port du service, FAUX via :8080")

    # ══════════════════════════════════════════════════════════════════
    print("\n── Section C — jeton invalide et limiteur de débit ──")

    s_faux = appel("GET", f"{GW}/api/bus", "jeton.bidon.invalide")
    note("C", "C1 · Jeton malformé sur la passerelle", 401, s_faux, s_faux == 401)

    # A4 — le limiteur. EN PARALLÈLE : en séquentiel, le temps d'aller-retour
    # (~40 ms) suffit à laisser le seau se remplir et rien ne se déclenche.
    print("  … saturation volontaire du limiteur, en parallèle (assertion A4)")
    from concurrent.futures import ThreadPoolExecutor

    def _login():
        try:
            return requests.post(f"{GW}/api/auth/login", json=ADMIN, timeout=15).status_code
        except Exception:
            return 0

    with ThreadPoolExecutor(max_workers=40) as ex:
        codes = list(ex.map(lambda _: _login(), range(40)))
    n429, n200 = codes.count(429), codes.count(200)
    note("A", "A4 · 40 connexions PARALLÈLES → limiteur /auth (5/s, burst 10)",
         "des 429", f"{n429} × 429 et {n200} × 200 sur 40", n429 > 0,
         "deux seaux empilés ; en SÉQUENTIEL rien ne se déclenche (test faussement rassurant)")

    time.sleep(3)

    def _bus(jeton):
        try:
            return requests.get(f"{GW}/api/bus", headers={"Authorization": f"Bearer {jeton}"},
                                timeout=15).status_code
        except Exception:
            return 0

    with ThreadPoolExecutor(max_workers=80) as ex:
        codes_b = list(ex.map(lambda _: _bus(TA), range(80)))
    note("A", "A4bis · 80 requêtes PARALLÈLES sur /api/bus (défaut 20/s, burst 40)",
         "des 429", f"{codes_b.count(429)} × 429 et {codes_b.count(200)} × 200 sur 80",
         codes_b.count(429) > 0, "le filtre par défaut s'applique à toutes les routes")

    print("  … pause de 5 s pour laisser le seau se remplir")
    time.sleep(5)

    # ── Nettoyage du compte d'escalade ──
    s, liste = corps("GET", f"{GW}/api/auth/users", TA)
    if s == 200 and isinstance(liste, list):
        for u in liste:
            if u.get("email") == esc["email"]:
                sd = appel("DELETE", f"{GW}/api/auth/users/{u['id']}", TA)
                print(f"\nNettoyage : compte d'escalade #{u['id']} supprimé (HTTP {sd})")
                break

    # ══════════════════════════════════════════════════════════════════
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps({
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(resultats), "ecarts": _ecarts, "assertions": resultats,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== {len(resultats) - _ecarts}/{len(resultats)} conformes · {_ecarts} écart(s) ===")
    print(f"Détail : {SORTIE}")
    if _ecarts:
        print("\nÉcarts (à qualifier : défaut à corriger, ou choix assumé à documenter) :")
        for r in resultats:
            if not r["ok"]:
                print(f"  • [{r['section']}] {r['nom']} — attendu {r['attendu']}, obtenu {r['obtenu']}")
                if r["commentaire"]:
                    print(f"      {r['commentaire']}")
    return 0 if _ecarts == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
