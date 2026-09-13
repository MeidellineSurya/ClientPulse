# Tests for baseline_engine.py — pure math, no I/O.

from app.services.baseline_engine import (
    compute_baselines,
    derive_contact_changed,
    mean_stddev,
    split_baseline_and_trend_windows,
)


def test_mean_stddev_of_empty_list():
    avg, stddev = mean_stddev([])
    assert avg == 0.0
    assert stddev is None


def test_mean_stddev_single_value_has_no_established_variance():
    avg, stddev = mean_stddev([5.0])
    assert avg == 5.0
    assert stddev is None


def test_mean_stddev_matches_known_sample_stddev():
    avg, stddev = mean_stddev([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
    assert round(avg, 4) == 5.0
    assert round(stddev, 4) == 2.1381


def test_split_windows_holds_out_last_three_periods():
    history = [{"period_start": f"2026-0{i}-01"} for i in range(1, 9)]  # 8 periods
    baseline_window, trend_window = split_baseline_and_trend_windows(history)
    assert baseline_window == history[:5]
    assert trend_window == history[-3:]


def test_split_windows_falls_back_to_all_history_when_too_short():
    history = [{"period_start": "2026-01-01"}, {"period_start": "2026-01-08"}]
    baseline_window, trend_window = split_baseline_and_trend_windows(history)
    assert baseline_window == history
    assert trend_window == history


def test_split_windows_falls_back_when_baseline_would_be_a_single_point():
    # Exactly TREND_WINDOW+1 (4) periods would otherwise leave a 1-point
    # baseline_window, which can never establish real variance (mean_stddev
    # always returns stddev=None for n<2) — falls back to using all 4 for
    # both windows instead, same as the too-short case above.
    history = [{"period_start": f"2026-01-{i:02d}"} for i in range(1, 5)]
    baseline_window, trend_window = split_baseline_and_trend_windows(history)
    assert baseline_window == history
    assert trend_window == history


def test_split_windows_uses_a_real_split_once_baseline_has_at_least_two_points():
    # 5 periods: baseline_window gets 2 points (enough for a real stddev),
    # trend_window gets the last 3.
    history = [{"period_start": f"2026-01-{i:02d}"} for i in range(1, 6)]
    baseline_window, trend_window = split_baseline_and_trend_windows(history)
    assert baseline_window == history[:2]
    assert trend_window == history[-3:]


def test_compute_baselines_per_signal():
    window = [
        {"avg_response_time_hours": 2.0, "meetings_cancelled": 0, "invoice_days_late": 0, "meetings_scheduled": 5},
        {"avg_response_time_hours": 4.0, "meetings_cancelled": 0, "invoice_days_late": 0, "meetings_scheduled": 5},
    ]
    baselines = compute_baselines(window)
    avg, stddev = baselines["avg_response_time_hours"]
    assert avg == 3.0
    assert round(stddev, 4) == round(2.0**0.5, 4)


def test_compute_baselines_ignores_missing_values():
    window = [
        {"avg_response_time_hours": 4.0, "meetings_cancelled": None, "invoice_days_late": 0, "meetings_scheduled": 5},
    ]
    baselines = compute_baselines(window)
    avg, stddev = baselines["meetings_cancelled"]
    assert avg == 0.0
    assert stddev is None


def test_derive_contact_changed_first_period_is_never_a_change():
    history = [{"primary_contact_email": "a@example.com"}]
    assert derive_contact_changed(history)[0]["contact_changed"] == 0


def test_derive_contact_changed_flags_a_transition_between_known_emails():
    history = [
        {"primary_contact_email": "old@example.com"},
        {"primary_contact_email": "old@example.com"},
        {"primary_contact_email": "new@example.com"},
    ]
    flags = [row["contact_changed"] for row in derive_contact_changed(history)]
    assert flags == [0, 0, 1]


def test_derive_contact_changed_treats_unknown_email_as_no_signal():
    # A missing/unknown email (e.g. a period ingested before this field
    # existed) must never itself register as a change, in either direction.
    history = [
        {"primary_contact_email": None},
        {"primary_contact_email": "a@example.com"},
        {"primary_contact_email": None},
    ]
    flags = [row["contact_changed"] for row in derive_contact_changed(history)]
    assert flags == [0, 0, 0]


def test_derive_contact_changed_does_not_mutate_input_rows():
    history = [{"primary_contact_email": "a@example.com"}]
    derive_contact_changed(history)
    assert "contact_changed" not in history[0]
