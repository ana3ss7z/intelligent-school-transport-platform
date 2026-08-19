
# resumé of free apis form multiple sources with notebooklm

En 2026, le marché de l'intelligence artificielle propose des offres gratuites extrêmement généreuses, permettant de construire des systèmes complexes sans budget d'infrastructure initial. Voici un résumé détaillé des plans gratuits disponibles pour les modèles et services d'IA.

### Master Comparaison des Fournisseurs d'Inférence (Avril 2026)
Le tableau suivant récapitule les offres majeures pour l'inférence de modèles de langage (LLM) :

| Fournisseur | Jetons (Tokens) / Jour | Requêtes / Jour | Carte Bancaire ? | Modèle phare gratuit |
| :--- | :--- | :--- | :--- | :--- |
| **Google AI Studio** | Illimité (sous réserve de RPM) | 1 000 – 1 500 | Non | Gemini 3.5 Flash |
| **Cerebras** | 1 000 000 | 14 400 | Non | Qwen3 235B Instruct |
| **Groq** | 500K – 1M | 1 000 – 14 400 | Non | Llama 4 Scout |
| **Mistral AI** | ~1 Milliard / mois | 60 RPM | Non (tél. requis) | Mistral Large / Codestral |
| **NVIDIA NIM** | Basé sur crédits (91 modèles) | 40 RPM | Non | DeepSeek V3.2 |
| **OpenRouter** | 200K – 1M+ | 50 – 1 000 | Non | DeepSeek R1 / Qwen3 480B |
| **Cloudflare** | 10K "Neurons" / jour | Illimité | Non | Llama 3.3 70B |

---

### Détails des Offres par Catégorie

#### 1. Géants de la Frontière (Google, OpenAI, Anthropic)
*   **Google Gemini (AI Studio)** : L'offre la plus généreuse pour le prototypage. Elle propose une fenêtre de contexte massive de **1 à 2 millions de tokens**. Gemini 3.5 Flash autorise **1 500 requêtes/jour**. Attention : les données du tier gratuit sont utilisées pour l'entraînement des modèles.
*   **OpenAI API** : Offre généralement un petit crédit initial (5-18 $) qui expire après 3 mois. Il n'y a pas d'offre gratuite continue après épuisement.
*   **Anthropic (Claude)** : Propose des crédits limités à l'inscription pour tester Claude Haiku.

#### 2. Inférence Haute Performance (Custom Silicon)
*   **Groq (LPU)** : Spécialisé dans la vitesse avec des temps de réponse inférieurs à 100ms. Le tier gratuit offre **30 000 tokens/minute (TPM)** et **14 400 requêtes/jour (RPD)** sur des modèles comme Llama 4 Scout et DeepSeek R1.
*   **Cerebras (WSE)** : Offre le débit le plus élevé (2 600+ tok/s) avec **1 million de tokens gratuits par jour** sur des modèles massifs comme Qwen3 235B.

#### 3. Plateformes Ouvertes et Spécialisées
*   **Mistral AI (La Plateforme)** : Propose un tier "Expérimentation" avec un quota mensuel exceptionnel de **1 milliard de tokens** pour les modèles open-weight. C'est l'option privilégiée pour la conformité RGPD.
*   **NVIDIA NIM** : Donne accès à **91 modèles** couvrant non seulement le langage, mais aussi la vision, la biologie et la simulation climatique.

---

### Infrastructure RAG et Geospatiale
Pour les projets complets (comme le transport scolaire), d'autres briques sont essentielles :

#### Embeddings et Reranking
*   **Voyage AI** : Offre **200 millions de tokens gratuits** pour l'indexation (modèle voyage-4-lite), ce qui est suffisant pour des bases de données massives.
*   **Cohere** : Propose une clé d'essai pour **1 000 appels/mois** de leur service de Rerank, essentiel pour la précision de la recherche.

#### Bases de Données Vectorielles
*   **Pinecone Serverless** : 2 Go de stockage gratuit, permettant de gérer environ **300 000 vecteurs**.
*   **Qdrant Cloud** : Tier gratuit de **1 Go de RAM et 4 Go de disque**. L'activation de la "Binary Quantization" peut multiplier la capacité par 32, permettant de stocker jusqu'à **8 millions de vecteurs**.

#### Services Géospatiaux
*   **OpenRouteService (ORS)** : Entièrement gratuit, il offre **500 appels d'optimisation/jour** (problèmes de tournées) et **2 000 calculs d'itinéraires**.
*   **Mapbox** : Inclut **50 000 chargements de cartes** et **100 000 requêtes de directions** par mois.
*   **Google Maps** : A remplacé son crédit forfaitaire par des quotas par SKU, par exemple **10 000 événements gratuits** pour les cartes statiques, mais seulement **1 000** pour l'optimisation de flotte.

### Points de vigilance critiques
*   **Le Piège de la Facturation (Google)** : Activer la facturation sur un projet Google Cloud peut supprimer immédiatement les quotas gratuits d'AI Studio pour ce projet.
*   **Expiration et Volatilité** : Les modèles disponibles sur Cerebras ou Groq peuvent changer sans préavis. Les crédits chez OpenAI ou Anthropic expirent rapidement.
*   **Limites de Jetons (TPM)** : C'est souvent la limite par minute (TPM) qui bloque les applications réelles avant même d'atteindre la limite journalière (RPD).




----

# gemini recommendations 

C'est une excellente clarification ! Le Cahier des Charges (CDC) cadre **très précisément** la vision de votre microservice **MS9 (Service assistant intelligent LLM)**.

Ce CDC transforme votre chatbot : au lieu d'un simple RAG sur des documents statiques (PDF/Règlements), MS9 devient un **Agent IA Opérationnel & Analytique (Tool Calling + NL2SQL)**.

