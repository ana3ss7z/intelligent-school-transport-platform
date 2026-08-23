"""
Banc de rejeu pour les RÈGLES LIVE de MS11 (`live_monitor.py`).

Pourquoi ce module existe
-------------------------
MS11 contient deux détecteurs de nature différente, et un seul était évalué :

- le **détecteur ML** (Isolation Forest) score des *trajets complets*, à la demande. Il a un
  benchmark à 4 détecteurs, un split temporel et des métriques gelées ;
- les **règles instantanées** de `live_monitor.observer()` tournent **en continu, sur chaque ping
  GPS**, et ce sont elles qui déclenchent les vraies alertes d'exploitation. Elles n'avaient
  **aucune métrique** — seulement un test de fumée binaire (« ça se déclenche ») et une mesure
  manuelle unique. Leurs quatre seuils (90 km/h · 5 min · 250 m · 2 pings) étaient posés à dire
  d'expert, sans qu'aucune courbe ne dise ce qu'on gagne ou perd en les déplaçant.

Ce module comble ce trou. Il ne modifie rien au service : `observer()` est une fonction pure à état
de module, donc rejouable hors ligne, sans RabbitMQ, sans backend et sans OSRM.

Le support n'est pas une géométrie de laboratoire
------------------------------------------------
On rejoue sur la **vraie tournée du groupe 1** telle que MS5 la produit — 753 points, 17 241 m,
35,99 min — la même fixture qui sert aux tests de parité ETA des deux applications Flutter. Les
événements (arrêt prolongé, excès de vitesse, déviation) sont **injectés à des instants connus**,
ce qui donne une vérité terrain exacte : on sait ce qui aurait dû être détecté, et quand.

    python replay.py            → rapport + data/live_rules_benchmark.json
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path

import live_monitor
from config import settings

# La fixture appartient à l'app chauffeur (tests de parité ETA) : on la partage plutôt que d'en
# fabriquer une seconde, qui divergerait.
FIXTURE = (Path(__file__).resolve().parent.parent
           / "frontend" / "chauffeur-mobile" / "test" / "fixtures" / "tournee_groupe1.json")

R_TERRE = 6371000.0


# ─────────────────────────────── Géométrie ───────────────────────────────────
def _haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dphi = math.radians(b[0] - a[0])
    dl = math.radians(b[1] - a[1])
    x = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_TERRE * math.asin(math.sqrt(x))


def _decaler(p: tuple[float, float], dx_m: float, dy_m: float) -> tuple[float, float]:
    """Décale un point de (dx, dy) mètres — est/nord — en projection équirectangulaire locale."""
    dlat = dy_m / (R_TERRE * math.pi / 180.0)
    dlng = dx_m / (R_TERRE * math.pi / 180.0 * math.cos(math.radians(p[0])))
    return (p[0] + dlat, p[1] + dlng)


class Polyligne:
    """Polyligne cumulée : permet d'échantillonner une position à une abscisse curviligne donnée."""

    def __init__(self, pts: list[tuple[float, float]]):
        self.pts = pts
        self.cumul = [0.0]
        for i in range(1, len(pts)):
            self.cumul.append(self.cumul[-1] + _haversine_m(pts[i - 1], pts[i]))
        self.longueur = self.cumul[-1]

    def position(self, s_m: float) -> tuple[tuple[float, float], tuple[float, float]]:
        """Retourne (point, vecteur unitaire de direction en mètres) à l'abscisse `s_m`."""
        s = max(0.0, min(self.longueur, s_m))
        i = 1
        while i < len(self.cumul) - 1 and self.cumul[i] < s:
            i += 1
        a, b = self.pts[i - 1], self.pts[i]
        seg = self.cumul[i] - self.cumul[i - 1]
        t = 0.0 if seg <= 1e-9 else (s - self.cumul[i - 1]) / seg
        p = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
        # direction locale, en mètres
        dy = (b[0] - a[0]) * R_TERRE * math.pi / 180.0
        dx = (b[1] - a[1]) * R_TERRE * math.pi / 180.0 * math.cos(math.radians(a[0]))
        n = math.hypot(dx, dy) or 1.0
        return p, (dx / n, dy / n)


