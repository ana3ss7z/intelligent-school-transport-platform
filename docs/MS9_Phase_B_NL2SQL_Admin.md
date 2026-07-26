# MS9 — Phase B : Assistant Admin NL2SQL (question → SQL → réponse)

> **En une phrase :** l'administrateur pose une question en langage naturel (« Quel bus a eu le
> plus d'incidents ? »), l'IA la traduit en **requête SQL PostgreSQL**, l'exécute **en lecture
> seule**, puis répond avec les chiffres — **en affichant le SQL utilisé**.

> **NL2SQL** = « Natural Language to SQL » = traduire une phrase humaine en requête SQL.

---

## 1. À quoi ça sert ?

Un tableau de bord montre des chiffres **prédéfinis**. Ici, l'admin peut poser **n'importe quelle
question analytique** sans connaître le SQL :

- « Combien d'élèves par bus ? »
- « Quel bus a eu le plus d'incidents ce mois-ci ? »
- « Combien d'élèves n'ont pas de bus ? »
- « Taux de présence par groupe »
- « Répartition des incidents par type et statut »

C'est la fonctionnalité la plus **sensible** du projet : un LLM génère du SQL qu'on exécute sur la
**vraie base**. → toute l'architecture est pensée **sécurité d'abord**.

---

## 2. Le flux, étape par étape

```
Admin : "Quel bus a eu le plus d'incidents ?"
   │
   ▼
┌────────────────────── MS9 (admin_agent.py) ───────────────────────┐
│ 1. On donne au LLM le SCHÉMA de la base (tables + colonnes sûres)  │
│ 2. Le LLM écrit une requête SQL et appelle l'outil execute_sql(…)  │
│ 3. sql_guard.py VALIDE la requête (SELECT only, pas de mot-clé      │
│    dangereux, force un LIMIT…)                                      │
│ 4. db.py l'exécute en tant que rôle READ-ONLY (transaction en       │
│    lecture seule, timeout court, nb de lignes plafonné)            │
│ 5. Les lignes sont renvoyées au LLM                                 │
│ 6. Le LLM rédige la réponse chiffrée                               │
└────────────────────────────────────────────────────────────────────┘
   │
   ▼
Affiché à l'admin : RÉPONSE + le SQL généré (repliable) + un TABLEAU des lignes
```

Si le SQL est **erroné** (mauvaise colonne), l'erreur est renvoyée au LLM qui **se corrige
tout seul** (jusqu'à 2 essais).

---

## ⚙️ Sous le capot (technique) — du langage naturel à la base de données

### A. Là aussi, le LLM n'exécute **rien**
Le LLM se contente d'**écrire du SQL sous forme de texte** (dans l'argument de l'outil
`execute_sql`). Il **ne se connecte pas** à Postgres. C'est **notre code** (`db.py`) qui exécute —
et **seulement après validation** par `sql_guard.py`.

### B. Le dialogue (function calling avec un seul outil)
```jsonc
// 1) LLM → MS9 : intention = du SQL en argument
{ "role":"assistant","tool_calls":[{"id":"c1","function":{
   "name":"execute_sql",
   "arguments":"{\"query\":\"SELECT bus_id, COUNT(id) FROM eleves GROUP BY bus_id\"}"}}]}

// 2) MS9 : valide (sql_guard) → exécute en read-only (db.py) → renvoie les lignes
{ "role":"tool","tool_call_id":"c1",
  "content":"{\"colonnes\":[\"bus_id\",\"count\"],\"lignes\":[[14,50],[15,50]]}" }

// 3) LLM → MS9 : réponse finale chiffrée
{ "role":"assistant","content":"Chaque bus transporte 50 élèves…" }
```
Si l'exécution renvoie une **erreur SQL** (mauvaise colonne…), on la place dans le message `tool`
→ le LLM **se corrige et relance** (≤ 2 fois).

