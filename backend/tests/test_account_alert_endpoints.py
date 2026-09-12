from app.dependencies import require_supabase_client
from app.main import app
from app.routers import alerts
from fastapi.testclient import TestClient

from tests.fakes import FakeSupabaseClient

ACCOUNT_ID = "11111111-1111-4111-8111-111111111111"
ALERT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def _alert(status: str = "open") -> dict:
    return {
        "id": ALERT_ID,
        "account_id": ACCOUNT_ID,
        "triggered_at": "2026-09-10T00:00:00+00:00",
        "signals_fired": ["meetings_cancelled"],
        "severity": "high",
        "ai_brief": None,
        "suggested_action": None,
        "status": status,
    }


def _client(fake: FakeSupabaseClient) -> TestClient:
    app.dependency_overrides[require_supabase_client] = lambda: fake
    return TestClient(app, raise_server_exceptions=False)


def test_malformed_account_and_alert_ids_are_rejected_before_database_access():
    fake = FakeSupabaseClient({"account": [], "alert": []})
    client = _client(fake)
    try:
        account_response = client.get("/accounts/not-a-uuid")
        signal_response = client.get("/accounts/not-a-uuid/signals")
        alert_response = client.post(
            "/alerts/not-a-uuid/status", json={"status": "acknowledged"}
        )
    finally:
        app.dependency_overrides.clear()

    assert account_response.status_code == 422
    assert signal_response.status_code == 422
    assert alert_response.status_code == 422


def test_open_alert_status_update_is_idempotent():
    alert = _alert(status="open")
    fake = FakeSupabaseClient({"alert": [alert]})
    client = _client(fake)
    try:
        response = client.post(f"/alerts/{ALERT_ID}/status", json={"status": "open"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "open"


def test_acknowledged_alert_cannot_return_to_open():
    alert = _alert(status="acknowledged")
    fake = FakeSupabaseClient({"alert": [alert]})
    client = _client(fake)
    try:
        response = client.post(f"/alerts/{ALERT_ID}/status", json={"status": "open"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["detail"] == "alert status cannot move backwards"
    assert alert["status"] == "acknowledged"


def test_resolved_alert_cannot_be_reopened():
    alert = _alert(status="resolved")
    fake = FakeSupabaseClient({"alert": [alert]})
    client = _client(fake)
    try:
        response = client.post(
            f"/alerts/{ALERT_ID}/status", json={"status": "acknowledged"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["detail"] == "resolved alerts cannot be reopened"
    assert alert["status"] == "resolved"


def test_concurrent_alert_status_change_returns_conflict(monkeypatch):
    alert = _alert(status="open")
    fake = FakeSupabaseClient({"alert": [alert]})
    client = _client(fake)
    monkeypatch.setattr(
        alerts, "update_alert_status_if_current", lambda *_args, **_kwargs: None
    )
    try:
        response = client.post(
            f"/alerts/{ALERT_ID}/status", json={"status": "acknowledged"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["detail"] == "alert status changed concurrently"


def test_patch_alert_status_uses_same_safe_transition_contract():
    alert = _alert(status="open")
    fake = FakeSupabaseClient({"alert": [alert]})
    client = _client(fake)
    try:
        response = client.patch(f"/alerts/{ALERT_ID}", json={"status": "acknowledged"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "acknowledged"
    assert alert["status"] == "acknowledged"
