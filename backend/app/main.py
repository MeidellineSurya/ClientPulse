# FastAPI app entrypoint for the ingestion service. Run with:
#   uvicorn app.main:app --port 8000

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import accounts, alerts, ingest, scoring

app = FastAPI(title="ClientPulse Ingestion Service")


# Safety net for any Supabase call whose retry (see app/db.py's with_retry)
# still failed - turns a raw connection error into a clean 503 instead of an
# unhandled 500, wherever it happens to surface.
@app.exception_handler(httpx.TransportError)
def handle_transport_error(_request: Request, _exc: httpx.TransportError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "upstream service unavailable"})

# Mount the /ingest/*, /score/*, /accounts/*, and /alerts/* routers.
app.include_router(ingest.router)
app.include_router(scoring.router)
app.include_router(accounts.router)
app.include_router(alerts.router)

# Allow the frontend (origins from CORS_ALLOWED_ORIGINS) to call this API
# from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    # Liveness check for the harness this ingestion code runs inside.
    return {"status": "ok"}
