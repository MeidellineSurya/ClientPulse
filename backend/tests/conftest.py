# Test-suite-wide fixtures.

import pytest

from app.main import app


@pytest.fixture(autouse=True)
def _clear_dependency_overrides():
    """Keep FastAPI dependency overrides isolated to one test."""
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _no_real_groq_calls(monkeypatch):
    """Force "Groq not configured" for every test by default.

    Without this, any test that fires an alert calls the real
    app.services.brief_generation -> app.groq_client -> retention_radar.groq
    chain, which reads settings.groq_api_key fresh on every call (it isn't
    injected via FastAPI's dependency-override system the way the Supabase
    client is). Whatever's in a developer's local backend/.env would then
    leak into the test suite as a real, slow, cost-incurring network call to
    Groq — this forces the safe deterministic-fallback path every test
    actually wants instead, exactly as a fresh clone with no GROQ_API_KEY
    would behave.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "groq_api_key", "")
