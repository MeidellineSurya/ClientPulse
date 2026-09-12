"""Retention Radar alert and brief-generation public API."""

from .alerts import AlertDecision, HealthScore, evaluate_alert
from .briefs import AccountBrief, BriefContext, generate_brief
from .groq import GroqBriefProvider
from .service import GeneratedAlert, build_alert

__all__ = [
    "AccountBrief",
    "AlertDecision",
    "BriefContext",
    "GeneratedAlert",
    "GroqBriefProvider",
    "HealthScore",
    "build_alert",
    "evaluate_alert",
    "generate_brief",
]
