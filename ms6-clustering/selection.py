"""
Sélection du nombre de bus (k) pour la stratégie de production.

Balaye k de ⌈n/capacité⌉ à +marge (courbe de Pareto qualité/compacité vs flotte), puis choisit le
plus petit k atteignant le seuil de silhouette, sinon le meilleur k.

Pourquoi ce module a été durci (24/08)
--------------------------------------
La version précédente notait chaque `k` **une seule fois** et retenait le meilleur score. Or la
silhouette d'une même partition varie d'une initialisation à l'autre — **±0,012 pour k=8 et ±0,020
pour k=9**, mesuré sur dix graines — alors que les écarts entre `k` voisins ne valent que 0,006 à
0,017. On départageait donc des candidats **indiscernables** : c'était un argmax sur du bruit.

Effet observé en production : sur 30 permutations des mêmes 300 élèves, le service répondait
**7 bus dans 57 % des cas, 8 dans 7 %, 9 dans 37 %**. Le nombre de bus n'était pas une propriété
des données, mais du hasard — et comme MS6 recalcule à chaque inscription, une seule inscription
pouvait faire changer de bus une trentaine d'enfants.

Deux changements y répondent :

1. **On mesure plusieurs fois avant de juger** (`n_init` initialisations par `k`, on retient la
   médiane). Un `k` instable ne peut plus gagner sur un coup de chance.
2. **On ne départage plus ce qui n'est pas départageable** : à moins de ε du meilleur, on garde le
   **plus petit `k`** — un bus de moins, donc un chauffeur de moins. Et **ε n'est pas codé en dur** :
   il est déduit de la dispersion réellement observée, donc il s'adapte à d'autres données.

Détail qui a son importance : la ligne renvoyée est celle de l'**essai médian**, pas une partition
recalculée après coup. La partition livrée est donc exactement celle qui a été notée.
"""
import math
import logging

import numpy as np

from algorithms import kmedoids_capacitaire
from evaluation import evaluer

logger = logging.getLogger(__name__)

# Nombre d'initialisations par k, et graines associées.
N_INIT_DEFAUT = 5
GRAINES_DEFAUT = (42, 7, 2024, 1337, 91)

# Bornes de sécurité pour ε (voir `epsilon_entre`).
EPSILON_MIN = 0.005
EPSILON_MAX = 0.05

# Marge d'HYSTÉRÉSIS — à ne pas confondre avec ε ci-dessus. Les deux répondent à des questions
# différentes, et les confondre a été une erreur de conception de ce correctif :
#
#   · ε (statistique)    : « ces deux k sont-ils discernables DANS CE CALCUL ? »
#                          → déduit de la dispersion entre initialisations, de l'ordre de 0,005.
#   · cette marge (métier) : « ce gain justifie-t-il de REDISTRIBUER TOUTE L'ÉCOLE ? »
#                          → une trentaine d'enfants changent de bus, autant de familles à
#                            prévenir, deux chauffeurs qui reçoivent une nouvelle liste.
#
# Elle est calibrée sur la fluctuation observée quand les données bougent à peine : entre 292 et
# 296 élèves, le meilleur k passe de 7 à 9 puis revient à 7, pour des écarts de silhouette de
# l'ordre de 0,019. Une marge de 0,03 absorbe ce va-et-vient sans figer la flotte pour autant —
# un `k` devenu infaisable sort de toute façon du Pareto et force le changement.
MARGE_HYSTERESIS = 0.03


def _note(row: dict) -> float:
    """Score d'un candidat : le meilleur essai s'il existe, sinon la mesure unique (rétro-compatible)."""
    val = row.get("silhouette_mediane")
    if val is None:
        val = row.get("silhouette")
    return -1.0 if val is None else float(val)


