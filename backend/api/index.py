# Vercel Python entrypoint. Vercel's @vercel/python runtime auto-detects an
# ASGI app named `app` in this file — this just re-exports the real FastAPI
# app so the actual application code stays framework-deployment-agnostic in
# app/main.py (also runnable locally via `uvicorn app.main:app`).
from app.main import app

__all__ = ["app"]
