"""Regression tests for the deterministic ClientPulse demonstration dataset."""

import random
from collections import Counter, defaultdict
from itertools import pairwise
from typing import cast

from app.services.baseline_engine import derive_contact_changed
from app.services.scoring_engine import score_account_history
from scripts import generate_seed


def test_seed_dataset_has_long_history_and_diverse_lifecycle_scenarios():
    """The seed must challenge scoring with more than obvious monotonic churn."""
    agency_id = generate_seed.stable_uuid("agency", "StudioCo")
    dataset = generate_seed.build_seed_dataset(
        random.Random(generate_seed.RNG_SEED),
        agency_id,
        anchor_end=generate_seed.date(2026, 9, 6),
    )

    assert len(dataset["accounts"]) == 48
    assert dataset["scenario_counts"] == {
        "acute_churn": 1,
        "cancellation_deterioration": 3,
        "contact_watch": 1,
        "invoice_deterioration": 4,
        "new_account": 1,
        "noisy_healthy": 3,
        "recovery": 4,
        "response_shock": 4,
        "seasonal": 3,
        "stable": 16,
        "worsening": 8,
    }
    assert sum(len(rows) for rows in dataset["snapshots_by_account"].values()) == 1228

    histories = {
        account["scenario"]: dataset["snapshots_by_account"][account["id"]]
        for account in dataset["accounts"]
    }
    assert len(histories["stable"]) == 26
    assert len(histories["new_account"]) == 6
    assert histories["response_shock"][-1]["avg_response_time_hours"] > histories["response_shock"][-2]["avg_response_time_hours"]
    assert histories["recovery"][-1]["avg_response_time_hours"] < histories["recovery"][-6]["avg_response_time_hours"]


def test_seed_dataset_populates_dashboard_risk_and_watch_tiers_with_distinct_scenarios():
    """The portfolio must show meaningful At risk and Watch graph variety."""
    agency_id = generate_seed.stable_uuid("agency", "StudioCo")
    dataset = generate_seed.build_seed_dataset(
        random.Random(generate_seed.RNG_SEED),
        agency_id,
        anchor_end=generate_seed.date(2026, 9, 6),
    )

    tiers = Counter()
    scenario_tiers = {}
    for account in dataset["accounts"]:
        result = score_account_history(dataset["snapshots_by_account"][account["id"]])
        tier = "risk" if result.composite_score >= 60 else "watch" if result.composite_score >= 30 else "healthy"
        tiers[tier] += 1
        scenario_tiers.setdefault(account["scenario"], set()).add(tier)

    assert tiers == {"risk": 9, "watch": 15, "healthy": 24}
    assert scenario_tiers["worsening"] == {"risk"}
    assert scenario_tiers["acute_churn"] == {"risk"}
    assert scenario_tiers["response_shock"] == {"watch"}
    assert scenario_tiers["invoice_deterioration"] == {"watch"}
    assert scenario_tiers["cancellation_deterioration"] == {"watch"}
    assert scenario_tiers["contact_watch"] == {"watch"}


def test_contact_events_do_not_create_synchronized_portfolio_score_spikes():
    from scripts.backfill_health_history import compute_period_scores

    agency_id = generate_seed.stable_uuid("agency", "StudioCo")
    dataset = generate_seed.build_seed_dataset(
        random.Random(generate_seed.RNG_SEED),
        agency_id,
        anchor_end=generate_seed.date(2026, 9, 13),
    )
    scores_by_period = defaultdict(list)
    for account in dataset["accounts"]:
        if account["scenario"] == "new_account":
            continue
        periods, scores = compute_period_scores(dataset["snapshots_by_account"][account["id"]])
        for period, score in zip(periods, scores):
            scores_by_period[period["period_end"]].append(score)

    portfolio_curve = [
        sum(scores) / len(scores)
        for _period, scores in sorted(scores_by_period.items())
    ]
    weekly_changes = [current - previous for previous, current in pairwise(portfolio_curve)]

    assert max(abs(change) for change in weekly_changes) <= 8
    assert sum(change > 0 for change in weekly_changes) >= 5
    assert sum(change < 0 for change in weekly_changes) >= 5


def test_seed_dataset_is_deterministic_for_a_fixed_anchor_date():
    agency_id = generate_seed.stable_uuid("agency", "StudioCo")
    first = generate_seed.build_seed_dataset(random.Random(generate_seed.RNG_SEED), agency_id, anchor_end=generate_seed.date(2026, 9, 6))
    second = generate_seed.build_seed_dataset(random.Random(generate_seed.RNG_SEED), agency_id, anchor_end=generate_seed.date(2026, 9, 6))

    assert first == second