# ─────────────────────────────── Scénarios ───────────────────────────────────
@dataclass
class Evenement:
    """Un fait injecté dans la trace, avec le type d'alerte qu'il DOIT provoquer."""
    genre: str                 # arret | vitesse | deviation
    debut_s: float
    duree_s: float
    attendu: str | None        # type d'alerte attendu, None = ne doit RIEN déclencher
    vitesse_kmh: float = 0.0
    ecart_m: float = 0.0
    libelle: str = ""


@dataclass
class Scenario:
    nom: str
    evenements: list[Evenement] = field(default_factory=list)
    bruit_m: float = 0.0
    cadence_s: float = 5.0
    vitesse_croisiere_kmh: float | None = None   # None = déduite de la tournée


@dataclass
class Trace:
    """Une trace GPS complète : positions, vitesses et instants."""
    pings: list[tuple[float, float, float, float]]   # (t, lat, lng, vitesse_kmh)
    scenario: Scenario


def construire_trace(poly: Polyligne, duree_plan_s: float, sc: Scenario, rng) -> Trace:
    """Fait rouler un bus le long de la tournée et y injecte les événements du scénario."""
    v_ms = (sc.vitesse_croisiere_kmh / 3.6) if sc.vitesse_croisiere_kmh else poly.longueur / duree_plan_s
    pings: list[tuple[float, float, float, float]] = []
    s = 0.0
    t = 0.0
    # On roule jusqu'au bout de la tournée, en tenant compte du temps figé par les arrêts.
    duree_arrets = sum(e.duree_s for e in sc.evenements if e.genre == "arret")
    t_max = duree_plan_s + duree_arrets + 60.0

    while t <= t_max and s < poly.longueur:
        immobile = any(e.genre == "arret" and e.debut_s <= t < e.debut_s + e.duree_s
                       for e in sc.evenements)
        p, direction = poly.position(s)

        # Déviation : on décale latéralement (perpendiculaire à la direction locale)
        dev = next((e for e in sc.evenements
                    if e.genre == "deviation" and e.debut_s <= t < e.debut_s + e.duree_s), None)
        if dev:
            nx, ny = -direction[1], direction[0]        # normale à gauche
            p = _decaler(p, nx * dev.ecart_m, ny * dev.ecart_m)

        if sc.bruit_m > 0:
            p = _decaler(p, rng.gauss(0, sc.bruit_m), rng.gauss(0, sc.bruit_m))

        vit = next((e.vitesse_kmh for e in sc.evenements
                    if e.genre == "vitesse" and e.debut_s <= t < e.debut_s + e.duree_s), None)
        if vit is None:
            vit = 0.0 if immobile else v_ms * 3.6

        pings.append((t, p[0], p[1], vit))
        if not immobile:
            s += v_ms * sc.cadence_s
        t += sc.cadence_s

    return Trace(pings, sc)


# ──────────────────────────────── Rejeu ──────────────────────────────────────
def _reinitialiser(bus_id: int, route: list[tuple[float, float]] | None) -> None:
    """Remet le monitor à zéro entre deux rejeux.

    On touche aux dictionnaires de module de `live_monitor` : c'est délibéré. Un banc d'essai a
    besoin de repartir d'un état vierge, et le service n'expose pas de réinitialisation — il n'en
    a pas besoin en production, où le processus vit aussi longtemps que la flotte.
    """
    live_monitor._state.pop(bus_id, None)
    live_monitor._routes.pop(bus_id, None)
    live_monitor.anomalies_live.clear()
    if route:
        live_monitor.set_route(bus_id, route)


