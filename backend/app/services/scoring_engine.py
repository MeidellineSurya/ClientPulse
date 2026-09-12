"""The deterministic core: per-signal drift vs. an account's own baseline,
combined into a composite churn-risk score, with alerts gated on a
sustained worsening trend rather than a single bad week.

Rule (HANDOFF.md §5): the LLM never generates this score. It only writes a
plain-language brief *after* this module has already decided the number.

    drift_score(signal) = (current_value - baseline_avg) / baseline_stddev
                            [normalized/clipped to 0-1]

    composite_risk =
        0.35 x drift(response_time)          # top churn cause: poor communication
      + 0.30 x drift(meeting_cancellations)
      + 0.20 x drift(payment_lag)
      + 0.15 x drift(meeting_frequency_decline)

All I/O (Supabase reads/writes) lives in scoring_repo.py — everything here
is pure and unit-testable without a database.
"""

from dataclasses import dataclass, field

from app.services.baseline_engine import (
    TRACKED_SIGNALS,
    compute_baselines,
    split_baseline_and_trend_windows,
)

# Weights sum to 1.0, taken directly from HANDOFF.md's stated formula.
SIGNAL_WEIGHTS = {
    "avg_response_time_hours": 0.35,
    "meetings_cancelled": 0.30,
    "invoice_days_late": 0.20,
    "meetings_scheduled": 0.15,  # meeting *frequency decline* — see HIGHER_IS_WORSE
}

# Whether a larger raw value is the "worse" direction for that signal.
# meetings_scheduled is the odd one out: a drop in meeting frequency is the
# risk signal, not a rise, so its drift is measured baseline-minus-current.
HIGHER_IS_WORSE = {
    "avg_response_time_hours": True,
    "meetings_cancelled": True,
    "invoice_days_late": True,
    "meetings_scheduled": False,
}

# A z-score at or beyond this is treated as "fully" at-risk for that signal
# (normalized drift clips to 1.0). 3 standard deviations is a conventional
# threshold for a statistically significant outlier.
Z_CAP = 3.0

# composite_score (0-100) at/above which an account is considered at-risk.
# Placeholder tuned so the seed data's worsening accounts cross it by their
# final weeks without healthy accounts tripping it — revisit with real data.
RISK_ALERT_THRESHOLD = 60.0

# A signal's normalized drift must reach this to be called out in
# alert.signals_fired as a meaningful contributor, not just noise.
SIGNAL_CONTRIBUTION_THRESHOLD = 0.3


@dataclass
class AccountScoringResult:
    composite_score: float
    trend_slope: float
    baselines: dict[str, tuple[float, float | None]]
    drifts: dict[str, float]
    alert_fired: bool
    severity: str | None
    signals_fired: list[str] = field(default_factory=list)
    signal_contributions: dict[str, float] = field(default_factory=dict)


def compute_drift(
    current_value: float, baseline_avg: float, baseline_stddev: float | None, higher_is_worse: bool
) -> float:
    """Normalized 0-1 drift: 0 = at or better than baseline, 1 = at/beyond
    Z_CAP standard deviations into the "worse" direction for this signal."""
    raw_delta = (current_value - baseline_avg) if higher_is_worse else (baseline_avg - current_value)
    if raw_delta <= 0:
        return 0.0
    if not baseline_stddev:
        # No established variance (0, or not enough history) — any
        # deviation at all from a flat baseline is itself anomalous, so
        # treat it as maximal rather than dividing by zero.
        return 1.0
    return max(0.0, min(1.0, (raw_delta / baseline_stddev) / Z_CAP))


def compute_composite_risk(
    current_signals: dict[str, float], baselines: dict[str, tuple[float, float | None]]
) -> tuple[float, dict[str, float]]:
    """Returns (composite_score 0-100, per-signal normalized drift 0-1)."""
    drifts = {}
    for signal in SIGNAL_WEIGHTS:
        avg, stddev = baselines.get(signal, (0.0, None))
        current = current_signals.get(signal, avg)
        drifts[signal] = compute_drift(current, avg, stddev, HIGHER_IS_WORSE[signal])
    composite = sum(SIGNAL_WEIGHTS[signal] * drifts[signal] for signal in SIGNAL_WEIGHTS)
    return round(composite * 100, 2), drifts


