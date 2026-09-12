# Tests for app/groq_client.py — no real network calls (the "configured"
# case only checks that a real provider was built, not that it can reach
# Groq; see test_brief_generation.py for how the safe fallback works when a
# provider genuinely fails).

import pytest

from app.groq_client import get_brief_provider
from retention_radar.groq import GroqBriefProvider


def test_get_brief_provider_returns_unconfigured_when_no_api_key(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "groq_api_key", "")
    provider = get_brief_provider()
    with pytest.raises(RuntimeError, match="not configured"):
        provider.generate("any prompt")


def test_get_brief_provider_returns_real_provider_when_configured(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "groq_api_key", "fake-key-for-test")
    monkeypatch.setattr(settings, "groq_model", "some-model")
    provider = get_brief_provider()
    assert isinstance(provider, GroqBriefProvider)
