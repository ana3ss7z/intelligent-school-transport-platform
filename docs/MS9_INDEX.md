# MS9 — Assistant LLM : index de la documentation

MS9 est le microservice d'assistant intelligent (FastAPI, port **8089**). Il a **deux parties
indépendantes**, chacune avec sa propre documentation détaillée :

| Partie | Pour qui | Ce que ça fait | Documentation |
|---|---|---|---|
| **Phase A — Chatbot parent** | rôle **PARENT** | Questions temps réel (« où est le bus ? ») via **appel d'outils** aux microservices, scopé aux enfants du parent | 📄 [MS9_Phase_A_Chatbot_Parent.md](MS9_Phase_A_Chatbot_Parent.md) |
| **Phase B — Assistant NL2SQL admin** | rôle **ADMIN** | Questions analytiques (« quel bus a le plus d'incidents ? ») → **SQL généré** → exécution **read-only** → réponse chiffrée | 📄 [MS9_Phase_B_NL2SQL_Admin.md](MS9_Phase_B_NL2SQL_Admin.md) |

> 📄 [MS9_chatbot_LLM.md](MS9_chatbot_LLM.md) = document de **recherche** initial (offres LLM gratuites 2026, choix de stack).

## Points communs aux deux parties
- **Fournisseurs LLM en cascade** : `Groq 70b → Groq 8b → Gemini` (agnostique OpenAI-compatible, retry/backoff, mode dégradé sans clé).
- **Sécurité** : JWT par rôle ; on ne fait **jamais** confiance au LLM (le code/DB garde).
- **Multilingue** : français, arabe, darija.
- Route Gateway : `/api/llm/**`. Endpoints : `/api/llm/chat` (parent), `/api/llm/admin/query` (admin), `/api/llm/health`.
- Lancement : inclus dans `start-all-ms.bat` (env conda `nlp`). Clés & secrets dans `ms9-llm/.env` (gitignoré).
