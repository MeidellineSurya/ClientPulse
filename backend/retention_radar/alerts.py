"""Deterministic retention-risk alert evaluation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import pairwise
from math import isfinite


@dataclass(frozen=True)
class HealthScore:
    account_id: str
    computed_at: datetime
    composite_risk: float
    signal_drifts: Mapping[str, float]

    def __post_init__(self) -> None:
        if not isinstance(self.account_id, str) or not self.account_id.strip():
            raise ValueError("account_id must be a non-empty string")
        if not isinstance(self.computed_at, datetime):
            raise TypeError("computed_at must be a datetime")
        if self.computed_at.tzinfo is None or self.computed_at.utcoffset() is None:
            raise ValueError("computed_at must be timezone-aware")
        if (
            isinstance(self.composite_risk, bool)
            or not isinstance(self.composite_risk, (int, float))
            or not isfinite(self.composite_risk)
            or not 0.0 <= self.composite_risk <= 1.0
        ):
            raise ValueError("composite_risk must be finite and between 0 and 1")
        for name, value in self.signal_drifts.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("each signal name must be a non-empty string")
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
                or not 0.0 <= value <= 1.0
            ):
                raise ValueError("each signal drift must be finite and between 0 and 1")


@dataclass(frozen=True)
class AlertDecision:
    should_alert: bool
    severity: str | None = None
    signals_fired: tuple[str, ...] = ()
    episode_key: str | None = None
    reason: str = ""


def evaluate_alert(
    history: Sequence[HealthScore],
    *,
    threshold: float = 0.65,
    alerted_episode_keys: frozenset[str] | set[str] = frozenset(),
) -> AlertDecision:
    """Fire only on a threshold crossing backed by three worsening periods."""
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0 and 1")
    if len({item.account_id for item in history}) > 1:
        raise ValueError("health-score history must belong to one account")
    if len({item.computed_at for item in history}) != len(history):
        raise ValueError("health-score history must contain distinct period timestamps")
    if len(history) < 3:
        return AlertDecision(False, reason="insufficient_history")

    latest = sorted(history, key=lambda item: item.computed_at)[-3:]
    previous, current = latest[-2], latest[-1]
    worsening = all(
        left.composite_risk < right.composite_risk for left, right in pairwise(latest)
    )
    crossed = previous.composite_risk < threshold <= current.composite_risk
    if not (worsening and crossed):
        return AlertDecision(False, reason="threshold_and_trend_not_met")

    episode_key = (
        f"{current.account_id}:{current.computed_at.astimezone(UTC).isoformat()}"
    )
    if episode_key in alerted_episode_keys:
        return AlertDecision(
            False, episode_key=episode_key, reason="episode_already_alerted"
        )

    score = current.composite_risk
    severity = "critical" if score >= 0.90 else "high" if score >= 0.80 else "medium"
    signals = tuple(
        sorted(
            name for name, drift in current.signal_drifts.items() if drift >= threshold
        )
    )
    return AlertDecision(
        True, severity, signals, episode_key, "threshold_crossed_with_worsening_trend"
    )