def compute_signal_contributions(drifts: dict[str, float]) -> dict[str, float]:
    """What percentage (0-100) of the composite score each signal is
    responsible for, e.g. {"avg_response_time_hours": 68.2, ...} — turns
    "the score is 97" into "97, and 68% of that is response-time drift",
    an inspectable breakdown rather than an opaque number (HANDOFF.md §5's
    "not the AI figures it out" standard applies to explaining the score,
    not just computing it).

    Percentages sum to ~100 (rounding aside) whenever the composite score
    is nonzero; all zero when nothing has drifted at all.
    """
    weighted = {signal: SIGNAL_WEIGHTS[signal] * drifts.get(signal, 0.0) for signal in SIGNAL_WEIGHTS}
    total = sum(weighted.values())
    if total <= 0:
        return {signal: 0.0 for signal in SIGNAL_WEIGHTS}
    return {signal: round(contribution / total * 100, 1) for signal, contribution in weighted.items()}


def compute_revenue_at_risk(contract_value_monthly: float, composite_score: float) -> float:
    """Annualized contract value, weighted by composite_score, as a dollar
    figure — the number the pitch's money case (HANDOFF.md §1/§9) is built
    on, not just an abstract 0-100 score.

    A deliberate hackathon-scope simplification: composite_score is a risk
    *severity* score, not a calibrated churn probability, so this isn't a
    true expected-value calculation. It's "how much of this account's
    annual value currently sits in the danger zone" — proportional
    exposure, which is what the portfolio view's at-risk-revenue total needs.
    """
    return round(contract_value_monthly * 12 * (composite_score / 100), 2)


def compute_trend_slope(scores: list[float]) -> float:
    """Least-squares slope of composite_score against period index (oldest
    first). Positive means risk is increasing period over period."""
    n = len(scores)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2
    y_mean = sum(scores) / n
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in enumerate(scores))
    denominator = sum((x - x_mean) ** 2 for x in range(n))
    return numerator / denominator if denominator else 0.0


def is_worsening_trend(trend_slope: float) -> bool:
    return trend_slope > 0


def should_fire_alert(composite_score: float, trend_slope: float) -> bool:
    """An alert only fires when the composite score is above threshold AND
    the trend is worsening — a single bad week must not trigger a flag."""
    return composite_score >= RISK_ALERT_THRESHOLD and is_worsening_trend(trend_slope)


# Ascending order, used to detect whether a new evaluation is an
# *escalation* of an account's existing open alert (see scoring_repo.upsert_alert).
SEVERITY_ORDER = ["low", "medium", "high", "critical"]


def decide_severity(composite_score: float) -> str:
    if composite_score >= 95:
        return "critical"
    if composite_score >= 85:
        return "high"
    if composite_score >= 70:
        return "medium"
    return "low"


def significant_signals(drifts: dict[str, float]) -> list[str]:
    """Which signals meaningfully drove the score, for alert.signals_fired."""
    return [signal for signal, drift in drifts.items() if drift >= SIGNAL_CONTRIBUTION_THRESHOLD]


def score_account_history(history: list[dict]) -> AccountScoringResult:
    """Runs the full pipeline for one account's period-ordered (oldest
    first) signal_snapshot history: baseline -> per-period composite_risk
    over the trend window -> trend slope -> alert decision.

    The baseline is computed once (from every period outside the trend
    window) and applied to each period inside it, rather than walking a
    baseline forward period by period — a deliberate hackathon-scope
    simplification, not a per-period lookback.
    """
    baseline_window, trend_window = split_baseline_and_trend_windows(history)
    baselines = compute_baselines(baseline_window)

    period_scores: list[float] = []
    latest_drifts: dict[str, float] = {}
    for row in trend_window:
        current_signals = {signal: float(row[signal]) for signal in TRACKED_SIGNALS if row.get(signal) is not None}
        score, drifts = compute_composite_risk(current_signals, baselines)
        period_scores.append(score)
        latest_drifts = drifts

    composite_score = period_scores[-1] if period_scores else 0.0
    trend_slope = round(compute_trend_slope(period_scores), 4)
    alert_fired = should_fire_alert(composite_score, trend_slope)

    return AccountScoringResult(
        composite_score=composite_score,
        trend_slope=trend_slope,
        baselines=baselines,
        drifts=latest_drifts,
        alert_fired=alert_fired,
        severity=decide_severity(composite_score) if alert_fired else None,
        signals_fired=significant_signals(latest_drifts) if alert_fired else [],
        signal_contributions=compute_signal_contributions(latest_drifts),
    )
