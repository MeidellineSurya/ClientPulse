# Tests for app/services/brief_generation.py — the bridge between our
# scoring engine and retention_radar's brief generator. No real network
# calls: the provider is always a fake injected via monkeypatch.

from app.services.brief_generation import build_alert_brief
from app.services.scoring_engine import AccountScoringResult


def _result(**overrides) -> AccountScoringResult:
    defaults = dict(
        composite_score=92.0,
        trend_slope=8.0,
        baselines={},
        drifts={"avg_response_time_hours": 0.9, "meetings_cancelled": 0.4},
        alert_fired=True,
        severity="critical",
        signals_fired=["avg_response_time_hours", "meetings_cancelled"],
        signal_contributions={"avg_response_time_hours": 60.0, "meetings_cancelled": 40.0},
        period_scores=[70.0, 82.0, 92.0],
    )
    defaults.update(overrides)
    return AccountScoringResult(**defaults)


class _FakeProvider:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error

    def generate(self, prompt: str) -> dict:
        if self._error is not None:
            raise self._error
        return self._response


def test_build_alert_brief_uses_llm_response_when_valid(monkeypatch):
    fake = _FakeProvider(
        response={
            "summary": "Acme is showing sustained response-time and cancellation drift.",
            "drivers": ["Response time is climbing.", "Cancellations are up."],
            "suggested_action": "Schedule a check-in call this week.",
        }
    )
    monkeypatch.setattr("app.services.brief_generation.get_brief_provider", lambda: fake)

    ai_brief, suggested_action = build_alert_brief("Acme", 10000, _result())

    assert "Acme is showing sustained" in ai_brief
    assert "- Response time is climbing." in ai_brief
    assert "- Cancellations are up." in ai_brief
    assert suggested_action == "Schedule a check-in call this week."


def test_build_alert_brief_falls_back_when_provider_errors(monkeypatch):
    fake = _FakeProvider(error=RuntimeError("network down"))
    monkeypatch.setattr("app.services.brief_generation.get_brief_provider", lambda: fake)

    ai_brief, suggested_action = build_alert_brief("Acme", 10000, _result())

    assert "Acme" in ai_brief
    assert "92" in ai_brief
    assert suggested_action == "Review the account internally and agree on the next human follow-up."


def test_build_alert_brief_falls_back_when_llm_response_fails_validation(monkeypatch):
    # Missing required fields -> retention_radar.briefs._validated raises,
    # which generate_brief() itself catches and turns into its own
    # (identical-shaped) fallback — still succeeds, just never touches our
    # except block.
    fake = _FakeProvider(response={"summary": "ok"})
    monkeypatch.setattr("app.services.brief_generation.get_brief_provider", lambda: fake)

    ai_brief, suggested_action = build_alert_brief("Acme", 10000, _result())

    assert "Acme" in ai_brief
    assert suggested_action


def test_build_alert_brief_falls_back_for_low_severity_not_accepted_by_brief_context(monkeypatch):
    # BriefContext only accepts medium/high/critical — "low" makes
    # constructing it raise, caught by build_alert_brief's own except.
    fake = _FakeProvider(response={"summary": "should never be reached"})
    monkeypatch.setattr("app.services.brief_generation.get_brief_provider", lambda: fake)

    result = _result(severity="low", signals_fired=[], signal_contributions={})
    ai_brief, suggested_action = build_alert_brief("Acme", 10000, result)

    assert "Acme" in ai_brief
    assert "low" in ai_brief
    assert suggested_action == "Review the account internally and agree on the next human follow-up."