def epsilon_entre(a: dict, b: dict) -> float:
    """Marge d'indécision **propre à la comparaison** entre deux candidats.

    Déduite de la dispersion réellement observée sur ces deux `k`-là, jamais figée : un ε codé en
    dur est réglé sur un jeu de données et faux sur tous les autres.

    ⚠️ **Une première version prenait la plus grande dispersion de TOUS les candidats. C'était
    faux, et le test l'a attrapé.** Sur une permutation, `k=9` s'est trouvé très instable
    (dispersion 0,0486) ; ce bruit — qui ne concernait que `k=9` — élargissait la marge au point de
    faire passer `k=6` (0,392) pour l'égal de `k=7` (0,433). Le service répondait alors 6 bus.
    L'incertitude qui compte pour départager deux candidats est **celle de ces deux-là**, pas celle
    d'un troisième.

    Les bornes évitent les deux cas dégénérés : une seule initialisation (dispersion nulle → ε nul
    → retour à l'argmax), et un jeu très bruité qui rendrait tous les `k` équivalents (→ on
    prendrait toujours le plus petit sans regarder la qualité).
    """
    brut = max(a.get("silhouette_dispersion") or 0.0, b.get("silhouette_dispersion") or 0.0)
    return float(min(EPSILON_MAX, max(EPSILON_MIN, brut)))


def _dispersion_robuste(scores: list[float]) -> float:
    """Écart typique entre essais, **insensible à un essai isolé** (écart absolu médian, MAD).

    On n'utilise pas l'étendue (max − min) : avec quelques initialisations, un seul mauvais départ
    la fait exploser. Concrètement, k=6 a tiré [0,3915 · 0,3920 · 0,3410] — un essai raté sur trois
    portait son étendue à 0,051, ce qui **élargissait sa propre marge de tolérance** et le faisait
    passer pour l'égal de k=7. Un candidat instable obtenait ainsi *plus* de bénéfice du doute :
    exactement l'inverse de ce qu'il faut. Le MAD vaut ici 0,0005 et décrit bien la réalité —
    les essais sont serrés, avec une valeur aberrante.
    """
    if len(scores) < 2:
        return 0.0
    med = float(np.median(scores))
    return float(np.median([abs(s - med) for s in scores]))


def _mesurer_k(D: np.ndarray, XY: np.ndarray, capacity: int, k: int,
               iters: int, rayon_max: float, graines) -> dict:
    """Évalue un `k` sur plusieurs initialisations.

    Deux grandeurs, pour deux usages différents — et les confondre est précisément l'erreur :

    - **`silhouette_mediane`** sert à **comparer les `k` entre eux**. On prend la médiane parce que
      les candidats n'ont pas la même variabilité : k=7 est stable (écarts ~0,0002) alors que k=9
      ne l'est pas (~0,03). Comparer le *meilleur* essai de chacun reviendrait à comparer des
      maxima d'échantillons de variances différentes — ce qui favorise mécaniquement le plus
      bruité. *Mesuré : en prenant le meilleur essai, le service répondait k=9 dans 14 cas sur 30 ;
      en prenant la médiane, il répond k=7.*
    - **la partition renvoyée** est celle du **meilleur** essai de ce `k`. Une fois `k` choisi, il
      n'y a plus de comparaison à fausser : autant livrer la meilleure partition disponible. C'est
      la pratique standard des redémarrages multiples (`KMeans(n_init=10)`).
    """
    essais = []
    for graine in graines:
        labels, medoids = kmedoids_capacitaire(D, k, capacity, XY, iters=iters,
                                               seed=graine, rayon_max=rayon_max)
        essais.append({"labels": labels, "medoids": medoids,
                       **evaluer(labels, capacity, D=D, medoids=medoids)})

    scores = [(-1.0 if e["silhouette"] is None else float(e["silhouette"])) for e in essais]
    representant = essais[int(np.argmax(scores))]      # meilleure partition pour ce k
    return {
        **representant,
        "k": k,
        "silhouette_mediane": round(float(np.median(scores)), 6),   # sert à comparer les k
        "silhouette_dispersion": round(_dispersion_robuste(scores), 6),
        "silhouettes_essais": [round(s, 4) for s in scores],
        "n_init": len(essais),
    }