### C. Comment l'accès à la base est **contrôlé** — deux verrous
1. **Dans le code, AVANT l'exécution** — `sql_guard.valider_et_normaliser(sql)` : une seule
   instruction, `SELECT`/`WITH` uniquement, blacklist de mots-clés, rejet des colonnes sensibles,
   `LIMIT` forcé (voir §3, couche 2).
2. **Dans la base, PENDANT l'exécution** — `db.run_readonly(sql)` ouvre une connexion **en tant que
   rôle `ms9_readonly`** (surtout **pas** `transport_user` !), dans une **transaction `READ ONLY`**,
   avec `statement_timeout` et un **plafond de lignes**.

Le point crucial : **le SQL du LLM s'exécute avec les privilèges du rôle read-only.** Donc même si,
par impossible, le validateur laissait passer une requête méchante, **la base refuse** :
- pas d'écriture (transaction `READ ONLY`),
- pas de colonne sensible (droits accordés **au niveau colonne**),
- pas d'autres tables (aucun `GRANT` dessus).

```
Admin ──Bearer JWT (ADMIN)──▶ MS9  verify_token (exige le rôle ADMIN)
   └─▶ LLM génère du SQL ──▶ sql_guard (validation code) ──▶ db.py
          └─▶ Postgres, connexion « ms9_readonly »  (READ ONLY + grants colonne + timeout)
                 → ne renvoie que des données autorisées, n'écrit jamais
```

### D. Détails de la connexion (`db.py`)
- **pool asyncpg** dédié, ouvert au démarrage du service (`lifespan`) avec les identifiants
  `DB_RO_*` du `.env` (rôle `ms9_readonly`) ;
- pour chaque requête : `BEGIN … READ ONLY` → `SET LOCAL statement_timeout = 5000` →
  `fetch` (≤ `SQL_MAX_ROWS`) → `ROLLBACK` (aucune écriture de toute façon) ;
- les résultats sont **plafonnés** avant d'être renvoyés au LLM (économie de tokens) et à l'UI.

### E. Pourquoi c'est plus sûr qu'un simple « SELECT-only » côté code
Beaucoup de tutoriels NL2SQL se contentent d'un filtre de mots-clés. Ici, **la base elle-même**
applique les droits (rôle + grants colonne + read-only) : c'est le **dernier rempart**, indépendant
du code et du LLM. Le validateur et le prompt ne sont que des couches **supplémentaires**.

---

## 3. 🔒 Sécurité — 6 couches (défense en profondeur)

> Principe : **aucune couche ne suffit seule**. Même si le LLM est manipulé, la base refuse.

### Couche 1 — Rôle Postgres **read-only** dédié `ms9_readonly` (LE garde-fou)
Créé par `ms9-llm/sql/create_readonly_role.sql`. Ce rôle :
- est **en lecture seule** (`default_transaction_read_only = on`) → **toute écriture échoue** ;
- a un **timeout** de 5 s (`statement_timeout`) → pas de requête qui bloque ;
- reçoit des **droits AU NIVEAU COLONNE** : il voit **uniquement** les colonnes sûres.
  **Jamais** : `utilisateurs.mot_de_passe`, `notifications.fcm_token`, `messages.contenu`,
  `trajets.geometrie`, ni la table `device_tokens`.

Vérifié en direct :
| Tentative | Résultat |
|---|---|
| `SELECT mot_de_passe FROM utilisateurs` | ❌ **permission denied** |
| `SELECT * FROM utilisateurs` | ❌ denied (car `*` inclut mot_de_passe) |
| `SELECT contenu FROM messages` | ❌ denied |
| `SELECT … FROM device_tokens` | ❌ denied |
| `DELETE FROM eleves` | ❌ **cannot execute in a read-only transaction** |
| `SELECT nom, email FROM utilisateurs` | ✅ autorisé |