def rejouer(trace: Trace, route: list[tuple[float, float]] | None,
            bus_id: int = 999, vitesse_du_payload: bool = True) -> list[dict]:
    """Rejoue une trace à travers `live_monitor.observer()` et retourne les alertes horodatées."""
    _reinitialiser(bus_id, route)
    alertes: list[dict] = []
    for (t, lat, lng, vit) in trace.pings:
        detections = live_monitor.observer(
            bus_id, lat, lng, vit if vitesse_du_payload else None, ts=t
        )
        for d in detections:
            alertes.append({"t": t, "type": d["type"], **{k: v for k, v in d.items()
                                                          if k not in ("busId", "timestamp", "type")}})
    return alertes


# ─────────────────────────────── Évaluation ──────────────────────────────────
def _plancher_theorique(e: Evenement, cadence_s: float) -> float:
    """Instant le plus tôt où la règle PEUT se déclencher — sert à séparer la latence
    intrinsèque à la règle (ce qu'on a choisi) de la latence d'implémentation."""
    if e.genre == "arret":
        return e.debut_s + settings.seuil_arret_min * 60.0
    if e.genre == "deviation":
        return e.debut_s + settings.deviation_pings_consecutifs * cadence_s
    return e.debut_s


def evaluer(trace: Trace, alertes: list[dict], tolerance_s: float = 120.0) -> dict:
    """Confronte les alertes à la vérité terrain du scénario."""
    sc = trace.scenario
    attendus = [e for e in sc.evenements if e.attendu]
    resultat = {"scenario": sc.nom, "n_pings": len(trace.pings),
                "duree_s": trace.pings[-1][0] if trace.pings else 0.0,
                "evenements": [], "fausses_alarmes": [], "n_alertes": len(alertes)}

    consommees: set[int] = set()
    for e in attendus:
        fin = e.debut_s + e.duree_s + tolerance_s
        trouvee = None
        for i, a in enumerate(alertes):
            if i in consommees or a["type"] != e.attendu:
                continue
            if e.debut_s <= a["t"] <= fin:
                trouvee = (i, a)
                break
        # Les répétitions du MÊME type dans la même fenêtre ne sont pas des fausses alarmes :
        # c'est un incident unique qui ré-alerte tous les `_ALERT_COOLDOWN_S`. On les compte à
        # part, parce que c'est ce que voit l'administration — et que c'est de la fatigue d'alerte.
        repetitions = 0
        if trouvee:
            consommees.add(trouvee[0])
            for i, a in enumerate(alertes):
                if i not in consommees and a["type"] == e.attendu and e.debut_s <= a["t"] <= fin:
                    consommees.add(i)
                    repetitions += 1
        plancher = _plancher_theorique(e, sc.cadence_s)
        resultat["evenements"].append({
            "libelle": e.libelle or e.genre,
            "attendu": e.attendu,
            "detecte": trouvee is not None,
            "t_debut_s": e.debut_s,
            "latence_s": round(trouvee[1]["t"] - e.debut_s, 1) if trouvee else None,
            "plancher_theorique_s": round(plancher - e.debut_s, 1),
            "surcout_s": round(trouvee[1]["t"] - plancher, 1) if trouvee else None,
            "alertes_repetees": repetitions,
        })

    for i, a in enumerate(alertes):
        if i not in consommees:
            resultat["fausses_alarmes"].append({"t": a["t"], "type": a["type"]})

    heures = max(1e-9, resultat["duree_s"] / 3600.0)
    resultat["fausses_alarmes_par_heure"] = round(len(resultat["fausses_alarmes"]) / heures, 2)
    resultat["n_detectes"] = sum(1 for e in resultat["evenements"] if e["detecte"])
    resultat["n_attendus"] = len(attendus)
    return resultat


# ───────────────────────────── Chargement ────────────────────────────────────
def charger_tournee() -> tuple[Polyligne, float, list[tuple[float, float]]]:
    d = json.loads(FIXTURE.read_text(encoding="utf-8"))
    pts = [(float(p[0]), float(p[1])) for p in d["geometrie"]]
    return Polyligne(pts), float(d["duree_min"]) * 60.0, pts


