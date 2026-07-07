# 📐 Grand exemple — Matrice OSRM de Meknès & résolution du TSP
*Transport Scolaire Intelligent — annexe pédagogique du service MS5 (VRP)*

Cet exemple utilise **10 arrêts réels de Meknès** (1 école-dépôt + 9 arrêts) et une **vraie matrice OSRM**
(réseau routier OSM), pour illustrer concrètement comment MS5 calcule une tournée optimale.

---

## 1. Les 10 points (dépôt = école)

- **0** = École (Al Massira)  `(33.893, -5.5455)`
- **1** = Médina  `(33.8935, -5.5547)`
- **2** = Hamria  `(33.8978, -5.5489)`
- **3** = Zitoune  `(33.9012, -5.5523)`
- **4** = Wislane  `(33.9067, -5.5456)`
- **5** = Ismailia  `(33.8876, -5.5612)`
- **6** = Mellah  `(33.8901, -5.5598)`
- **7** = Sidi Baba  `(33.8845, -5.5534)`
- **8** = Ain Karma  `(33.8712, -5.5312)`
- **9** = Al Manzeh  `(33.8756, -5.5401)`

> Le point **0** est le **dépôt** : le bus part de l'école, passe par les 9 arrêts, revient à l'école.

---

## 2. Matrice des DURÉES routières OSRM (en minutes)

Cellule (i, j) = temps de conduite réel du point *i* vers le point *j* (réseau routier de Meknès).

| # |0|1|2|3|4|5|6|7|8|9|
|---|---|---|---|---|---|---|---|---|---|---|
| **0** |0.0|5.2|3.0|4.1|5.5|7.3|6.0|5.2|5.3|6.0|
| **1** |3.6|0.0|2.1|2.5|4.1|4.3|3.3|2.7|6.0|4.8|
| **2** |3.2|4.0|0.0|1.9|3.3|5.7|4.6|4.1|5.4|5.3|
| **3** |4.0|4.1|1.7|0.0|2.9|5.8|4.8|4.2|6.2|6.0|
| **4** |5.5|6.1|3.2|2.8|0.0|7.8|6.7|6.2|7.7|7.9|
| **5** |7.2|4.0|5.7|6.1|7.7|0.0|2.9|2.4|7.6|6.0|
| **6** |6.2|3.0|4.7|5.0|6.7|3.0|0.0|2.6|6.6|5.0|
| **7** |4.8|1.6|3.7|4.0|5.7|2.7|2.2|0.0|5.2|3.6|
| **8** |5.3|5.8|5.7|6.3|7.7|7.9|6.7|5.8|0.0|4.5|
| **9** |6.1|4.2|5.5|6.4|8.1|6.3|5.1|4.2|4.1|0.0|


*(Matrice ≈ symétrique ici ; elle pourrait être asymétrique en présence de sens uniques.)*

---

## 3. Matrice des DISTANCES routières OSRM (en km)

| # |0|1|2|3|4|5|6|7|8|9|
|---|---|---|---|---|---|---|---|---|---|---|
| **0** |0.00|3.49|1.21|2.31|2.85|3.92|3.46|3.02|3.16|3.40|
| **1** |1.71|0.00|1.37|1.29|2.29|2.37|1.97|1.72|4.43|3.17|
| **2** |1.72|2.78|0.00|0.69|1.44|3.16|2.76|2.51|3.97|3.24|
| **3** |2.14|2.76|0.76|0.00|1.27|3.15|2.75|2.50|4.40|3.65|
| **4** |3.10|4.07|1.73|1.26|0.00|4.46|4.06|3.80|5.36|5.06|
| **5** |3.36|2.04|3.02|2.94|3.95|0.00|1.18|0.98|4.50|2.99|
| **6** |2.93|1.63|2.59|2.51|3.52|1.20|0.00|1.02|4.09|2.57|
| **7** |2.54|1.06|2.43|2.35|3.36|1.04|0.94|0.00|3.52|2.01|
| **8** |3.15|4.30|4.11|4.57|5.10|4.73|4.27|3.84|0.00|2.47|
| **9** |2.98|2.64|3.27|3.59|4.59|3.06|2.60|2.17|2.22|0.00|


---

## 4. Preuve : routes réelles ≠ vol d'oiseau

| Trajet | Route OSRM (m) | Vol d'oiseau (m) | Ratio |
|---|---|---|---|
| École (Al Massira) → Médina | 3493 | 851 | **4.10×** |
| École (Al Massira) → Wislane | 2846 | 1523 | **1.87×** |
| École (Al Massira) → Ain Karma | 3159 | 2760 | **1.14×** |
| Médina → Wislane | 2295 | 1691 | **1.36×** |

La route est **toujours plus longue** que la ligne droite → on utilise bien le **vrai réseau** (le détour
École → Médina traverse l'oued, d'où un ratio élevé).

---

## 5. Résolution du TSP sur cette matrice

**Baseline (« plus proche voisin ») :**
`École (Al Massira) → Hamria → Zitoune → Wislane → Médina → Sidi Baba → Mellah → Ismailia → Al Manzeh → Ain Karma → École (Al Massira)`
→ durée totale ≈ **37.3 min**

**Optimisé (OR-Tools, coût = durées OSRM) :**
`École (Al Massira) → Ain Karma → Al Manzeh → Mellah → Ismailia → Sidi Baba → Médina → Zitoune → Wislane → Hamria → École (Al Massira)`
→ durée totale ≈ **33.7 min** · distance ≈ **17.5 km**

### 🎯 Gain : **9.8 %** de temps économisé (37.3 min → 33.7 min)

- La **baseline** fonce toujours au plus proche → elle finit par faire des **allers-retours**.
- **OR-Tools** part de cette solution puis la **décroise** (2-opt) et **déplace** des arrêts (Or-opt) jusqu'à
  la tournée quasi-optimale — le tout sur les **vraies durées OSRM**.
- La géométrie de la tournée optimale contient **726 points** (elle épouse les rues, ce n'est pas une
  succession de lignes droites).

---

## 6. Comment lire / refaire

- Ces chiffres proviennent d'un appel réel à l'API OSRM `/table` (durées + distances) sur le réseau de Meknès.
- C'est exactement ce que fait le service **MS5** (`POST /api/planification/tournee`) pour chaque bus, avec les
  élèves réels du groupe (issus du clustering MS6).
- Détails du fonctionnement : voir `docs/MS5_VRP_PLANIFICATION.md` (§2bis « Le problème du voyageur de commerce »).
