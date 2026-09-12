# Supabase client factory for backend writes.

from functools import lru_cache

from supabase import Client, create_client

from app.config import settings


@lru_cache
def get_supabase_client() -> Client:
    # Cached so the same client (and its connection pool) is reused across
    # requests instead of reconnecting every call.
    if not settings.supabase_url or not settings.supabase_service_role_key:
        # Raised as a plain RuntimeError (not an HTTPException) so this
        # module stays usable outside of FastAPI, e.g. from future scripts.
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set to write to signal_snapshot"
        )
    # Service role key bypasses row-level security, which the backend needs
    # in order to write to signal_snapshot on behalf of any account.
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
