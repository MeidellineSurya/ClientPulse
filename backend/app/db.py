# Supabase client factory for backend writes.

import time
from functools import lru_cache
from typing import Callable, TypeVar

import httpx
from supabase import Client, create_client

from app.config import settings

T = TypeVar("T")

# The single cached client's connection pool is shared by every concurrent
# request, so a burst (e.g. the frontend loading per-account history for a
# whole portfolio at once) can drop a connection mid-request. Retrying once
# is enough in practice — see with_retry.
RETRY_ATTEMPTS = 2
RETRY_DELAY_SECONDS = 0.15


@lru_cache
def get_supabase_client() -> Client:
    # Cached so the same client (and its connection pool) is reused across
    # requests instead of reconnecting every call.
    if not settings.supabase_url or not settings.supabase_service_role_key:
        # Raised as a plain RuntimeError (not an HTTPException) so this
        # module stays usable outside of FastAPI, e.g. from future scripts.
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set to use the Supabase client")
    # Service role key bypasses row-level security, which the backend needs
    # in order to write to signal_snapshot on behalf of any account.
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def with_retry(call: Callable[[], T]) -> T:
    """Retries a Supabase call once on a transient network disconnect. Re-raises
    the underlying httpx error on final failure — main.py's exception handler
    turns that into a 503 for any caller that doesn't handle it more specifically."""
    last_error: httpx.TransportError | None = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return call()
        except httpx.TransportError as exc:
            last_error = exc
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_DELAY_SECONDS)
    assert last_error is not None
    raise last_error
