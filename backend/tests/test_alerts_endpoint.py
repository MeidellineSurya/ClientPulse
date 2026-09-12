# End-to-end tests for GET /alerts and POST /alerts/{id}/status, using a
# fake Supabase client (no real database needed) injected via FastAPI's
# dependency override.

from fastapi.testclient import TestClient

from app.dependencies import require_supabase_client
from app.main import app
from tests.fakes import FakeSupabaseClient


def _override_client(fake_client: FakeSupabaseClient) -> TestClient:
    app.dependency_overrides[require_supabase_client] = lambda: fake_client
    return TestClient(app)


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


def test_list_alerts_sorted_newest_first_with_account_name():
    fake_client = FakeSupabaseClient(
        {
            "alert": [
                _alert("older", "acc-1", "2026-01-01T00:00:00"),
                _alert("newer", "acc-2", "2026-02-01T00:00:00"),
            ],
            "account": [{"id": "acc-1", "name": "Acme"}, {"id": "acc-2", "name": "Beta"}],
        }
    )
    client = _override_client(fake_client)
    try:
        response = client.get("/alerts")
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 200
    body = response.json()
    assert [a["id"] for a in body] == ["newer", "older"]
    assert body[0]["account_name"] == "Beta"


def test_set_alert_status_updates_and_returns_the_alert():
    fake_client = FakeSupabaseClient({"alert": [_alert("alert-1", "acc-1", "2026-01-01T00:00:00", status="open")]})
    client = _override_client(fake_client)
    try:
        response = client.post("/alerts/alert-1/status", json={"status": "acknowledged"})
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "acknowledged"
    assert fake_client._tables["alert"][0]["status"] == "acknowledged"


def test_set_alert_status_404_when_alert_missing():
    fake_client = FakeSupabaseClient({"alert": []})
    client = _override_client(fake_client)
    try:
        response = client.post("/alerts/ghost/status", json={"status": "resolved"})
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 404


def test_set_alert_status_rejects_invalid_status_value():
    fake_client = FakeSupabaseClient({"alert": [_alert("alert-1", "acc-1", "2026-01-01T00:00:00")]})
    client = _override_client(fake_client)
    try:
        response = client.post("/alerts/alert-1/status", json={"status": "snoozed"})
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 422


def test_alerts_endpoint_503_without_supabase_configured(monkeypatch):
    from app.config import settings
    from app.db import get_supabase_client

    # A developer's real backend/.env (needed for live testing) would
    # otherwise leak into this test via the module-level settings
    # singleton, masking the "not configured" case this test exists to check.
    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "supabase_service_role_key", "")
    get_supabase_client.cache_clear()
    app.dependency_overrides.pop(require_supabase_client, None)
    client = TestClient(app)

    response = client.get("/alerts")

    assert response.status_code == 503
