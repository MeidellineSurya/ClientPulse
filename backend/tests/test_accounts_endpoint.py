# End-to-end tests for GET /accounts and GET /accounts/{id}[/signals],
# using a fake Supabase client (no real database needed) injected via
# FastAPI's dependency override.

from app.auth import require_auth_context
from app.dependencies import require_supabase_client
from app.main import app
from fastapi.testclient import TestClient

from tests.fakes import FakeSupabaseClient, authenticated_context


def _override_client(fake_client: FakeSupabaseClient) -> TestClient:
    app.dependency_overrides[require_supabase_client] = lambda: fake_client
    app.dependency_overrides[require_auth_context] = lambda: authenticated_context(
        fake_client
    )
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


def test_batch_history_endpoints_return_all_account_series_in_two_requests():
    first = "11111111-1111-4111-8111-111111111111"
    second = "22222222-2222-4222-8222-222222222222"
    fake_client = FakeSupabaseClient(
        {
            "account": [
                {"id": first, "name": "Acme", "contract_value_monthly": 10000},
                {"id": second, "name": "Beta", "contract_value_monthly": 8000},
            ],
            "signal_snapshot": [
                _snapshot(first, "2026-01-01"),
                _snapshot(second, "2026-01-08", "2026-01-14"),
            ],
            "health_score": [
                {"account_id": first, "composite_score": 20, "trend_slope": 1, "computed_at": "2026-01-07T00:00:00"},
                {"account_id": second, "composite_score": 40, "trend_slope": 2, "computed_at": "2026-01-14T00:00:00"},
            ],
        }
    )
    client = _override_client(fake_client)
    try:
        signal_response = client.get("/accounts/signal-histories")
        health_response = client.get("/accounts/health-histories")
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)
        app.dependency_overrides.pop(require_auth_context, None)

    assert signal_response.status_code == 200
    assert health_response.status_code == 200
    assert set(signal_response.json()) == {first, second}
    assert signal_response.json()[second][0]["period_start"] == "2026-01-08"
    assert set(health_response.json()) == {first, second}
    assert health_response.json()[first][0]["composite_score"] == 20


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


def test_get_account_detail_flags_a_contact_change_in_the_history():
    account_id = "11111111-1111-4111-8111-111111111111"
    fake_client = FakeSupabaseClient(
        {
            "account": [
                {
                    "id": account_id,
                    "name": "Acme",
                    "contract_value_monthly": 10000,
                    "contract_start_date": "2025-01-01",
                    "primary_contact_email": "new@acme.com",
                }
            ],
            "signal_snapshot": [
                {**_snapshot(account_id, "2026-01-01"), "primary_contact_email": "old@acme.com"},
                {
                    **_snapshot(account_id, "2026-01-08", "2026-01-14"),
                    "primary_contact_email": "new@acme.com",
                },
            ],
        }
    )
    client = _override_client(fake_client)
    try:
        response = client.get(f"/accounts/{account_id}")
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    body = response.json()
    assert body["contact_changed_at"] == "2026-01-14"
    assert body["previous_contact_email"] == "old@acme.com"


def test_get_account_detail_returns_every_contact_change_event():
    account_id = "11111111-1111-4111-8111-111111111111"
    fake_client = FakeSupabaseClient(
        {
            "account": [
                {
                    "id": account_id,
                    "name": "Acme",
                    "contract_value_monthly": 10000,
                    "contract_start_date": "2025-01-01",
                    "primary_contact_email": "third@acme.com",
                }
            ],
            "signal_snapshot": [
                {**_snapshot(account_id, "2026-01-01"), "primary_contact_email": "first@acme.com"},
                {
                    **_snapshot(account_id, "2026-01-08", "2026-01-14"),
                    "primary_contact_email": "second@acme.com",
                },
                {
                    **_snapshot(account_id, "2026-01-15", "2026-01-21"),
                    "primary_contact_email": "second@acme.com",
                },
                {
                    **_snapshot(account_id, "2026-01-22", "2026-01-28"),
                    "primary_contact_email": "third@acme.com",
                },
            ],
        }
    )
    client = _override_client(fake_client)
    try:
        response = client.get(f"/accounts/{account_id}")
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 200
    assert response.json()["contact_events"] == [
        {
            "period_end": "2026-01-14",
            "previous_contact_email": "first@acme.com",
            "current_contact_email": "second@acme.com",
        },
        {
            "period_end": "2026-01-28",
            "previous_contact_email": "second@acme.com",
            "current_contact_email": "third@acme.com",
        },
    ]


def test_get_account_detail_no_contact_changed_at_when_contact_is_stable():
    account_id = "11111111-1111-4111-8111-111111111111"
    fake_client = FakeSupabaseClient(
        {
            "account": [
                {
                    "id": account_id,
                    "name": "Acme",
                    "contract_value_monthly": 10000,
                    "contract_start_date": "2025-01-01",
                    "primary_contact_email": "same@acme.com",
                }
            ],
            "signal_snapshot": [
                {**_snapshot(account_id, "2026-01-01"), "primary_contact_email": "same@acme.com"},
                {
                    **_snapshot(account_id, "2026-01-08", "2026-01-14"),
                    "primary_contact_email": "same@acme.com",
                },
            ],
        }
    )
    client = _override_client(fake_client)
    try:
        response = client.get(f"/accounts/{account_id}")
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    body = response.json()
    assert body["contact_changed_at"] is None
    assert body["previous_contact_email"] is None


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


def test_get_account_health_history_returns_history():
    account_id = "11111111-1111-4111-8111-111111111111"
    fake_client = FakeSupabaseClient(
        {
            "account": [
                {"id": account_id, "name": "Acme", "contract_value_monthly": 10000}
            ],
            "health_score": [
                {
                    "account_id": account_id,
                    "composite_score": 20.0,
                    "trend_slope": 1.0,
                    "computed_at": "2026-01-01T00:00:00",
                },
                {
                    "account_id": account_id,
                    "composite_score": 60.0,
                    "trend_slope": 5.0,
                    "computed_at": "2026-02-01T00:00:00",
                },
            ],
        }
    )
    client = _override_client(fake_client)
    try:
        response = client.get(f"/accounts/{account_id}/health-history")
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 200
    body = response.json()
    assert [row["composite_score"] for row in body] == [20.0, 60.0]


def test_get_account_health_history_404_when_account_missing():
    fake_client = FakeSupabaseClient({"account": []})
    client = _override_client(fake_client)
    try:
        response = client.get(
            "/accounts/99999999-9999-4999-8999-999999999999/health-history"
        )
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 404


def test_get_account_signals_404_when_account_missing():
    fake_client = FakeSupabaseClient({"account": []})
    client = _override_client(fake_client)
    try:
        response = client.get("/accounts/99999999-9999-4999-8999-999999999999/signals")
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 404


def test_accounts_endpoint_503_without_supabase_configured(monkeypatch):
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

    response = client.get("/accounts")

    assert response.status_code == 503