def test_demo_alert_profiles_cover_varied_lifecycle_states_and_severities():
    agency_id = generate_seed.stable_uuid("agency", "StudioCo")
    dataset = generate_seed.build_seed_dataset(
        random.Random(generate_seed.RNG_SEED),
        agency_id,
        anchor_end=generate_seed.date(2026, 9, 13),
    )

    profiles = generate_seed.build_demo_alert_profiles(dataset["accounts"])

    assert len(profiles) == 20
    assert Counter(profile["status"] for profile in profiles.values()) == {
        "open": 6,
        "acknowledged": 6,
        "resolved": 8,
    }
    assert Counter(profile["severity"] for profile in profiles.values()) == {
        "low": 5,
        "medium": 7,
        "high": 5,
        "critical": 3,
    }

    contact_account = next(
        account for account in dataset["accounts"] if account["scenario"] == "contact_watch"
    )
    assert set(profiles[contact_account["id"]]["signals_fired"]) == {
        "contact_changed",
        "avg_response_time_hours",
    }
    contact_history = dataset["snapshots_by_account"][contact_account["id"]]
    assert contact_history[0]["primary_contact_email"] != contact_history[-1]["primary_contact_email"]
    assert contact_history[-1]["avg_response_time_hours"] > contact_history[0]["avg_response_time_hours"]

    scheduling_accounts = [
        account
        for account in dataset["accounts"]
        if account["scenario"] == "cancellation_deterioration"
    ]
    assert all(
        {"meetings_scheduled", "meetings_cancelled"}
        <= set(profiles[account["id"]]["signals_fired"])
        for account in scheduling_accounts
    )
    for account in scheduling_accounts:
        history = dataset["snapshots_by_account"][account["id"]]
        early_scheduled = sum(row["meetings_scheduled"] for row in history[:10]) / 10
        recent_scheduled = sum(row["meetings_scheduled"] for row in history[-3:]) / 3
        early_cancelled = sum(row["meetings_cancelled"] for row in history[:10]) / 10
        recent_cancelled = sum(row["meetings_cancelled"] for row in history[-3:]) / 3
        assert recent_scheduled < early_scheduled
        assert recent_cancelled > early_cancelled


def test_many_accounts_have_substantial_contact_history_while_alerts_remain_evidence_backed():
    agency_id = generate_seed.stable_uuid("agency", "StudioCo")
    dataset = generate_seed.build_seed_dataset(
        random.Random(generate_seed.RNG_SEED),
        agency_id,
        anchor_end=generate_seed.date(2026, 9, 13),
    )
    profiles = generate_seed.build_demo_alert_profiles(dataset["accounts"])
    contact_history_accounts = [
        account for account in dataset["accounts"] if account["_contact_change_indexes"]
    ]
    contact_alert_accounts = [
        account
        for account in dataset["accounts"]
        if "contact_changed"
        in cast(list[str], profiles.get(account["id"], {}).get("signals_fired", []))
    ]

    assert len(contact_history_accounts) == 20
    assert len(contact_alert_accounts) == 4
    assert {account["id"] for account in contact_alert_accounts} <= {
        account["id"] for account in contact_history_accounts
    }
    assert Counter(profiles[account["id"]]["status"] for account in contact_alert_accounts) == {
        "open": 1,
        "acknowledged": 1,
        "resolved": 2,
    }
    event_counts = {}
    for account in contact_history_accounts:
        history = derive_contact_changed(
            dataset["snapshots_by_account"][account["id"]]
        )
        event_counts[account["id"]] = sum(row["contact_changed"] for row in history)

    assert set(event_counts.values()) == {4}
    assert sum(event_counts.values()) == 80


def test_every_established_account_signal_history_has_visible_turning_points():
    agency_id = generate_seed.stable_uuid("agency", "StudioCo")
    dataset = generate_seed.build_seed_dataset(
        random.Random(generate_seed.RNG_SEED),
        agency_id,
        anchor_end=generate_seed.date(2026, 9, 13),
    )
    displayed_signals = (
        "avg_response_time_hours",
        "meetings_scheduled",
        "meetings_cancelled",
        "invoice_days_late",
    )

    for account in dataset["accounts"]:
        history = dataset["snapshots_by_account"][account["id"]]
        minimum_distinct_values = 2 if account["scenario"] == "new_account" else 4
        for signal in displayed_signals:
            values = [row[signal] for row in history]
            directions = [
                1 if current > previous else -1
                for previous, current in pairwise(values)
                if current != previous
            ]
            turns = sum(previous != current for previous, current in pairwise(directions))
            assert len(set(values)) >= minimum_distinct_values, (account["name"], signal)
            assert turns >= 4, (account["name"], signal)
