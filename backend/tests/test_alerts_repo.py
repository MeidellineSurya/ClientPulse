# Tests for alerts_repo.py's Supabase reads/writes, using the shared fake
# client — no real database needed.

from app.services.alerts_repo import (
    fetch_alert,
    fetch_alerts_for_account,
    fetch_all_alerts,
    update_alert_status_if_current,
)
from tests.fakes import TEST_AGENCY_ID, FakeSupabaseClient


def _alert(alert_id, account_id, triggered_at, **overrides):
    row = {
        "id": alert_id,
        "account_id": account_id,
        "triggered_at": triggered_at,
        "signals_fired": ["avg_response_time_hours"],
        "severity": "high",
        "ai_brief": None,
        "suggested_action": None,
        "status": "open",
    }
    row.update(overrides)
    return row


def test_fetch_all_alerts_sorted_newest_first_with_account_name_joined():
    client = FakeSupabaseClient(
        {
            "alert": [
                _alert("older", "a1", "2026-01-01T00:00:00"),
                _alert("newer", "a2", "2026-02-01T00:00:00"),
            ],
            "account": [{"id": "a1", "name": "Acme"}, {"id": "a2", "name": "Beta"}],
        }
    )
    alerts = fetch_all_alerts(client, TEST_AGENCY_ID)
    assert [a["id"] for a in alerts] == ["newer", "older"]
    assert alerts[0]["account_name"] == "Beta"
    assert alerts[1]["account_name"] == "Acme"


def test_fetch_alerts_for_account_sorted_newest_first():
    client = FakeSupabaseClient(
        {
            "alert": [
                _alert("older", "a1", "2026-01-01T00:00:00"),
                _alert("newer", "a1", "2026-02-01T00:00:00"),
                _alert("other-account", "a2", "2026-03-01T00:00:00"),
            ]
        }
    )
    alerts = fetch_alerts_for_account(client, "a1")
    assert [a["id"] for a in alerts] == ["newer", "older"]


def test_fetch_alert_returns_the_matching_row():
    client = FakeSupabaseClient(
        {"alert": [_alert("a1", "acc-1", "2026-01-01T00:00:00")]}
    )
    assert fetch_alert(client, "a1", TEST_AGENCY_ID)["account_id"] == "acc-1"


def test_fetch_alert_returns_none_when_missing():
    client = FakeSupabaseClient({"alert": []})
    assert fetch_alert(client, "ghost", TEST_AGENCY_ID) is None


def test_conditional_alert_status_update_rejects_stale_state():
    client = FakeSupabaseClient(
        {"alert": [_alert("a1", "acc-1", "2026-01-01T00:00:00", status="open")]}
    )

    updated = update_alert_status_if_current(
        client,
        "a1",
        account_id="acc-1",
        current_status="open",
        new_status="acknowledged",
    )
    stale_update = update_alert_status_if_current(
        client,
        "a1",
        account_id="acc-1",
        current_status="open",
        new_status="resolved",
    )

    assert updated is not None
    assert updated["status"] == "acknowledged"
    assert stale_update is None
