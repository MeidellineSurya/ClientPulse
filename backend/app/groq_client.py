"""Builds the Groq-backed brief provider for the scoring pipeline.

Reuses retention_radar's tested BriefProvider implementation (evidence-bound
prompt, JSON-mode Groq call, prompt-injection-aware system message) instead
of building a second Groq client — see app/services/brief_generation.py for
where this plugs into scoring.
"""

from app.config import settings
from retention_radar.briefs import BriefProvider
from retention_radar.groq import GroqBriefProvider


class _UnconfiguredProvider:
    """Used when GROQ_API_KEY isn't set. briefs.generate_brief()'s broad
    except catches whatever this raises and falls back to the deterministic
    brief — so scoring always writes *some* brief, LLM-backed or not."""

    def generate(self, prompt: str) -> dict:
        raise RuntimeError("GROQ_API_KEY is not configured")


def get_brief_provider() -> BriefProvider:
    if not settings.groq_api_key:
        return _UnconfiguredProvider()
    return GroqBriefProvider(api_key=settings.groq_api_key, model=settings.groq_model)
