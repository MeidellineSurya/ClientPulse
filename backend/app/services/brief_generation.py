"""Bridges the deterministic scoring engine to retention_radar's tested
Groq brief generator, so the AI-brief step reuses their evidence-bound
prompt, JSON-schema validation, and safe deterministic fallback instead of
a second implementation being built here.

The score and alert decision are already final by the time this runs (see
scoring_engine.py) — this module only turns that decision into a
plain-language explanation. It can never change the score or the alert.
"""

from app.groq_client import get_brief_provider
from app.services.scoring_engine import AccountScoringResult
from retention_radar.briefs import BriefContext, generate_brief

# BriefContext.__post_init__ only accepts severity in {"medium", "high",
# "critical"} (see retention_radar/briefs.py) — our engine's "low" band
# isn't one of them, so constructing BriefContext raises ValueError for a
# low-severity alert. Caught below: it still gets *a* brief, just always
# the deterministic fallback, never an LLM-generated one.

# Mirrors frontend/src/lib/format.ts's healthTier bucketing exactly, so a
# brief's "watch"/"at-risk" language always agrees with what the Portfolio
# and Account Detail pages show for the same score.
def _score_tier_label(score_0_to_100: float) -> str:
    if score_0_to_100 >= 60:
        return "at-risk"
    if score_0_to_100 >= 30:
        return "watch"
    return "healthy"


def build_alert_brief(
    account_name: str, contract_value_monthly: float, result: AccountScoringResult
) -> tuple[str, str]:
    """Returns (ai_brief, suggested_action) for a fired alert. Always
    succeeds: falls back to a deterministic brief if Groq isn't configured,
    the request fails, or the response fails validation, or this account's
    severity/history shape doesn't fit BriefContext's constraints.
    """
    try:
        if result.severity is None:
            raise ValueError("a fired alert must have a severity")
        recent_period_scores = result.period_scores[-3:]
        recent_scores = tuple(score / 100 for score in recent_period_scores)
        context = BriefContext(
            account_name=account_name,
            monthly_value=contract_value_monthly,
            composite_risk=result.composite_score / 100,
            severity=result.severity,
            triggered_signals={signal: result.drifts[signal] for signal in result.signals_fired},
            recent_scores=recent_scores,
            signal_current_values={
                signal: result.current_values[signal]
                for signal in result.signals_fired
                if signal in result.current_values
            },
            signal_baseline_averages={
                signal: result.baselines[signal][0]
                for signal in result.signals_fired
                if signal in result.baselines
            },
            recent_score_labels=tuple(_score_tier_label(score) for score in recent_period_scores),
        )
        brief = generate_brief(context, get_brief_provider())
    except Exception:  # noqa: BLE001 - every provider failure must use the safe fallback
        return (
            (
                f"{account_name} is at {result.composite_score:.0f} "
                f"({result.severity or 'elevated'}) retention risk after a worsening trend."
            ),
            "Review the account internally and agree on the next human follow-up.",
        )

    ai_brief = "\n".join([brief.summary, *(f"- {driver}" for driver in brief.drivers)])
    return ai_brief, brief.suggested_action
