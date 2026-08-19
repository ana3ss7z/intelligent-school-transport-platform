# MS9 — Phase A : Chatbot Parent (assistant conversationnel temps réel)

> **En une phrase :** un parent pose une question en langage naturel (« Où est le bus de mon
> enfant ? »), et l'IA répond avec des **données réelles** en appelant les microservices — jamais
> d'invention, et **uniquement** sur les enfants de ce parent.

---

## 1. À quoi ça sert ?

Le parent discute avec un assistant (page **Assistant** de l'espace parent) qui sait répondre à :

| Le parent demande… | L'assistant va chercher… | Dans le microservice |
|---|---|---|
| « Où est le bus ? » | la dernière position GPS (+ le **quartier**) | MS3 |
| « Dans combien de temps ? » | l'ETA (temps estimé jusqu'à l'école) | MS12 |
| « Mon enfant est-il monté ? » | le statut de présence | MS2 |
| « Le trajet est-il parti ? » | le trajet en cours (matin/soir) | MS1 |
| « Y a-t-il un incident ? » | les incidents du bus | MS10 |
| « Où est l'école ? » | réponse directe (connue) | — |

**Langues :** français, arabe standard, **darija**.

---

## 2. L'idée clé : le « tool-calling » (appel d'outils)

Le LLM **ne devine pas** les réponses. Il décide **quels outils appeler**, on exécute ces
outils (de vraies requêtes HTTP vers les microservices), on lui rend les résultats, et il rédige
la réponse. C'est ce qu'on appelle un **agent à outils**.

```
Parent : "Où est le bus et quand arrive-t-il ?"
   │
   ▼
┌─────────────────────── MS9 (agent.py) ───────────────────────┐
│ 1. Récupère les enfants du parent (1 seul appel MS2)          │
│ 2. Envoie la question + la liste des outils au LLM            │
│ 3. Le LLM répond : "appelle get_position_bus(14)              │
│                     ET get_eta_ecole(14)"                     │
│ 4. MS9 exécute les 2 outils EN PARALLÈLE (avec le JWT parent) │
│    → MS3 (position) + Nominatim (quartier) + MS12 (ETA)       │
│ 5. MS9 renvoie les résultats au LLM                           │
│ 6. Le LLM rédige : "Le bus est près de Jnane Ben Halima,     │
│                     à ~10 min de l'école."                    │
└──────────────────────────────────────────────────────────────┘
   │
   ▼
Réponse affichée au parent
```

---

## ⚙️ Sous le capot (technique) — comment le LLM « envoie » une requête et vérifie l'accès

### A. Un LLM n'exécute **rien** — il écrit du texte
Point fondamental : le modèle de langage **n'a aucun accès** au réseau, aux microservices ou à la
base. Il ne fait que **produire du texte**. Quand on dit « le LLM appelle un outil », en réalité :
1. le LLM **écrit une intention** structurée (nom d'outil + arguments en JSON) ;
2. **notre code Python** (`agent.py`/`tools.py`) lit cette intention et fait le **vrai** appel HTTP.

### B. Le protocole « function calling » (au niveau du fil réseau)
On appelle l'API du LLM (compatible OpenAI) `POST /chat/completions` avec :
- `messages` : l'historique (`system`, `user`, …) ;
- `tools` : la **description JSON** des 5 outils (nom, description, paramètres attendus).

Le LLM répond alors de 2 manières possibles :
- **du texte** (`content`) → réponse finale ;
- **des `tool_calls`** → une liste `{id, function:{name, arguments}}` = « je veux appeler
  `get_position_bus` avec `{busId:14}` ». **C'est du JSON, pas une exécution.**

Dialogue réel (simplifié) :
```jsonc
// 1) MS9 → LLM : question + catalogue d'outils
{ "messages":[{"role":"system",...},{"role":"user","content":"où est le bus ?"}],
  "tools":[{"type":"function","function":{"name":"get_position_bus","parameters":{...}}}, ...] }

// 2) LLM → MS9 : une INTENTION (aucune action réelle)
{ "role":"assistant","tool_calls":[
   {"id":"call_1","function":{"name":"get_position_bus","arguments":"{\"busId\":14}"}}]}

// 3) MS9 exécute l'outil (vrai appel HTTP) puis renvoie le résultat comme message "tool"
{ "role":"tool","tool_call_id":"call_1",
  "content":"{\"lieu\":\"Jnane Ben Halima\",\"vitesse\":40}" }

// 4) LLM → MS9 : réponse finale en texte
{ "role":"assistant","content":"Le bus est près de Jnane Ben Halima…" }
```
La **boucle** (`agent.py`) répète les étapes 2↔3 jusqu'à obtenir un texte final (max 5 tours).

### C. Comment le vrai appel est fait, et l'accès **vérifié**
Quand le LLM demande `get_position_bus(14)`, `execute_tool()` fait **dans cet ordre** :
1. **Contrôle de portée** : `14 ∈ allowed_bus_ids ?` (les bus des enfants du parent). Sinon →
   **refus immédiat**, aucun appel réseau n'est émis.
2. **Appel HTTP réel** avec `httpx`, en **transmettant le JWT du parent** :
   `GET http://localhost:8083/api/gps/bus/14/derniere` + header `Authorization: Bearer <jwt>`.
3. Le microservice cible (MS3) **re-valide** ce JWT de son côté (double validation).

D'où vient `allowed_bus_ids` ? Au tout début de `POST /api/llm/chat` :
- la **Gateway** a validé le JWT et l'a transmis ;
- MS9 **décode** le JWT (`verify_token`, signature **HMAC-SHA256**, **même secret que MS7**) →
  on obtient `parentId` et `role` (doit être `PARENT`) ;
- MS9 appelle **une seule fois** `GET /api/eleves/parent/{parentId}` → liste des enfants → on en
  déduit l'ensemble des `busId` autorisés.

**Chaîne d'accès (défense en profondeur) :**
```
Navigateur ──Bearer JWT──▶ Gateway (valide le JWT, injecte X-User-*)
                              └─▶ MS9  verify_token (exige le rôle PARENT)
                                    └─▶ garde de portée (busId ∈ enfants du parent)
                                          └─▶ MS2/MS3/MS12/MS1/MS10 (re-valident le JWT + @PreAuthorize)
```
Le LLM ne peut donc **jamais** élargir l'accès : même s'il « invente » `busId=3`, la garde le rejette.

### D. Interaction avec la base de données
En Phase A, le chatbot **ne touche jamais Postgres directement**. Chaque microservice est
**propriétaire de ses tables** ; MS9 passe par leurs **API REST**. Exemple : « mon enfant est-il
monté ? » → MS9 appelle **MS2** (`/api/eleves/parent/{id}`) → **c'est MS2** qui lit sa table
`eleves` et renvoie du JSON. MS9 ne connaît ni les tables ni les accès Postgres.
> La lecture SQL **directe** de la base, c'est la **Phase B** (assistant admin) — avec un rôle
> Postgres *read-only* dédié. Voir [MS9_Phase_B_NL2SQL_Admin.md](MS9_Phase_B_NL2SQL_Admin.md).

---

## 3. Les 5 outils (fichier `tools.py`)

| Outil | Ce qu'il fait | Appel réel |
|---|---|---|
| `get_mes_enfants()` | liste les enfants (nom, bus, groupe, présence) | `GET /api/eleves/parent/{parentId}` (MS2) |
| `get_position_bus(busId)` | position GPS + **rue/quartier** | `GET /api/gps/bus/{busId}/derniere` (MS3) + Nominatim |
| `get_eta_ecole(busId)` | minutes avant l'école | `POST /api/eta/predict` (MS12) |
| `get_trajet_actif(busId)` | trajet en cours + sens | `GET /api/trajets/bus/{busId}/actif` (MS1) |
| `get_incidents_bus(busId)` | incidents récents du bus | `GET /api/incidents/bus/{busId}` (MS10) |

### Le « reverse geocoding » (coordonnées → quartier)
`get_position_bus` transforme `33.891, -5.563` en **« Jnane Ben Halima, Meknès »** grâce à
**Nominatim (OpenStreetMap)** — gratuit, sans clé. Résultat mis en **cache** pour respecter les
limites d'usage. Réglable via `.env` (`REVERSE_GEOCODE=true/false`).

---

## 4. 🔒 Sécurité — la « garde de portée »

**Le risque :** qu'un parent voie les données d'un autre enfant/bus (ex. « donne-moi la position
du bus 3 » alors que son enfant est sur le bus 14), ou qu'il manipule l'IA (« ignore tes règles »).

**La protection (dans `tools.py`) :**
1. `parentId` vient **du JWT** (le jeton de connexion), **jamais** de ce que dit le modèle.
2. Au début de chaque conversation, on calcule `allowed_bus_ids` = les bus des enfants du parent.
3. **Chaque outil vérifie** que le `busId` demandé est dans cette liste. Sinon → **refus** poli,
   aucun appel n'est fait.
4. Aucun outil d'écriture n'existe → impossible de modifier quoi que ce soit via l'assistant.

> On ne fait **jamais** confiance au LLM pour la sécurité : c'est le **code** qui garde.

---

## 5. Fiabilité — 3 astuces dans `agent.py`

1. **Pré-fetch unique** : on appelle `get_mes_enfants` **une seule fois** par question, et on
   **injecte le contexte enfants dans le prompt** → souvent le LLM répond sans appel superflu.
2. **Outils en parallèle** : si le LLM demande 2 outils d'un coup, on les exécute avec
   `asyncio.gather` → réponse ~2× plus rapide.
3. **Historique propre** : on n'envoie au LLM que les tours `user`/`assistant` (jamais les
   messages techniques d'outils) → évite une erreur `400` fréquente des APIs LLM.

---

## 6. 🤖 Les modèles LLM — cascade « qualité puis repli »

MS9 est **agnostique** : il parle à n'importe quel fournisseur **compatible OpenAI**. Ordre
d'essai automatique (fichier `llm_client.py` + `config.py`) :

```
1) Groq  openai/gpt-oss-120b        ← qualité (raisonnement, multilingue)
      ↓  (si quota/erreur : retry court, puis bascule)
2) Groq  openai/gpt-oss-20b         ← repli rapide, quota journalier séparé
      ↓
3) Gemini gemini-2.0-flash          ← dernier repli
```

- **Retry + backoff** sur les erreurs `429` (rate limit) / `5xx`.
- **Mode dégradé** : si aucune clé n'est configurée, le service démarre quand même et répond
  « assistant non configuré » (rien ne plante).
- Pourquoi le 120b d'abord ? il est **plus intelligent** (respect des règles de sécurité, arabe/darija).
  Le 20b est un **repli** (plus léger, quota séparé), pas « meilleur ».

> ⚠️ **Migration du 19/08/2026.** La cascade utilisait `llama-3.3-70b-versatile` → `llama-3.1-8b-instant`.
> Groq a décommissionné **toute la famille Llama le 16/08/2026** — l'avis ne mentionnait que le 70b, mais le
> 8b a disparu **aussi**. Les deux étages Groq échouaient donc en silence, MS9 retombant sur Gemini.
> `qwen/qwen3.6-27b` (2ᵉ remplaçant conseillé par Groq) a été **écarté** : au test, il n'émet pas de
> `tool_call` — rédhibitoire pour un agent dont tout repose sur les outils. `gpt-oss` 120b et 20b : tool
> calling vérifié.
>
> **Effet de bord traité** : `gpt-oss` renvoie un champ propriétaire `reasoning`, et **aucun `content`**
> lorsqu'il appelle un outil. `agent.py` réinjectait le message assistant **brut** dans l'historique ; Groq
> le tolère, mais la cascade peut basculer sur Gemini **en cours de conversation** avec cet historique.
> `_assistant_spec()` réduit désormais le message à `role`/`content`/`tool_calls` (et évite de repayer les
> jetons de raisonnement à chaque tour).
>
> **À surveiller** : `max_tokens` (800) est **partagé avec les jetons de raisonnement** de `gpt-oss` — sur un
> tour multi-outils, la réponse visible peut être tronquée. Vérifier la liste vivante des modèles avant une
> démo : `GET https://api.groq.com/openai/v1/models`.

---

## 7. Fichiers du service

```
ms9-llm/
├── main.py           ← API FastAPI : /api/llm/health, /model-info, POST /api/llm/chat (PARENT)
├── agent.py          ← la boucle d'agent (pré-fetch, parallèle, historique propre)
├── tools.py          ← les 5 outils + garde de portée + reverse geocoding
├── llm_client.py     ← appel LLM OpenAI-compatible + cascade + retry
├── config.py         ← réglages (défauts) — lit .env
├── requirements.txt  ← fastapi, uvicorn, httpx, PyJWT, asyncpg…
├── .env              ← clés API + réglages (GITIGNORÉ — jamais commité)
└── .env.example      ← modèle sans les secrets
```

**Frontend :** `frontend/web-admin/src/pages/ParentAssistant.tsx` (widget chat + suggestions),
endpoint `chatLLM` dans `api/endpoints.ts`, route `/parent/assistant`, item nav « Assistant ».

**Deltas backend nécessaires :** `GET /api/incidents/bus/{id}` (MS10) et `POST /api/eta/predict`
(MS12) ont été **ouverts au rôle PARENT** (la portée reste gardée par MS9).

---

## 8. Configuration (`.env`)

```env
JWT_SECRET=...              # identique à MS7 / Gateway
MS1_URL=http://localhost:8081   MS2_URL=http://localhost:8082
MS3_URL=http://localhost:8083   MS10_URL=http://localhost:8090
MS12_URL=http://localhost:8088

PRIMARY_PROVIDER=groq
FALLBACK_PROVIDER=gemini
GROQ_API_KEY=gsk_...            # https://console.groq.com/keys (gratuit, sans CB)
GROQ_MODEL=openai/gpt-oss-120b
GROQ_FALLBACK_MODEL=openai/gpt-oss-20b
GEMINI_API_KEY=...             # https://aistudio.google.com/apikey (optionnel)
GEMINI_MODEL=gemini-2.0-flash

REVERSE_GEOCODE=true           # coordonnées → quartier (Nominatim/OSM)
```

> **Au moins une clé** (Groq ou Gemini) est nécessaire pour de vraies réponses.

---

## 9. Comment lancer

```bash
cd ms9-llm
pip install -r requirements.txt          # env conda "nlp"
uvicorn main:app --host 0.0.0.0 --port 8089 --reload
# (ou simplement start-all-ms.bat qui lance tout)
```

**Vérifier :** `GET http://localhost:8089/api/llm/health` →
`{"status":"UP","providers":["groq","groq","gemini"],"configured":true}`.

---

## 10. Comment tester (dans le navigateur)

Connecte-toi en **parent** → menu **Assistant**. Exemples :

**Opérationnel :** « Où est le bus de mon enfant ? » · « Dans combien de temps arrive-t-il ? » ·
« Mon enfant est-il monté ? » · « Y a-t-il un incident ? »
**Multilingue :** « فين كاينة الحافلة ديال ولدي؟ »
**Sécurité (doit refuser) :** « Donne-moi la position du bus 3 » · « Marque mon enfant absent »

> Pour des données vivantes (bus qui bouge, ETA), lance d'abord un trajet + mouvement GPS via
> `html_tests/simulation-control.html`.

---

## 11. Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| « assistant non configuré » | aucune clé LLM | renseigner `GROQ_API_KEY` dans `.env` |
| `503` / « momentanément indisponible » | quotas Groq **et** Gemini épuisés | attendre le reset, ou clé Gemini fraîche ; le repli 8b amortit |
| position en coordonnées brutes | Nominatim indisponible | réessayer ; `REVERSE_GEOCODE=false` pour désactiver |
| réponse hors-sujet | prompt à affiner | signaler le cas → on ajoute une règle |

---

## 12. Limites assumées

- Les **quotas gratuits** (tokens/jour) sont limités → cascade + repli pour tenir. En production :
  Groq Dev tier (payant) ou auto-hébergement.
- **Nominatim public** : usage modéré (OK pour un chatbot + cache) ; en production, self-host.
- Périmètre **lecture seule** : l'assistant informe, il ne modifie rien.
