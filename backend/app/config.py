# App settings, loaded from environment variables / backend/.env.
# Field names are matched case-insensitively against env var names by
# pydantic-settings, e.g. supabase_url <- SUPABASE_URL.

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Supabase project connection info. Service role key is required for
    # backend writes (e.g. /ingest/csv updating signal_snapshot) since it
    # bypasses row-level security; anon key is unused by this service so far.
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    # Groq (LLM brief generation, see app/groq_client.py). Empty api_key
    # means "not configured" — the brief pipeline falls back to a
    # deterministic brief rather than failing, so this is safe to leave blank.
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"

    backend_port: int = 8000
    # Comma-separated list of origins allowed to call this API (CORS).
    # 5173 is Vite's default dev port (frontend is React/Vite, not Next.js).
    cors_allowed_origins: str = "http://localhost:5173"

    # Google OAuth2 (Gmail metadata + Calendar pull, stretch goal). The
    # refresh token must have been granted with metadata-only Gmail scope
    # and read-only Calendar scope — see backend/.env.example.
    google_client_id: str = ""
    google_client_secret: str = ""
    google_refresh_token: str = ""

    @property
    def cors_origins(self) -> list[str]:
        # Split the raw comma-separated env value into a clean list for
        # CORSMiddleware, dropping empty entries from stray commas/whitespace.
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


# Singleton settings instance, imported wherever config is needed.
settings = Settings()
