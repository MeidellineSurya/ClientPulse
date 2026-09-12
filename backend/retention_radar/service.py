"""Application service joining deterministic alerts to LLM-authored briefs."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass

from .alerts import AlertDecision, HealthScore, evaluate_alert
from .briefs import AccountBrief, BriefContext, BriefProvider, generate_brief


@dataclass(frozen=True)
class GeneratedAlert:
    decision: AlertDecision
    brief: AccountBrief


def build_alert(
    history: Sequence[HealthScore],
    *,
    account_name: str,
    monthly_value: float,
    provider: BriefProvider,
    threshold: float = 0.65,
    alerted_episode_keys: Collection[str] = (),
) -> GeneratedAlert | None:
    """Return an alert and brief only when deterministic policy says to fire."""
    decision = evaluate_alert(
        history,
        threshold=threshold,
        alerted_episode_keys=set(alerted_episode_keys),
    )
    if not decision.should_alert:
        return None

    ordered = sorted(history, key=lambda item: item.computed_at)
    current = ordered[-1]
    triggered = {name: current.signal_drifts[name] for name in decision.signals_fired}
    context = BriefContext(
        account_name=account_name,
        monthly_value=monthly_value,
        composite_risk=current.composite_risk,
        severity=decision.severity or "medium",
        triggered_signals=triggered,
        recent_scores=tuple(item.composite_risk for item in ordered[-3:]),
    )
    return GeneratedAlert(decision=decision, brief=generate_brief(context, provider))
