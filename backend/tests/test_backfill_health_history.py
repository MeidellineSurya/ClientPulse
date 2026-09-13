import random

from scripts import generate_seed
from scripts.backfill_health_history import compute_period_scores


def _dataset():
    agency_id = generate_seed.stable_uuid("agency", "StudioCo")
    return generate_seed.build_seed_dataset(
        random.Random(generate_seed.RNG_SEED),
        agency_id,
        anchor_end=generate_seed.date(2026, 9, 13),
    )


def test_period_scores_are_point_in_time_rolling_history_not_only_the_final_window():
    dataset = _dataset()
    account = next(a for a in dataset["accounts"] if a["scenario"] == "worsening")
    history = dataset["snapshots_by_account"][account["id"]]

    periods, scores = compute_period_scores(history)

    assert len(periods) == len(scores) == len(history) - 4
    assert periods[0]["period_end"] == history[4]["period_end"]
    assert periods[-1]["period_end"] == history[-1]["period_end"]
    assert len(set(scores)) >= 4


def test_rolling_history_does_not_let_a_future_period_change_earlier_scores():
    dataset = _dataset()
    account = next(a for a in dataset["accounts"] if a["scenario"] == "response_shock")
    history = dataset["snapshots_by_account"][account["id"]]
    _, original_scores = compute_period_scores(history)

    changed = [dict(row) for row in history]
    changed[-1]["avg_response_time_hours"] = 48.0
    _, changed_scores = compute_period_scores(changed)

    assert changed_scores[:-1] == original_scores[:-1]


def test_representative_demo_scenarios_have_non_flat_rolling_score_curves():
    dataset = _dataset()
    representative = {
        "worsening",
        "response_shock",
        "invoice_deterioration",
        "cancellation_deterioration",
        "recovery",
        "seasonal",
        "noisy_healthy",
    }

    for scenario in representative:
        account = next(a for a in dataset["accounts"] if a["scenario"] == scenario)
        _, scores = compute_period_scores(dataset["snapshots_by_account"][account["id"]])
        assert len(set(scores)) >= 4, scenario
