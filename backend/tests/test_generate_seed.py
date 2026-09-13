"""Regression tests for the deterministic ClientPulse demonstration dataset."""

import random

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
        "cancellation_deterioration": 3,
        "invoice_deterioration": 4,
        "new_account": 1,
        "noisy_healthy": 3,
        "recovery": 4,
        "response_shock": 4,
        "seasonal": 3,
        "stable": 18,
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


def test_seed_dataset_is_deterministic_for_a_fixed_anchor_date():
    agency_id = generate_seed.stable_uuid("agency", "StudioCo")
    first = generate_seed.build_seed_dataset(random.Random(generate_seed.RNG_SEED), agency_id, anchor_end=generate_seed.date(2026, 9, 6))
    second = generate_seed.build_seed_dataset(random.Random(generate_seed.RNG_SEED), agency_id, anchor_end=generate_seed.date(2026, 9, 6))

    assert first == second
