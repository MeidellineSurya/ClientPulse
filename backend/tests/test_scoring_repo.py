# Tests for scoring_repo.py's Supabase reads/writes, using the shared fake
# client — no real database needed.

from app.services.scoring_repo import (
    fetch_accounts_with_contract_value,
    fetch_contract_value,
    fetch_open_alert,
    fetch_signal_history,
    insert_alert,
    insert_health_score,
    upsert_alert,
    upsert_baselines,
)
from tests.fakes import FakeSupabaseClient


def test_fetch_contract_value_returns_the_accounts_value():
    client = FakeSupabaseClient({"account": [{"id": "a1", "contract_value_monthly": 5000}]})
    assert fetch_contract_value(client, "a1") == 5000.0


def test_fetch_contract_value_defaults_to_zero_when_account_missing():
    client = FakeSupabaseClient({"account": []})
    assert fetch_contract_value(client, "ghost") == 0.0


def test_fetch_accounts_with_contract_value_maps_every_account():
    client = FakeSupabaseClient(
        {
            "account": [
                {"id": "a1", "contract_value_monthly": 5000},
                {"id": "a2", "contract_value_monthly": 12000},
            ]
        }
    )
    assert fetch_accounts_with_contract_value(client) == {"a1": 5000.0, "a2": 12000.0}


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


def test_insert_alert_defaults_to_open_status_with_a_triggered_at_timestamp():
    client = FakeSupabaseClient({"alert": []})
    insert_alert(client, "a1", ["avg_response_time_hours"], "high")
    rows = client._tables["alert"]
    assert len(rows) == 1
    assert rows[0]["account_id"] == "a1"
    assert rows[0]["signals_fired"] == ["avg_response_time_hours"]
    assert rows[0]["severity"] == "high"
    assert rows[0]["status"] == "open"
    assert rows[0]["triggered_at"]  # non-empty, set at insert time


def test_fetch_open_alert_ignores_resolved_alerts():
    client = FakeSupabaseClient(
        {
            "alert": [
                {"id": "old", "account_id": "a1", "severity": "high", "status": "resolved", "triggered_at": "2026-01-01"},
            ]
        }
    )
    assert fetch_open_alert(client, "a1") is None


def test_fetch_open_alert_returns_most_recently_triggered():
    client = FakeSupabaseClient(
        {
            "alert": [
                {"id": "older", "account_id": "a1", "severity": "low", "status": "open", "triggered_at": "2026-01-01T00:00:00"},
                {"id": "newer", "account_id": "a1", "severity": "medium", "status": "acknowledged", "triggered_at": "2026-02-01T00:00:00"},
            ]
        }
    )
    existing = fetch_open_alert(client, "a1")
    assert existing["id"] == "newer"


def test_upsert_alert_inserts_when_no_open_alert_exists():
    client = FakeSupabaseClient({"alert": []})
    upsert_alert(client, "a1", ["invoice_days_late"], "medium")
    assert len(client._tables["alert"]) == 1
    assert client._tables["alert"][0]["severity"] == "medium"


def test_upsert_alert_does_not_duplicate_when_severity_is_unchanged():
    # Simulates calling /score/recompute twice in a row against the same
    # still-worsening (but not further worsening) account — the inbox
    # should not gain a second row for the same issue.
    client = FakeSupabaseClient(
        {
            "alert": [
                {
                    "id": "existing",
                    "account_id": "a1",
                    "severity": "medium",
                    "signals_fired": ["invoice_days_late"],
                    "status": "open",
                    "triggered_at": "2026-01-01T00:00:00",
                }
            ]
        }
    )
    upsert_alert(client, "a1", ["invoice_days_late"], "medium")
    assert len(client._tables["alert"]) == 1
    assert client._tables["alert"][0]["triggered_at"] == "2026-01-01T00:00:00"  # untouched


def test_upsert_alert_escalates_existing_alert_in_place():
    client = FakeSupabaseClient(
        {
            "alert": [
                {
                    "id": "existing",
                    "account_id": "a1",
                    "severity": "low",
                    "signals_fired": ["invoice_days_late"],
                    "status": "open",
                    "triggered_at": "2026-01-01T00:00:00",
                }
            ]
        }
    )
    upsert_alert(client, "a1", ["invoice_days_late", "meetings_cancelled"], "high")
    rows = client._tables["alert"]
    assert len(rows) == 1  # updated in place, not duplicated
    assert rows[0]["severity"] == "high"
    assert rows[0]["signals_fired"] == ["invoice_days_late", "meetings_cancelled"]
    assert rows[0]["triggered_at"] == "2026-01-01T00:00:00"  # preserved: still the original trigger time


def test_upsert_alert_does_not_downgrade_existing_alert():
    client = FakeSupabaseClient(
        {
            "alert": [
                {
                    "id": "existing",
                    "account_id": "a1",
                    "severity": "high",
                    "signals_fired": ["invoice_days_late"],
                    "status": "open",
                    "triggered_at": "2026-01-01T00:00:00",
                }
            ]
        }
    )
    upsert_alert(client, "a1", ["invoice_days_late"], "medium")
    rows = client._tables["alert"]
    assert len(rows) == 1
    assert rows[0]["severity"] == "high"  # not downgraded