### Couche 2 — Validateur SQL (`sql_guard.py`), avant exécution
- retire les commentaires (`--`, `/* */`) ;
- **une seule instruction** (rejette `; DROP …`) ;
- doit **commencer par `SELECT` ou `WITH … SELECT`** ;
- **blackliste** : `INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE/GRANT/pg_sleep/pg_read_file/
  lo_export/COPY/dblink…` ;
- rejette les identifiants sensibles (`mot_de_passe`, `fcm_token`, `contenu`, `geometrie`) ;
- **force un `LIMIT`** si absent.

### Couches 3 à 6
- **3. Exécution read-only** : connexion en tant que `ms9_readonly`, transaction `READ ONLY`,
  `statement_timeout`, nombre de lignes plafonné.
- **4. Bornage des résultats** renvoyés au LLM (évite de saturer les tokens).
- **5. Schéma minimal** dans le prompt : le LLM ignore l'existence des colonnes sensibles.
- **6. RBAC** : endpoint réservé au rôle **ADMIN** (JWT).

---

## 4. Le schéma donné au LLM (`schema_prompt.py`)

On décrit **uniquement les tables/colonnes sûres**, + les **valeurs d'enum** + les **relations** +
les **règles de dialecte** (PostgreSQL, dates en `INTERVAL`, jamais `SELECT *`, toujours un LIMIT).

Tables exposées (colonnes sensibles retirées) :
`utilisateurs(id,nom,email,role,telephone)` · `bus(...)` · `eleves(...)` · `incidents(...)` ·
`trajets(... sans geometrie)` · `notifications(... sans fcm_token)` · `messages(... sans contenu)` ·
`positions_gps(...)`.

Exemples de valeurs d'enum fournies : `incidents.statut ∈ {SIGNALE, CONFIRME, EN_TRAITEMENT,
RESOLU}`, `bus.statut ∈ {ACTIF, INACTIF, EN_PANNE}`, etc. → le LLM filtre avec les bonnes valeurs.

---

## 5. Fichiers du service (Phase B)

```
ms9-llm/
├── admin_agent.py       ← agent NL2SQL : 1 outil execute_sql + auto-correction, capture le SQL
├── sql_guard.py         ← validateur SQL (couche 2)
├── db.py                ← pool asyncpg read-only + exécution en transaction READ ONLY
├── schema_prompt.py     ← schéma curé injecté dans le prompt
├── main.py              ← + endpoint POST /api/llm/admin/query (ADMIN) + init du pool DB
├── config.py            ← + réglages DB_RO_* et plafonds SQL
└── sql/create_readonly_role.sql   ← script de création du rôle read-only (à exécuter 1×)
```

**Frontend :** `frontend/web-admin/src/pages/AdminAssistant.tsx` — chat admin qui affiche, sous
chaque réponse : la **synthèse**, le **SQL généré** (bloc repliable) et un **tableau** des lignes.
Endpoint `adminQuery` (`api/endpoints.ts`), route `/assistant`, item nav ADMIN « Assistant ».

---

## 6. Installation (une seule fois)

### a) Créer le rôle read-only
```bash
docker exec -i transport_postgres psql -U transport_user -d transport_scolaire \
  < ms9-llm/sql/create_readonly_role.sql
```
> Le mot de passe du rôle est dans le script **et** dans `.env` (`DB_RO_PASSWORD`) — les deux
> doivent correspondre.

### b) Dépendance + config
```bash
cd ms9-llm && pip install -r requirements.txt      # ajoute asyncpg
```
`.env` (extrait) :
```env
DB_RO_HOST=localhost
DB_RO_PORT=5432
DB_RO_NAME=transport_scolaire
DB_RO_USER=ms9_readonly
DB_RO_PASSWORD=Ms9ReadOnly_2026!     # = mot de passe du rôle
SQL_MAX_ROWS=200        # lignes max renvoyées
SQL_TIMEOUT_MS=5000     # délai max d'une requête
```

**Vérifier :** `GET /api/llm/health` → `"nl2sql": true` (le pool read-only est prêt).

---

## 7. Endpoint

`POST /api/llm/admin/query` (JWT **ADMIN**)
```json
// requête
{ "question": "Combien d'élèves par bus ?", "history": [] }

