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

    ecole_lat: float = 33.893
    ecole_lng: float = -5.5455

    # ── Reverse geocoding (coordonnées → rue/quartier), OSM/Nominatim (gratuit, sans clé) ──
    reverse_geocode: bool = True
    nominatim_url: str = "https://nominatim.openstreetmap.org/reverse"
    geo_lang: str = "fr"
    geo_user_agent: str = "transport-scolaire-meknes/1.0 (PFE)"

    # JWT — DOIT être identique à app.jwt.secret dans MS7 / Gateway
    jwt_secret: str = "transport_scolaire_secret_key_2026_super_long"

    # ── Fournisseurs LLM (OpenAI-compatible, interchangeables) ───────
    primary_provider: str = "groq"       # groq | gemini
    fallback_provider: str = "gemini"    # groq | gemini | "" (aucun)

    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.3-70b-versatile"
    # Repli Groq (budget journalier séparé) : modèle plus léger si le principal est saturé
    groq_fallback_model: str = "llama-3.1-8b-instant"

    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    gemini_model: str = "gemini-2.0-flash"

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

        Chaque modèle Groq a son propre quota journalier ; le repli 8b prend donc le relais
        automatiquement quand le 70b est saturé (au lieu d'échouer)."""
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
