# FastAPI app entrypoint for the ingestion service. Run with:
#   uvicorn app.main:app --port 8000

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import accounts, alerts, ingest, scoring

app = FastAPI(title="ClientPulse Ingestion Service")

# Mount the backend API routers.
app.include_router(accounts.router)
app.include_router(alerts.router)
app.include_router(ingest.router)
app.include_router(scoring.router)

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
