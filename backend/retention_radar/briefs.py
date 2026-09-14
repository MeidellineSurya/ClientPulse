"""Evidence-bound LLM briefs with a deterministic fallback."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from typing import Protocol


class BriefProvider(Protocol):
    def generate(self, prompt: str) -> Mapping[str, object]: ...


@dataclass(frozen=True)
class BriefContext:
    account_name: str
    monthly_value: float
    composite_risk: float
    severity: str
    triggered_signals: Mapping[str, float]
    recent_scores: tuple[float, ...]
    # Optional richer evidence, keyed the same as triggered_signals. When
    # present, the prompt cites the account's actual numbers ("14.2 hours,
    # usually 3.1") instead of only the abstract 0-1 drift ratio. Left empty
    # by callers that don't have raw values on hand (e.g. retention_radar's
    # own evaluate_alert path) — the brief degrades gracefully to the old
    # drift-only phrasing rather than failing.
    signal_current_values: Mapping[str, float] = field(default_factory=dict)
    signal_baseline_averages: Mapping[str, float] = field(default_factory=dict)
    # One label per recent_scores entry (same order, same length when set) —
    # e.g. ("healthy", "watch", "at-risk") — so the prompt can describe the
    # trend's actual shape instead of three bare numbers. None when the
    # caller doesn't have tier labels to offer.
    recent_score_labels: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.account_name, str) or not self.account_name.strip():
            raise ValueError("account_name must be a non-empty string")
        if (
            isinstance(self.monthly_value, bool)
            or not isinstance(self.monthly_value, (int, float))
            or not isfinite(self.monthly_value)
            or self.monthly_value < 0
        ):
            raise ValueError("monthly_value must be finite and non-negative")
        if (
            isinstance(self.composite_risk, bool)
            or not isinstance(self.composite_risk, (int, float))
            or not isfinite(self.composite_risk)
            or not 0.0 <= self.composite_risk <= 1.0
        ):
            raise ValueError("composite_risk must be between 0 and 1")
        if self.severity not in {"medium", "high", "critical"}:
            raise ValueError("severity must be medium, high, or critical")
        for name, drift in self.triggered_signals.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("each signal name must be a non-empty string")
            if (
                isinstance(drift, bool)
                or not isinstance(drift, (int, float))
                or not isfinite(drift)
                or not 0.0 <= drift <= 1.0
            ):
                raise ValueError("each signal drift must be between 0 and 1")
        if len(self.recent_scores) != 3 or any(
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not isfinite(score)
            or not 0.0 <= score <= 1.0
            for score in self.recent_scores
        ):
            raise ValueError("recent_scores must contain three values between 0 and 1")
        for label, values in (
            ("signal_current_values", self.signal_current_values),
            ("signal_baseline_averages", self.signal_baseline_averages),
        ):
            for name, value in values.items():
                if not isinstance(name, str) or not name.strip():
                    raise ValueError(f"each {label} name must be a non-empty string")
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                    raise ValueError(f"each {label} value must be a finite number")
        if self.recent_score_labels is not None and len(self.recent_score_labels) != len(self.recent_scores):
            raise ValueError("recent_score_labels must have one label per recent_scores entry")


@dataclass(frozen=True)
class AccountBrief:
    summary: str
    drivers: tuple[str, ...]
    suggested_action: str
    source: str


def _prompt(context: BriefContext) -> str:
    evidence = {
        "account_name": context.account_name,
        "monthly_value": context.monthly_value,
        "composite_risk": context.composite_risk,
        "severity": context.severity,
        "triggered_signals": dict(context.triggered_signals),
        "recent_scores": list(context.recent_scores),
    }
    instructions = [
        "Write an internal retention-risk brief using only the supplied evidence.",
        "The risk score is authoritative: do not calculate, revise, or contradict it.",
        "Explain drivers using only the supplied evidence, without overclaiming certainty, and do not contact the client.",
    ]
    # Only present when a caller has raw signal values on hand (see
    # BriefContext) — lets the brief cite this account's actual numbers
    # ("14.2 hours, usually 3.1") instead of only an abstract 0-1 ratio.
    if context.signal_current_values:
        evidence["signal_current_values"] = dict(context.signal_current_values)
        evidence["signal_baseline_averages"] = dict(context.signal_baseline_averages)
        instructions.append(
            "For each triggered signal, signal_current_values and "
            "signal_baseline_averages give this specific account's actual current "
            "and usual numbers — cite them directly (e.g. \"14.2 hours, usually "
            "around 3\") rather than describing drift as an abstract percentage."
        )
    if context.recent_score_labels is not None:
        evidence["recent_score_labels"] = list(context.recent_score_labels)
        instructions.append(
            "recent_score_labels gives a plain-language tier (e.g. healthy/watch/"
            "at-risk) for each entry in recent_scores, oldest first — describe the "
            "trend using these tiers, not just the bare numbers."
        )
    instructions.append(
        "Return JSON with exactly summary (string), drivers (1-4 strings), and "
        "suggested_action (string)."
    )
    return " ".join(instructions) + f"\nEVIDENCE={json.dumps(evidence, sort_keys=True)}"


def _text(value: object, field: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    cleaned = value.strip()
    if len(cleaned) > maximum:
        raise ValueError(f"{field} exceeds {maximum} characters")
    return cleaned


def _validated(payload: Mapping[str, object], *, source: str) -> AccountBrief:
    if set(payload) != {"summary", "drivers", "suggested_action"}:
        raise ValueError("brief response has unexpected fields")
    raw_drivers = payload["drivers"]
    if not isinstance(raw_drivers, list) or not 1 <= len(raw_drivers) <= 4:
        raise ValueError("drivers must contain between 1 and 4 strings")
    drivers = tuple(_text(driver, "driver", 250) for driver in raw_drivers)
    summary = _text(payload["summary"], "summary", 500)
    suggested_action = _text(payload["suggested_action"], "suggested_action", 300)
    policy_text = " ".join((summary, *drivers, suggested_action)).lower()
    # Ordinary causal connectors ("because", "due to", "led to", "caused") are
    # allowed — the brief is expected to tie evidence to the score, and the
    # scoring formula itself is a real causal relationship. What's actually
    # unsupported is claiming a level of certainty the evidence doesn't give.
    if re.search(
        r"\b(?:definitely|certainly|proven?|guaranteed?|undeniably|unquestionably)\b",
        policy_text,
    ):
        raise ValueError("brief makes an unsupported certainty claim")
    contact_verb = r"(?:contact|email|message|call|send)"
    urgency = r"(?:automatically|immediately)"
    if re.search(
        rf"\b(?:{urgency}\b.{{0,50}}\b{contact_verb}|{contact_verb}\b.{{0,50}}\b{urgency})\b",
        policy_text,
    ):
        raise ValueError("brief proposes unreviewed client contact")
    return AccountBrief(
        summary=summary,
        drivers=drivers,
        suggested_action=suggested_action,
        source=source,
    )


def _fallback(context: BriefContext) -> AccountBrief:
    ordered = sorted(
        context.triggered_signals.items(), key=lambda item: (-item[1], item[0])
    )

    def _describe(name: str, drift: float) -> str:
        label = name.replace("_", " ").capitalize()
        current = context.signal_current_values.get(name)
        baseline = context.signal_baseline_averages.get(name)
        if current is not None and baseline is not None:
            return f"{label} is now {current:.1f}, usually {baseline:.1f}."
        return f"{label} drift is {drift:.0%}."

    drivers = tuple(
        _describe(name, drift) for name, drift in ordered[:4]
    ) or ("The composite risk crossed the configured alert threshold.",)
    return AccountBrief(
        summary=f"{context.account_name} is at {context.composite_risk:.0%} {context.severity} retention risk after a worsening three-period trend.",
        drivers=drivers,
        suggested_action="Review the account internally and agree on the next human follow-up.",
        source="fallback",
    )


def generate_brief(context: BriefContext, provider: BriefProvider) -> AccountBrief:
    """Generate and validate an evidence-bound account brief."""
    try:
        return _validated(provider.generate(_prompt(context)), source="llm")
    except Exception:  # noqa: BLE001 - this boundary must always return the safe fallback
        return _fallback(context)
