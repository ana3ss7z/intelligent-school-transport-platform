"""Configuration MS9-LLM (pydantic-settings) — assistant conversationnel (Phase A : chatbot parent)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Réseau ───────────────────────────────────────────────────────
    port: int = 8089

    # URLs internes des microservices (appels d'outils avec le JWT du parent)
    ms1_url: str = "http://localhost:8081"   # bus / trajets
    ms2_url: str = "http://localhost:8082"   # élèves
    ms3_url: str = "http://localhost:8083"   # GPS
    ms10_url: str = "http://localhost:8090"  # incidents
    ms12_url: str = "http://localhost:8088"  # ETA
    ms13_url: str = "http://localhost:8092"  # paramètres (appel direct : /internal n'est pas routé)

    ecole_lat: float = 33.893
    ecole_lng: float = -5.5455

    # MS9 ne publie ni ne consomme d'événement métier ; il s'abonne uniquement à
    # `parametres.updated` pour recevoir à chaud un changement de modèle ou de clé API —
    # ce qui évite d'éditer `.env` et de redémarrer quand un fournisseur retire un modèle.
    rabbitmq_url: str = "amqp://admin:admin123@localhost:5672/"
    exchange_name: str = "transport.exchange"

    # ── Reverse geocoding (coordonnées → rue/quartier), OSM/Nominatim (gratuit, sans clé) ──
    reverse_geocode: bool = True
    nominatim_url: str = "https://nominatim.openstreetmap.org/reverse"
    geo_lang: str = "fr"
    geo_user_agent: str = "transport-scolaire-meknes/1.0 (PFE)"

    # JWT — DOIT être identique à app.jwt.secret dans MS7 / Gateway
    jwt_secret: str = "transport_scolaire_secret_key_2026_super_long"

    # ── NL2SQL admin (Phase B) : connexion Postgres READ-ONLY dédiée ──
    db_ro_host: str = "localhost"
    db_ro_port: int = 5432
    db_ro_name: str = "transport_scolaire"
    db_ro_user: str = "ms9_readonly"
    db_ro_password: str = ""          # = mot de passe du rôle ms9_readonly (.env)
    sql_max_rows: int = 200           # cap de lignes renvoyées
    sql_default_limit: int = 200      # LIMIT ajouté si absent
    sql_timeout_ms: int = 5000        # statement_timeout côté requête

    # ── Fournisseurs LLM (OpenAI-compatible, interchangeables) ───────
    primary_provider: str = "groq"       # groq | gemini
    fallback_provider: str = "gemini"    # groq | gemini | "" (aucun)

    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    # Groq a décommissionné TOUTE la famille Llama le 16/08/2026 : `llama-3.3-70b-versatile`
    # ET `llama-3.1-8b-instant` ont disparu de /v1/models (l'e-mail d'avis ne mentionnait que
    # le 70b). Remplacés par gpt-oss, seule famille encore servie qui appelle réellement les
    # outils — vérifié : gpt-oss 120b et 20b émettent bien un tool_call, `qwen/qwen3.6-27b`
    # (l'autre modèle conseillé) a répondu sans appeler l'outil, donc écarté pour cet agent.
    groq_model: str = "openai/gpt-oss-120b"
    # Repli Groq (budget journalier séparé) : modèle plus léger si le principal est saturé
    groq_fallback_model: str = "openai/gpt-oss-20b"

    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    gemini_model: str = "gemini-2.0-flash"

    # ── Socle de connaissances « école » (prompt parent) ─────────────
    # Faits vérifiés injectés dans le prompt système (school_facts.py). Le mettre à false permet de
    # mesurer l'écart avec/sans : sans socle, le modèle répond aux questions d'école de mémoire —
    # c'est-à-dire qu'il invente. Sert au comparatif d'évaluation.
    school_facts_enabled: bool = True

    # ── Paramètres d'inférence / agent ───────────────────────────────
    temperature: float = 0.2
    max_tokens: int = 800
    http_timeout: float = 30.0        # timeout appels LLM + outils (s)
    max_tool_iters: int = 5           # nb max de tours de boucle function-calling
    history_max_turns: int = 6        # nb max de tours user/assistant conservés

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", protected_namespaces=()
    )

    def provider_conf(self, name: str) -> dict | None:
        """Retourne {api_key, base_url, model} pour un provider, ou None si pas de clé."""
        if name == "groq" and self.groq_api_key:
            return {"api_key": self.groq_api_key, "base_url": self.groq_base_url, "model": self.groq_model}
        if name == "gemini" and self.gemini_api_key:
            return {"api_key": self.gemini_api_key, "base_url": self.gemini_base_url, "model": self.gemini_model}
        return None

    def providers_order(self) -> list[dict]:
        """Cascade ordonnée : primaire → repli Groq (modèle léger) → fallback provider.

        Chaque modèle Groq a son propre quota journalier ; le repli 20b prend donc le relais
        automatiquement quand le 120b est saturé (au lieu d'échouer)."""
        out: list[dict] = []

        def add(name: str, model_override: str | None = None):
            conf = self.provider_conf(name)
            if not conf:
                return
            entry = {**conf, "name": name}
            if model_override:
                entry["model"] = model_override
            if entry not in out:
                out.append(entry)

        add(self.primary_provider)
        # repli Groq (budget séparé) si le primaire est Groq
        if self.primary_provider == "groq" and self.groq_fallback_model:
            add("groq", self.groq_fallback_model)
        if self.fallback_provider:
            add(self.fallback_provider)
        return out


settings = Settings()