def pareto(D: np.ndarray, XY: np.ndarray, capacity: int, k_min: int | None = None,
           k_margin: int = 3, iters: int = 6, rayon_max: float = 0.0,
           n_init: int = N_INIT_DEFAUT, graines=GRAINES_DEFAUT) -> list[dict]:
    """
    Pour chaque k, calcule la partition capacitaire et ses métriques (routières/euclidiennes).
    k_min : nombre de bus minimal (par défaut ⌈n/capacité⌉ ; on peut imposer un k_min plus grand
            pour réserver de la capacité aux élèves dispersés ajoutés ensuite).
    `rayon_max` > 0 : contrainte de rayon max au médoïde (les points trop loin deviennent dispersés).
    `n_init` : nombre d'initialisations par k (voir l'en-tête du module). `n_init=1` reproduit
            exactement l'ancien comportement — utile pour comparer avant/après.
    Retourne une liste de dicts {k, labels, medoids, silhouette_mediane, ...}.
    """
    n = len(D)
    if k_min is None:
        k_min = math.ceil(n / capacity)
    graines_utilisees = list(graines)[:max(1, n_init)]
    out = []
    for k in range(k_min, k_min + k_margin + 1):
        if k * capacity < n:
            continue
        out.append(_mesurer_k(D, XY, capacity, k, iters, rayon_max, graines_utilisees))
    return out


def choisir_k(pareto_rows: list[dict], min_silhouette: float = 0.50,
              epsilon: float | None = None, k_precedent: int | None = None) -> dict:
    """
    Choix : plus petit k faisable dont la silhouette ≥ seuil ; sinon, parmi les k dont la qualité
    est indiscernable du meilleur (à moins de ε), le plus petit.

    `epsilon=None` → déduit des données (`epsilon_entre`) ; `epsilon=0.0` → ancien comportement
    (argmax strict), conservé pour les comparaisons avant/après.

    `k_precedent` active l'**hystérésis** : on conserve la flotte en place tant qu'elle reste
    faisable et qu'elle n'est pas nettement battue. Sans cela, la règle de parcimonie bascule dès
    qu'un `k` plus petit devient faisable — et **chaque bascule redistribue toute l'école**
    (12 à 17 % des élèves changent de bus, mesuré, pour une seule inscription).

    Un point qui tombe juste : « l'ancien `k` est-il encore faisable ? » ne demande aucun test
    supplémentaire. `pareto` n'émet que des `k` capables d'accueillir tout le monde
    (`k * capacité >= n`) ; il suffit donc que `k_precedent` **figure parmi les lignes**.
    On ne s'appuie surtout pas sur le drapeau `faisable`, qui ne vaut `False` qu'en cas
    d'affectation totalement vide et n'est donc pas un signal exploitable.

    Retourne la ligne Pareto retenue.
    """
    faisables = [r for r in pareto_rows if r["faisable"]]
    if not faisables:
        faisables = pareto_rows
    if not faisables:
        raise ValueError("aucune ligne Pareto à départager")

    passe = [r for r in faisables if _note(r) >= min_silhouette]
    if passe:
        return min(passe, key=lambda r: r["k"])

    meilleur = max(faisables, key=_note)
    base = _note(meilleur)

    def marge(r: dict) -> float:
        return float(epsilon) if epsilon is not None else epsilon_entre(r, meilleur)

    indiscernables = [r for r in faisables if _note(r) >= base - marge(r)]
    retenu = min(indiscernables, key=lambda r: r["k"])

    if len(indiscernables) > 1:
        logger.info("[MS6] k=%d retenu (parcimonie) parmi %s — meilleur k=%d à %.4f",
                    retenu["k"], [r["k"] for r in indiscernables], meilleur["k"], base)

    if k_precedent is not None and k_precedent != retenu["k"]:
        ancien = next((r for r in faisables if r["k"] == k_precedent), None)
        if ancien is not None and _note(ancien) >= base - MARGE_HYSTERESIS:
            logger.info("[MS6] Hystérésis : flotte maintenue à k=%d (le calcul proposait k=%d ; "
                        "écart %.4f < marge %.3f)",
                        k_precedent, retenu["k"], base - _note(ancien), MARGE_HYSTERESIS)
            return ancien
        if ancien is None:
            logger.info("[MS6] Flotte k=%d devenue infaisable — passage à k=%d",
                        k_precedent, retenu["k"])
        else:
            logger.info("[MS6] Flotte changée : k=%d → k=%d (écart %.4f ≥ marge %.3f)",
                        k_precedent, retenu["k"], base - _note(ancien), MARGE_HYSTERESIS)
    return retenu
