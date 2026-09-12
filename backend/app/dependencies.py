"""Shared FastAPI request dependencies used across routers."""

from fastapi import HTTPException
from supabase import Client

from app.db import get_supabase_client


def require_supabase_client() -> Client:
    # Wraps get_supabase_client() so a missing SUPABASE_* config surfaces as
    # a clean 503 instead of an unhandled 500.
    try:
        return get_supabase_client()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
