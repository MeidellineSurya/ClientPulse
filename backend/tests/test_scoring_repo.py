# Tests for scoring_repo.py's Supabase reads/writes, using the shared fake
# client — no real database needed.

from app.services.scoring_repo import (
    fetch_all_account_ids,
    fetch_signal_history,
    insert_alert,
    insert_health_score,
    upsert_baselines,
)
from tests.fakes import FakeSupabaseClient


def test_fetch_all_account_ids():
    client = FakeSupabaseClient({"account": [{"id": "a1"}, {"id": "a2"}]})
    assert fetch_all_account_ids(client) == ["a1", "a2"]


def test_fetch_signal_history_returns_oldest_period_first():
    client = FakeSupabaseClient(
        {
            "signal_snapshot": [
                {"account_id": "a1", "period_start": "2026-02-01", "avg_response_time_hours": 5},
                {"account_id": "a1", "period_start": "2026-01-01", "avg_response_time_hours": 3},
                {"account_id": "a2", "period_start": "2026-01-01", "avg_response_time_hours": 9},
            ]
        }
    )
    history = fetch_signal_history(client, "a1")
    assert [row["period_start"] for row in history] == ["2026-01-01", "2026-02-01"]


def test_upsert_baselines_inserts_when_no_existing_row():
    client = FakeSupabaseClient({"baseline": []})
    upsert_baselines(client, "a1", {"avg_response_time_hours": (4.0, 1.0)})
    rows = client._tables["baseline"]
    assert len(rows) == 1
    assert rows[0]["account_id"] == "a1"
    assert rows[0]["signal_name"] == "avg_response_time_hours"
    assert rows[0]["rolling_avg"] == 4.0
    assert rows[0]["rolling_stddev"] == 1.0


def test_upsert_baselines_updates_existing_row_in_place_instead_of_duplicating():
    client = FakeSupabaseClient(
        {
            "baseline": [
                {"account_id": "a1", "signal_name": "avg_response_time_hours", "rolling_avg": 1.0, "rolling_stddev": 0.1}
            ]
        }
    )
    upsert_baselines(client, "a1", {"avg_response_time_hours": (4.0, 2.0)})
    rows = client._tables["baseline"]
    assert len(rows) == 1
    assert rows[0]["rolling_avg"] == 4.0
    assert rows[0]["rolling_stddev"] == 2.0


def test_insert_health_score_appends_a_row():
    client = FakeSupabaseClient({"health_score": []})
    insert_health_score(client, "a1", 72.5, 3.2)
    assert client._tables["health_score"] == [{"account_id": "a1", "composite_score": 72.5, "trend_slope": 3.2}]


def test_insert_alert_defaults_to_open_status():
    client = FakeSupabaseClient({"alert": []})
    insert_alert(client, "a1", ["avg_response_time_hours"], "high")
    assert client._tables["alert"] == [
        {"account_id": "a1", "signals_fired": ["avg_response_time_hours"], "severity": "high", "status": "open"}
    ]