# ═══════════════════════════ Campagne de mesure ══════════════════════════════
def scenarios() -> list[Scenario]:
    """Les scénarios de la campagne. Chaque événement déclare ce qui DOIT (ou ne doit pas) sortir."""
    return [
        Scenario("normal", []),
        Scenario("normal_bruite_15m", [], bruit_m=15.0),
        Scenario("arrets_legitimes", [
            Evenement("arret", 300, 60, None, libelle="feu rouge / montee (1 min)"),
            Evenement("arret", 900, 120, None, libelle="arret eleve long (2 min)"),
            Evenement("arret", 1500, 240, None, libelle="embouteillage (4 min)"),
        ]),
        Scenario("panne_8min", [
            Evenement("arret", 600, 480, "ARRET_PROLONGE", libelle="panne (8 min)"),
        ]),
        Scenario("exces_vitesse", [
            Evenement("vitesse", 700, 20, "VITESSE_EXCESSIVE", vitesse_kmh=110.0,
                      libelle="pointe a 110 km/h"),
        ]),
        Scenario("deviation_franche_400m", [
            Evenement("deviation", 800, 150, "DEVIATION_ITINERAIRE", ecart_m=400.0,
                      libelle="detour de 400 m"),
        ]),
        Scenario("deviation_limite_260m", [
            Evenement("deviation", 800, 150, "DEVIATION_ITINERAIRE", ecart_m=260.0,
                      libelle="detour de 260 m (seuil 250)"),
        ]),
        Scenario("deviation_sous_seuil_150m", [
            Evenement("deviation", 800, 150, None, ecart_m=150.0,
                      libelle="rue parallele a 150 m, ne doit RIEN declencher"),
        ]),
        Scenario("outlier_gps_isole", [
            Evenement("deviation", 800, 5, None, ecart_m=600.0,
                      libelle="saut GPS d un seul ping (600 m)"),
        ]),
        # La règle de vitesse n'a AUCUN anti-rebond, contrairement à la déviation : un seul ping
        # aberrant suffit. Ce scénario n'attend donc rien, et toute alerte compte comme fausse.
        Scenario("pointe_vitesse_isolee", [
            Evenement("vitesse", 800, 5, None, vitesse_kmh=200.0,
                      libelle="ping GPS aberrant a 200 km/h (1 seul ping)"),
        ]),
    ]