---

## 🎯 Ce que le CDC change concrètement pour MS9

Le CDC (sections **5.7**, **6.11** et **7**) découpe le microservice assistant intelligent en **2 piliers complémentaires** :

```
                                  ┌──────────────────────────────────────────┐
                                  │          MS9 — Service Assistant LLM     │
                                  │                (FastAPI :8089)           │
                                  └────────────────────┬─────────────────────┘
                                                       │
                   ┌───────────────────────────────────┴───────────────────────────────────┐
                   ▼                                                                       ▼
    ┌─────────────────────────────┐                                         ┌─────────────────────────────┐
    │     1. Chatbot Parents      │                                         │   2. Assistant Admin        │
    │   (Opérationnel / Live)     │                                         │        (NL2SQL)             │
    ├─────────────────────────────┤                                         ├─────────────────────────────┤
    │ • Introvisibilité temps réel│                                         │ • Traduction de questions   │
    │ • Tool Calling (APIs REST)  │                                         │   en requêtes SQL           │
    │ • Contexte : GPS, ETA,      │                                         │ • Interrogation de la BDD   │
    │   Présence enfant, Incidents│                                         │   (retards, assiduité, etc.)│
    │ • Multilingue (FR / AR)     │                                         │ • Synthèse décisionnelle    │
    └─────────────────────────────┘                                         └─────────────────────────────┘

```

1. **Pour les Parents (Chatbot Temps Réel)** : L'utilisateur pose des questions opérationnelles (*"Où est le bus de mon fils ?"*, *"Mon enfant a-t-il été pris en charge ce matin ?"*). Le LLM utilise des **outils (Tool Calling / Function Calling)** pour interroger vos microservices internes (MS2 Élèves, MS3 GPS, MS12 ETA, MS10 Incidents).
2. **Pour les Administrateurs (Assistant Analytique / NL2SQL)** : L'admin pose des questions décisionnelles en langage naturel (*"Quel bus a eu le plus de retard cette semaine ?"*, *"Combien d'élèves étaient absents lundi ?"*). Le LLM convertit la question en **requête SQL (NL2SQL)**, l'exécute en lecture seule sur la base PostgreSQL, et formule une réponse claire avec les chiffres.
3. **Contrainte Multilingue** : Prise en charge native du **Français** et de l'**Arabe** (Standard / Darija).

---

## 🏆 Stack Recommandée pour MS9 (100% Gratuite, 0 DH, Sans CB)

Pour répondre parfaitement à cette double exigence (Function Calling + NL2SQL + Arabe/Français) avec les offres 2026 gratuites :

| Composant | Technologie Recommandée | Pourquoi ce choix pour votre PFE ? |
| --- | --- | --- |
| **LLM Principal** | **Google AI Studio** (`gemini-2.0-flash` ou `gemini-1.5-flash`) | **0 DH / Sans CB.** Modèle souverain pour le **Tool Calling**, la génération de **code SQL**, et le multilingue (Français/Arabe parfait). 1 500 req/jour offertes. |
| **LLM Secours / Vitesse** | **Groq Cloud** (`openai/gpt-oss-120b`) | Inférence sous les 200 ms. Idéal en plan B pour le chatbot parent. *(Ce document date de l'étude préalable ; à la réalisation, Groq est devenu le **principal** et Gemini le dernier repli — cf. `MS9_Phase_A_Chatbot_Parent.md`. `llama-3.3-70b-versatile`, retenu à l'origine, a été **décommissionné le 16/08/2026**.)* |
| **Framework Agent IA** | **FastAPI + LangChain / LangGraph** (ou SDK `google-genai`) | Gestion simplifiée de l'agent à outils (Tools) et de la chaîne NL2SQL (`SQLDatabaseChain`). |
| **Accès BDD (NL2SQL)** | **PostgreSQL** (Connexion Read-Only) | Accès direct aux vues/tables analytiques de votre base globale pour l'admin. |

---

## 📐 Architecture Technique Détaillée de MS9

### Pilier 1 : Le Chatbot Parent (Mode Agent & Tools)

Lorsqu'un parent connecté interroge MS9, le LLM ne devine pas la réponse : il **exécute des fonctions Python** (Tools) qui appellent vos microservices Spring Boot / FastAPI existants.

* `get_enfant_presence(parent_id)` $\rightarrow$ Appel **MS2** (`GET /api/eleves/parent/{parentId}`)
* `get_bus_position(bus_id)` $\rightarrow$ Appel **MS3** (`GET /api/localisation/bus/{busId}`)
* `get_eta_prediction(bus_id, stop_id)` $\rightarrow$ Appel **MS12** (`POST /api/eta/predict`)
* `get_incidents_recents(bus_id)` $\rightarrow$ Appel **MS10** (`GET /api/incidents`)

### Pilier 2 : L'Assistant Admin (Mode NL2SQL)

Lorsqu'un administrateur pose une question statistique, MS9 utilise un pipeline NL2SQL sécurisé :

1. **Prompt avec Schéma BDD** : On fournit au LLM le schéma DDL des tables (`eleves`, `bus`, `incidents`, `historique_presence`).
2. **Génération SQL** : Gemini traduit la question en requête PostgreSQL (ex: `SELECT bus_id, COUNT(*) FROM incidents WHERE date >= NOW() - INTERVAL '7 days' GROUP BY bus_id ORDER BY count DESC LIMIT 1;`).
3. **Exécution Sécurisée** : Connexion PostgreSQL en **Lecture Seule (SELECT uniquement)**.
4. **Synthèse LLM** : Le LLM met en forme le résultat brut sous forme de phrase claire ou de mini-tableau.

---
