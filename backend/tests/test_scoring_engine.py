# Tests for scoring_engine.py — pure math, no I/O. This is the piece
# HANDOFF.md calls "the entire defensibility argument for the pitch", so it
# gets the most thorough coverage in this branch.

from app.services.scoring_engine import (
    RISK_ALERT_THRESHOLD,
    compute_composite_risk,
    compute_drift,
    compute_revenue_at_risk,
    compute_trend_slope,
    decide_severity,
    score_account_history,
    should_fire_alert,
    significant_signals,
)


def test_compute_drift_is_zero_when_current_is_better_than_baseline():
    # Lower response time than baseline is an improvement, not risk.
    assert compute_drift(2.0, 4.0, 1.0, higher_is_worse=True) == 0.0


def test_compute_drift_scales_with_z_score_up_to_cap():
    # 1 stddev above baseline -> drift = 1/3 (Z_CAP=3.0).
    drift = compute_drift(5.0, 4.0, 1.0, higher_is_worse=True)
    assert round(drift, 4) == round(1 / 3, 4)


def test_compute_drift_clips_at_one_beyond_z_cap():
    drift = compute_drift(10.0, 4.0, 1.0, higher_is_worse=True)  # z=6, past the cap
    assert drift == 1.0


def test_compute_drift_lower_is_worse_flips_direction():
    # meetings_scheduled: a *drop* below baseline is the risk direction.
    drift = compute_drift(2.0, 5.0, 1.0, higher_is_worse=False)
    assert drift == 1.0  # z=3, exactly at the cap
    # A rise in meetings, by contrast, is not risk.
    assert compute_drift(8.0, 5.0, 1.0, higher_is_worse=False) == 0.0


def test_compute_drift_with_no_established_variance_treats_any_deviation_as_maximal():
    assert compute_drift(5.0, 4.0, None, higher_is_worse=True) == 1.0
    assert compute_drift(5.0, 4.0, 0.0, higher_is_worse=True) == 1.0
    assert compute_drift(4.0, 4.0, 0.0, higher_is_worse=True) == 0.0  # no deviation at all


def test_compute_composite_risk_hits_full_scale_when_every_signal_is_maximally_drifted():
    baselines = {
        "avg_response_time_hours": (2.0, 0.01),
        "meetings_cancelled": (0.0, 0.01),
        "invoice_days_late": (0.0, 0.01),
        "meetings_scheduled": (5.0, 0.01),
    }
    current = {
        "avg_response_time_hours": 100.0,
        "meetings_cancelled": 100.0,
        "invoice_days_late": 100.0,
        "meetings_scheduled": 0.0,
    }
    score, drifts = compute_composite_risk(current, baselines)
    assert score == 100.0
    assert all(d == 1.0 for d in drifts.values())


def test_compute_composite_risk_is_zero_at_baseline():
    baselines = {
        "avg_response_time_hours": (4.0, 1.0),
        "meetings_cancelled": (0.0, 1.0),
        "invoice_days_late": (0.0, 1.0),
        "meetings_scheduled": (4.0, 1.0),
    }
    current = {signal: avg for signal, (avg, _stddev) in baselines.items()}
    score, drifts = compute_composite_risk(current, baselines)
    assert score == 0.0
    assert all(d == 0.0 for d in drifts.values())


def test_compute_revenue_at_risk_at_full_score_is_the_full_annual_value():
    assert compute_revenue_at_risk(contract_value_monthly=10000, composite_score=100) == 120000.0


def test_compute_revenue_at_risk_at_zero_score_is_zero():
    assert compute_revenue_at_risk(contract_value_monthly=10000, composite_score=0) == 0.0


def test_compute_revenue_at_risk_scales_proportionally():
    assert compute_revenue_at_risk(contract_value_monthly=10000, composite_score=50) == 60000.0


def test_compute_revenue_at_risk_with_zero_contract_value():
    assert compute_revenue_at_risk(contract_value_monthly=0, composite_score=100) == 0.0


def test_compute_trend_slope_positive_for_worsening_scores():
    assert compute_trend_slope([10, 20, 30]) > 0


def test_compute_trend_slope_negative_for_improving_scores():
    assert compute_trend_slope([30, 20, 10]) < 0


def test_compute_trend_slope_zero_for_flat_scores():
    assert compute_trend_slope([20, 20, 20]) == 0.0


def test_compute_trend_slope_needs_at_least_two_points():
    assert compute_trend_slope([50]) == 0.0
    assert compute_trend_slope([]) == 0.0


def test_should_fire_alert_requires_both_threshold_and_worsening_trend():
    assert should_fire_alert(RISK_ALERT_THRESHOLD, 1.0) is True
    assert should_fire_alert(RISK_ALERT_THRESHOLD - 0.01, 1.0) is False  # below threshold
    assert should_fire_alert(RISK_ALERT_THRESHOLD, 0.0) is False  # flat, not worsening
    assert should_fire_alert(RISK_ALERT_THRESHOLD, -1.0) is False  # improving despite high score


def test_decide_severity_buckets():
    assert decide_severity(50) == "low"
    assert decide_severity(70) == "medium"
    assert decide_severity(85) == "high"
    assert decide_severity(95) == "critical"


def test_significant_signals_filters_out_noise():
    drifts = {
        "avg_response_time_hours": 0.9,
        "meetings_cancelled": 0.1,
        "invoice_days_late": 0.0,
        "meetings_scheduled": 0.4,
    }
    assert significant_signals(drifts) == ["avg_response_time_hours", "meetings_scheduled"]


def _stable_history(weeks: int = 8) -> list[dict]:
    # A healthy account: every period identical to its own baseline.
    return [
        {
            "period_start": f"2026-01-{i + 1:02d}",
            "avg_response_time_hours": 4.0,
            "meetings_cancelled": 0,
            "invoice_days_late": 0,
            "meetings_scheduled": 4,
        }
        for i in range(weeks)
    ]


def _worsening_history(weeks: int = 8) -> list[dict]:
    # Mirrors the shape of backend/scripts/generate_seed.py's worsening
    # accounts: every signal ramps steadily worse across the window.
    history = []
    for i in range(weeks):
        progress = i / (weeks - 1)
        history.append(
            {
                "period_start": f"2026-01-{i + 1:02d}",
                "avg_response_time_hours": 4.0 + progress * 20,
                "meetings_cancelled": round(progress * 4),
                "invoice_days_late": round(progress * 25),
                "meetings_scheduled": max(0, round(5 - progress * 5)),
            }
        )
    return history


def test_score_account_history_stable_account_does_not_fire():
    result = score_account_history(_stable_history())
    assert result.alert_fired is False
    assert result.composite_score == 0.0
    assert result.severity is None
    assert result.signals_fired == []


def test_score_account_history_worsening_account_fires_alert():
    result = score_account_history(_worsening_history())
    assert result.composite_score >= RISK_ALERT_THRESHOLD
    assert result.trend_slope > 0
    assert result.alert_fired is True
    assert result.severity is not None
    assert "avg_response_time_hours" in result.signals_fired


def test_score_account_history_handles_short_history_without_crashing():
    # Only 2 periods — falls back to using all of them for both windows;
    # a brand-new account should score as "no drift from itself" rather
    # than error out.
    result = score_account_history(_stable_history(weeks=2))
    assert result.composite_score == 0.0
    assert result.alert_fired is False