def couverture_spatiale(poly: Polyligne, route: list[tuple[float, float]],
                        n_points: int = 120) -> list[dict]:
    """Part du parcours où un détour d'ampleur donnée SERAIT détecté.

    La règle mesure la distance au point le plus proche de **toute** la polyligne. Sur une tournée
    urbaine de 50 arrêts qui repasse dans le même quartier, un bus décalé de 400 m peut rester à
    moins de 250 m d'un **autre tronçon de sa propre tournée**. La sensibilité effective dépend
    donc de l'endroit, pas seulement de l'ampleur — et c'est ce que cette fonction chiffre.
    """
    lignes = []
    for nominal in (100, 150, 200, 250, 300, 400, 600, 800):
        mesures = []
        for k in range(n_points):
            s = poly.longueur * (k + 0.5) / n_points
            p, d = poly.position(s)
            nx, ny = -d[1], d[0]
            for signe in (1, -1):    # détour à gauche et à droite
                q = _decaler(p, signe * nx * nominal, signe * ny * nominal)
                mesures.append(live_monitor._dist_point_polyline_m(q, route))
        mesures.sort()
        n = len(mesures)
        detectes = sum(1 for m in mesures if m > settings.seuil_deviation_m)
        lignes.append({
            "detour_nominal_m": nominal,
            "ecart_mesure_median_m": round(mesures[n // 2], 1),
            "ecart_mesure_min_m": round(mesures[0], 1),
            "ecart_mesure_max_m": round(mesures[-1], 1),
            "part_parcours_detectee_%": round(100 * detectes / n, 1),
        })
    return lignes


def couverture_par_seuil(poly: Polyligne, route: list[tuple[float, float]],
                         detours=(200, 300, 400), n_points: int = 120) -> list[dict]:
    """Croise seuil de déviation et ampleur du détour : quelle part du parcours est couverte ?

    Se lit avec le balayage bruit×seuil : celui-ci donne le **coût** d'un seuil bas (fausses
    alarmes), celle-ci donne le **bénéfice** (couverture). Les deux ensemble permettent de choisir.
    """
    initial = settings.seuil_deviation_m
    lignes = []
    try:
        for seuil in (50, 80, 100, 120, 150, 200, 250, 300):
            settings.seuil_deviation_m = float(seuil)
            cov = {c["detour_nominal_m"]: c["part_parcours_detectee_%"]
                   for c in couverture_spatiale(poly, route, n_points)}
            lignes.append({"seuil_m": seuil, **{f"detour_{d}m_%": cov.get(d) for d in detours}})
    finally:
        settings.seuil_deviation_m = initial
    return lignes


def _rng():
    import random
    return random.Random(42)   # même bruit d'un scénario à l'autre : les colonnes restent comparables


def _campagne(poly, duree_plan_s, route) -> list[dict]:
    out = []
    for sc in scenarios():
        trace = construire_trace(poly, duree_plan_s, sc, _rng())
        out.append(evaluer(trace, rejouer(trace, route)))
    return out


BRUITS = (0.0, 5.0, 15.0, 30.0)


def _balayage_deviation(poly, duree_plan_s, route) -> list[dict]:
    """Détection vs fausses alarmes, en fonction du seuil de déviation ET du bruit GPS."""
    initial = settings.seuil_deviation_m
    lignes = []
    try:
        for seuil in (50, 100, 150, 200, 250, 300, 400, 500):
            settings.seuil_deviation_m = float(seuil)
            for bruit in BRUITS:
                # (a) trajet normal bruité : toute alerte est une fausse alarme
                sc_n = Scenario("normal", [], bruit_m=bruit)
                tr_n = construire_trace(poly, duree_plan_s, sc_n, _rng())
                ev_n = evaluer(tr_n, rejouer(tr_n, route))
                # (b) vrai détour de 300 m : doit être détecté
                sc_d = Scenario("detour300", [
                    Evenement("deviation", 800, 150, "DEVIATION_ITINERAIRE", ecart_m=300.0)
                ], bruit_m=bruit)
                tr_d = construire_trace(poly, duree_plan_s, sc_d, _rng())
                ev_d = evaluer(tr_d, rejouer(tr_d, route))
                lignes.append({
                    "seuil_m": seuil, "bruit_m": bruit,
                    "detour_300m_detecte": ev_d["n_detectes"] == 1,
                    "latence_s": ev_d["evenements"][0]["latence_s"],
                    "fausses_alarmes_h": ev_n["fausses_alarmes_par_heure"],
                })
    finally:
        settings.seuil_deviation_m = initial
    return lignes


def _balayage_antirebond(poly, duree_plan_s, route) -> list[dict]:
    """Ce que l'anti-rebond achète en fausses alarmes, et ce qu'il coûte en latence."""
    init_p, init_s = settings.deviation_pings_consecutifs, settings.seuil_deviation_m
    lignes = []
    try:
        settings.seuil_deviation_m = 100.0   # là où le bruit devient un adversaire réel
        for pings in (1, 2, 3, 4):
            settings.deviation_pings_consecutifs = pings
            tr_n = construire_trace(poly, duree_plan_s,
                                    Scenario("normal", [], bruit_m=30.0), _rng())
            ev_n = evaluer(tr_n, rejouer(tr_n, route))
            tr_d = construire_trace(poly, duree_plan_s, Scenario("detour300", [
                Evenement("deviation", 800, 150, "DEVIATION_ITINERAIRE", ecart_m=300.0)
            ], bruit_m=30.0), _rng())
            ev_d = evaluer(tr_d, rejouer(tr_d, route))
            lignes.append({
                "pings_consecutifs": pings,
                "fausses_alarmes_h": ev_n["fausses_alarmes_par_heure"],
                "detour_detecte": ev_d["n_detectes"] == 1,
                "latence_s": ev_d["evenements"][0]["latence_s"],
            })
    finally:
        settings.deviation_pings_consecutifs = init_p
        settings.seuil_deviation_m = init_s
    return lignes


def _balayage_arret(poly, duree_plan_s, route) -> list[dict]:
    """Seuil d'arrêt prolongé : où passe la frontière entre embouteillage et panne ?"""
    initial = settings.seuil_arret_min
    lignes = []
    try:
        for seuil in (1, 2, 3, 5, 8, 10):
            settings.seuil_arret_min = float(seuil)
            tr = construire_trace(poly, duree_plan_s, Scenario("arrets_mixtes", [
                Evenement("arret", 300, 60, None, libelle="feu (1 min)"),
                Evenement("arret", 700, 180, None, libelle="trafic (3 min)"),
                Evenement("arret", 1300, 480, "ARRET_PROLONGE", libelle="panne (8 min)"),
            ]), _rng())
            ev = evaluer(tr, rejouer(tr, route))
            lignes.append({
                "seuil_min": seuil,
                "panne_detectee": ev["n_detectes"] == 1,
                "latence_s": ev["evenements"][0]["latence_s"],
                "fausses_alarmes": len(ev["fausses_alarmes"]),
            })
    finally:
        settings.seuil_arret_min = initial
    return lignes


def main() -> None:
    poly, duree_plan_s, route = charger_tournee()

    print(f"[MS11] Tournee reelle : {len(route)} points | {poly.longueur:,.0f} m | "
          f"{duree_plan_s/60:.2f} min -> vitesse {poly.longueur/duree_plan_s*3.6:.1f} km/h")
    print(f"[MS11] Seuils en vigueur : vitesse {settings.seuil_vitesse_kmh} km/h | "
          f"arret {settings.seuil_arret_min} min | deviation {settings.seuil_deviation_m} m "
          f"sur {settings.deviation_pings_consecutifs} pings\n")

    camp = _campagne(poly, duree_plan_s, route)
    print("## Scenarios\n")
    print("| Scenario | Attendu | Detecte | Latence | Plancher | Repetitions | Fausses alarmes/h |")
    print("|---|---|:-:|--:|--:|--:|--:|")
    for r in camp:
        if r["evenements"]:
            for e in r["evenements"]:
                lat = f"{e['latence_s']:.0f} s" if e["latence_s"] is not None else "-"
                att = e["attendu"] or "aucune alerte"
                ok = ("OUI" if e["detecte"] else "NON") if e["attendu"] else \
                     ("OUI" if not r["fausses_alarmes"] else "NON")
                print(f"| {r['scenario']} | {att} | {ok} "
                      f"| {lat} | {e['plancher_theorique_s']:.0f} s "
                      f"| {e['alertes_repetees']} | {r['fausses_alarmes_par_heure']} |")
        else:
            ok = "OUI" if not r["fausses_alarmes"] else "NON"
            print(f"| {r['scenario']} | aucune alerte | {ok} | - | - | - "
                  f"| {r['fausses_alarmes_par_heure']} |")

    couverture = couverture_spatiale(poly, route)
    print(f"\n## Portee reelle de la regle de deviation (seuil {settings.seuil_deviation_m:.0f} m)\n")
    print("| Detour nominal | Ecart mesure a la polyligne (min / median / max) | Part du parcours detectee |")
    print("|--:|---|--:|")
    for l in couverture:
        print(f"| {l['detour_nominal_m']} m | {l['ecart_mesure_min_m']:.0f} / "
              f"{l['ecart_mesure_median_m']:.0f} / {l['ecart_mesure_max_m']:.0f} m "
              f"| {l['part_parcours_detectee_%']} % |")

    cov_seuil = couverture_par_seuil(poly, route)
    print("\n## Couverture selon le seuil (part du parcours ou le detour serait detecte)\n")
    print("| Seuil (m) | detour 200 m | detour 300 m | detour 400 m |")
    print("|--:|--:|--:|--:|")
    for l in cov_seuil:
        print(f"| {l['seuil_m']} | {l['detour_200m_%']} % | {l['detour_300m_%']} % "
              f"| {l['detour_400m_%']} % |")

    bal_dev = _balayage_deviation(poly, duree_plan_s, route)
    bal_reb = _balayage_antirebond(poly, duree_plan_s, route)
    bal_arr = _balayage_arret(poly, duree_plan_s, route)

    print("\n## Seuil de deviation x bruit GPS (detour reel de 300 m ; detecte . fausses alarmes/h)\n")
    print("| Seuil (m) | " + " | ".join(f"sigma={b:g} m" for b in BRUITS) + " |")
    print("|--:|" + "---|" * len(BRUITS))
    for seuil in sorted({l["seuil_m"] for l in bal_dev}):
        cells = []
        for b in BRUITS:
            l = next(x for x in bal_dev if x["seuil_m"] == seuil and x["bruit_m"] == b)
            cells.append(f"{'OUI' if l['detour_300m_detecte'] else 'NON'} . {l['fausses_alarmes_h']}/h")
        print(f"| {seuil} | " + " | ".join(cells) + " |")

    print("\n## Anti-rebond (seuil abaisse a 100 m, bruit sigma=30 m)\n")
    print("| Pings consecutifs | Fausses alarmes/h | Detour detecte | Latence |")
    print("|--:|--:|:-:|--:|")
    for l in bal_reb:
        lat = f"{l['latence_s']:.0f} s" if l["latence_s"] is not None else "-"
        print(f"| {l['pings_consecutifs']} | {l['fausses_alarmes_h']} | "
              f"{'OUI' if l['detour_detecte'] else 'NON'} | {lat} |")

    print("\n## Seuil d'arret prolonge (feu 1 min | trafic 3 min | panne 8 min)\n")
    print("| Seuil (min) | Panne detectee | Latence | Fausses alarmes |")
    print("|--:|:-:|--:|--:|")
    for l in bal_arr:
        lat = f"{l['latence_s']:.0f} s" if l["latence_s"] is not None else "-"
        print(f"| {l['seuil_min']} | {'OUI' if l['panne_detectee'] else 'NON'} | {lat} "
              f"| {l['fausses_alarmes']} |")

    os.makedirs(settings.data_dir, exist_ok=True)
    chemin = os.path.join(settings.data_dir, "live_rules_benchmark.json")
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump({
            "tournee": {"points": len(route), "longueur_m": round(poly.longueur, 1),
                        "duree_plan_min": round(duree_plan_s / 60, 2)},
            "seuils_production": {
                "vitesse_kmh": settings.seuil_vitesse_kmh,
                "arret_min": settings.seuil_arret_min,
                "deviation_m": settings.seuil_deviation_m,
                "deviation_pings": settings.deviation_pings_consecutifs,
                "cooldown_s": live_monitor._ALERT_COOLDOWN_S,
            },
            "scenarios": camp,
            "couverture_spatiale_deviation": couverture,
            "couverture_par_seuil": cov_seuil,
            "balayage_deviation": bal_dev,
            "balayage_antirebond": bal_reb,
            "balayage_arret": bal_arr,
        }, f, indent=2, ensure_ascii=False)
    print(f"\n[MS11] -> {chemin}")


if __name__ == "__main__":
    main()
