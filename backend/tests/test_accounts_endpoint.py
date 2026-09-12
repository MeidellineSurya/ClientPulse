# End-to-end tests for GET /accounts and GET /accounts/{id}[/signals],
# using a fake Supabase client (no real database needed) injected via
# FastAPI's dependency override.

from app.dependencies import require_supabase_client
from app.main import app
from fastapi.testclient import TestClient

from tests.fakes import FakeSupabaseClient


def _override_client(fake_client: FakeSupabaseClient) -> TestClient:
    app.dependency_overrides[require_supabase_client] = lambda: fake_client
    return TestClient(app)


def _snapshot(account_id, period_start, period_end="2026-01-07"):
    return {
        "account_id": account_id,
        "period_start": period_start,
        "period_end": period_end,
        "avg_response_time_hours": 4.0,
        "meetings_scheduled": 3,
        "meetings_cancelled": 0,
        "invoice_days_late": 0,
        "email_thread_count": 12,
    }


def test_list_accounts_includes_latest_health_score():
    fake_client = FakeSupabaseClient(
        {
            "account": [
                {
                    "id": "11111111-1111-4111-8111-111111111111",
                    "name": "Acme",
                    "contract_value_monthly": 10000,
                }
            ],
            "health_score": [
                {
                    "account_id": "11111111-1111-4111-8111-111111111111",
                    "composite_score": 20.0,
                    "trend_slope": 1.0,
                    "computed_at": "2026-01-01T00:00:00",
                },
                {
                    "account_id": "11111111-1111-4111-8111-111111111111",
                    "composite_score": 72.5,
                    "trend_slope": 3.2,
                    "computed_at": "2026-02-01T00:00:00",
                },
            ],
        }
    )
    client = _override_client(fake_client)
    try:
        response = client.get("/accounts")
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 200
    body = response.json()
    assert body == [
        {
            "id": "11111111-1111-4111-8111-111111111111",
            "name": "Acme",
            "contract_value_monthly": 10000.0,
            "composite_score": 72.5,
            "trend_slope": 3.2,
            "health_computed_at": "2026-02-01T00:00:00",
        }
    ]


def test_list_accounts_account_never_scored_has_null_score_fields():
    fake_client = FakeSupabaseClient(
        {
            "account": [
                {
                    "id": "11111111-1111-4111-8111-111111111111",
                    "name": "Acme",
                    "contract_value_monthly": 5000,
                }
            ],
            "health_score": [],
        }
    )
    client = _override_client(fake_client)
    try:
        response = client.get("/accounts")
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    body = response.json()
    assert body[0]["composite_score"] is None
    assert body[0]["trend_slope"] is None
    assert body[0]["health_computed_at"] is None


def test_get_account_detail_includes_signal_history_and_alerts():
    fake_client = FakeSupabaseClient(
        {
            "account": [
                {
                    "id": "11111111-1111-4111-8111-111111111111",
                    "name": "Acme",
                    "contract_value_monthly": 10000,
                    "contract_start_date": "2025-01-01",
                    "primary_contact_email": "jordan@acme.com",
                }
            ],
            "health_score": [
                {
                    "account_id": "11111111-1111-4111-8111-111111111111",
                    "composite_score": 90.0,
                    "trend_slope": 5.0,
                    "computed_at": "2026-02-01T00:00:00",
                }
            ],
            "signal_snapshot": [
                _snapshot("11111111-1111-4111-8111-111111111111", "2026-01-01")
            ],
            "alert": [
                {
                    "id": "alert-1",
                    "account_id": "11111111-1111-4111-8111-111111111111",
                    "triggered_at": "2026-02-01T00:00:00",
                    "signals_fired": ["avg_response_time_hours"],
                    "severity": "high",
                    "ai_brief": None,
                    "suggested_action": None,
                    "status": "open",
                }
            ],
        }
    )
    client = _override_client(fake_client)
    try:
        response = client.get("/accounts/11111111-1111-4111-8111-111111111111")
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Acme"
    assert body["composite_score"] == 90.0
    assert len(body["signal_history"]) == 1
    assert body["signal_history"][0]["period_start"] == "2026-01-01"
    assert len(body["alerts"]) == 1
    assert body["alerts"][0]["id"] == "alert-1"


def test_get_account_detail_404_when_account_missing():
    fake_client = FakeSupabaseClient({"account": []})
    client = _override_client(fake_client)
    try:
        response = client.get("/accounts/99999999-9999-4999-8999-999999999999")
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 404


def test_get_account_signals_returns_history():
    fake_client = FakeSupabaseClient(
        {
            "account": [
                {
                    "id": "11111111-1111-4111-8111-111111111111",
                    "name": "Acme",
                    "contract_value_monthly": 10000,
                }
            ],
            "signal_snapshot": [
                _snapshot("11111111-1111-4111-8111-111111111111", "2026-01-01"),
                _snapshot(
                    "11111111-1111-4111-8111-111111111111", "2026-01-08", "2026-01-14"
                ),
            ],
        }
    )
    client = _override_client(fake_client)
    try:
        response = client.get("/accounts/11111111-1111-4111-8111-111111111111/signals")
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["period_start"] == "2026-01-01"


def test_get_account_signals_404_when_account_missing():
    fake_client = FakeSupabaseClient({"account": []})
    client = _override_client(fake_client)
    try:
        response = client.get("/accounts/99999999-9999-4999-8999-999999999999/signals")
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 404


def test_accounts_endpoint_503_without_supabase_configured():
    from app.db import get_supabase_client

    get_supabase_client.cache_clear()
    app.dependency_overrides.pop(require_supabase_client, None)
    client = TestClient(app)

    response = client.get("/accounts")

    assert response.status_code == 503