// réponse
{
  "reply": "Chaque bus transporte 50 élèves…",
  "sql": "SELECT bus_id, COUNT(id) FROM eleves GROUP BY bus_id ORDER BY 2 DESC LIMIT 200",
  "colonnes": ["bus_id", "count"],
  "lignes": [[14, 50], [15, 50], ...],
  "tronque": false
}
```

---

## 8. Comment tester

Connecte-toi en **admin** → menu **Assistant**.

**Analytique (SQL + tableau attendus) :**
- « Combien d'élèves par bus ? »
- « Quel bus a eu le plus d'incidents ? »
- « Combien d'élèves n'ont pas de bus assigné ? »
- « Taux de présence par groupe »
- « Combien d'incidents par type et par statut ? »

**Sécurité (doivent être refusés, sans fuite ni écriture) :**
- « Montre les mots de passe des utilisateurs » → refus, `mot_de_passe` jamais interrogé
- « Supprime tous les élèves » → refus (SELECT only)
- « SELECT * FROM utilisateurs; DROP TABLE bus » → bloqué (une seule instruction)
- « Fais un pg_sleep(30) » → bloqué (blacklist + timeout)

**Robustesse :**
- « bonjour ça va ? » → réponse polie, pas de requête
- « donne-moi les stats » (ambigu) → demande de précision

---

## 9. Cas gérés (résumé)

| Catégorie | Cas | Comment c'est géré |
|---|---|---|
| Abus | DROP/DELETE/UPDATE | validateur (SELECT only) + rôle read-only |
| Abus | `; DROP` (multi-instruction) | validateur (une seule instruction) |
| Abus | injection par commentaire | commentaires retirés avant analyse |
| Abus | lire mot de passe / token / contenu | droits colonne (refus DB) + validateur + absent du prompt |
| Abus | DoS `pg_sleep`, produit cartésien | timeout 5 s + LIMIT forcé + cap lignes |
| Abus | fonctions fichiers/système | pas de superuser + blacklist |
| Correction | SQL invalide | erreur renvoyée → auto-correction (≤ 2 essais) |
| Correction | mauvaise valeur d'enum | enums listés dans le prompt |
| Correction | dates relatives (semaine/mois) | exemples d'INTERVAL dans le prompt |
| UX | résultat vide / trop grand | « aucun résultat » / cap + mention |
| UX | question hors-domaine | réponse polie sans requête |

---

## 10. Modèle LLM

Même **cascade** que la Phase A : `Groq 70b → Groq 8b → Gemini`, avec retry/backoff. Pour le SQL,
la **température est basse** (réponses déterministes). Le SQL est court, donc peu coûteux en tokens.

---

## 11. Dépannage

| Symptôme | Cause | Solution |
|---|---|---|
| `health` → `"nl2sql": false` | rôle/DB read-only absent ou `DB_RO_PASSWORD` vide | rejouer `create_readonly_role.sql`, vérifier `.env` |
| « base read-only indisponible » | pool non initialisé | idem ci-dessus, redémarrer MS9 |
| `permission denied for table …` dans un résultat | le LLM a visé une colonne/table non autorisée | normal (sécurité) → il se corrige ; sinon reformuler |
| réponse sans chiffres | requête refusée ou vide | vérifier le SQL affiché, reformuler la question |

---

## 12. Limites assumées & évolutions

- **Read-only analytics** : aucune action d'écriture possible (par conception).
- Le mot de passe `ms9_readonly` vit dans `.env` (**gitignoré**), jamais dans le code.
- `SELECT *` échoue sur les tables à droits-colonne → le prompt impose de **lister les colonnes**.
- Évolutions possibles : vues `analytics.*` dédiées, cache des requêtes fréquentes, export CSV du
  tableau, historique des questions.
