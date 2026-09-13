"""Authentication and tenant-isolation regressions for the HTTP API."""

from types import SimpleNamespace

from fastapi.testclient import TestClient
from gotrue.errors import AuthApiError, AuthRetryableError

from app.dependencies import require_supabase_client
from app.main import app
from tests.fakes import FakeSupabaseClient


class _FakeAuth:
    def __init__(self, user_id: str | None = None, error: Exception | None = None):
        self.user_id = user_id
        self.error = error

    def get_user(self, token: str):
        if self.error is not None:
            raise self.error
        user = None if self.user_id is None else SimpleNamespace(id=self.user_id)
        return SimpleNamespace(user=user)


def _client_with_auth(tables: dict, auth: _FakeAuth) -> FakeSupabaseClient:
    client = FakeSupabaseClient(tables)
    client.auth = auth
    return client


def test_accounts_requires_bearer_authentication():
    fake = FakeSupabaseClient({"account": [], "health_score": []})
    app.dependency_overrides[require_supabase_client] = lambda: fake
    try:
        response = TestClient(app).get("/accounts")
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_invalid_bearer_token_is_rejected():
    fake = _client_with_auth(
        {"agency_member": []},
        _FakeAuth(error=AuthApiError("invalid token", 401, "bad_jwt")),
    )
    app.dependency_overrides[require_supabase_client] = lambda: fake
    try:
        response = TestClient(app).get(
            "/accounts", headers={"Authorization": "Bearer invalid"}
        )
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_auth_provider_outage_is_not_misreported_as_bad_credentials():
    fake = _client_with_auth(
        {"agency_member": []},
        _FakeAuth(error=AuthRetryableError("auth unavailable", 503)),
    )
    app.dependency_overrides[require_supabase_client] = lambda: fake
    try:
        response = TestClient(app).get(
            "/accounts", headers={"Authorization": "Bearer valid-token"}
        )
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 503
    assert response.json()["detail"] == "authentication service unavailable"


def test_authenticated_user_only_sees_accounts_in_their_agency():
    fake = _client_with_auth(
        {
            "agency_member": [{"user_id": "user-1", "agency_id": "agency-a"}],
            "account": [
                {
                    "id": "account-a",
                    "agency_id": "agency-a",
                    "name": "Visible",
                    "contract_value_monthly": 1000,
                },
                {
                    "id": "account-b",
                    "agency_id": "agency-b",
                    "name": "Hidden",
                    "contract_value_monthly": 9000,
                },
            ],
            "health_score": [],
        },
        _FakeAuth(user_id="user-1"),
    )
    app.dependency_overrides[require_supabase_client] = lambda: fake
    try:
        response = TestClient(app).get(
            "/accounts?agency_id=agency-b",
            headers={"Authorization": "Bearer valid-token"},
        )
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 200
    assert [account["id"] for account in response.json()] == ["account-a"]


def test_authenticated_user_cannot_read_another_agencys_account():
    hidden_id = "22222222-2222-4222-8222-222222222222"
    fake = _client_with_auth(
        {
            "agency_member": [{"user_id": "user-1", "agency_id": "agency-a"}],
            "account": [
                {
                    "id": hidden_id,
                    "agency_id": "agency-b",
                    "name": "Hidden",
                    "contract_value_monthly": 9000,
                    "contract_start_date": "2025-01-01",
                }
            ],
        },
        _FakeAuth(user_id="user-1"),
    )
    app.dependency_overrides[require_supabase_client] = lambda: fake
    try:
        response = TestClient(app).get(
            f"/accounts/{hidden_id}",
            headers={"Authorization": "Bearer valid-token"},
        )
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 404


def test_alerts_require_bearer_authentication():
    fake = FakeSupabaseClient({"alert": [], "account": []})
    app.dependency_overrides[require_supabase_client] = lambda: fake
    try:
        response = TestClient(app).get("/alerts")
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_authenticated_user_only_sees_alerts_in_their_agency():
    def alert(alert_id: str, account_id: str) -> dict:
        return {
            "id": alert_id,
            "account_id": account_id,
            "triggered_at": "2026-09-13T00:00:00+00:00",
            "signals_fired": ["invoice_days_late"],
            "severity": "high",
            "ai_brief": None,
            "suggested_action": None,
            "status": "open",
        }

    fake = _client_with_auth(
        {
            "agency_member": [{"user_id": "user-1", "agency_id": "agency-a"}],
            "account": [
                {"id": "account-a", "agency_id": "agency-a", "name": "Visible"},
                {"id": "account-b", "agency_id": "agency-b", "name": "Hidden"},
            ],
            "alert": [alert("alert-a", "account-a"), alert("alert-b", "account-b")],
        },
        _FakeAuth(user_id="user-1"),
    )
    app.dependency_overrides[require_supabase_client] = lambda: fake
    try:
        response = TestClient(app).get(
            "/alerts", headers={"Authorization": "Bearer valid-token"}
        )
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == ["alert-a"]


def test_authenticated_user_cannot_mutate_another_agencys_alert():
    alert_id = "33333333-3333-4333-8333-333333333333"
    fake = _client_with_auth(
        {
            "agency_member": [{"user_id": "user-1", "agency_id": "agency-a"}],
            "account": [
                {"id": "account-a", "agency_id": "agency-a", "name": "Visible"},
                {"id": "account-b", "agency_id": "agency-b", "name": "Hidden"},
            ],
            "alert": [
                {
                    "id": alert_id,
                    "account_id": "account-b",
                    "triggered_at": "2026-09-13T00:00:00+00:00",
                    "signals_fired": ["invoice_days_late"],
                    "severity": "high",
                    "ai_brief": None,
                    "suggested_action": None,
                    "status": "open",
                }
            ],
        },
        _FakeAuth(user_id="user-1"),
    )
    app.dependency_overrides[require_supabase_client] = lambda: fake
    try:
        response = TestClient(app).post(
            f"/alerts/{alert_id}/status",
            headers={"Authorization": "Bearer valid-token"},
            json={"status": "resolved"},
        )
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 404
    assert fake._tables["alert"][0]["status"] == "open"


def test_scoring_requires_bearer_authentication():
    fake = FakeSupabaseClient({"signal_snapshot": []})
    app.dependency_overrides[require_supabase_client] = lambda: fake
    try:
        response = TestClient(app).post("/score/recompute/account-a")
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_csv_ingestion_requires_bearer_authentication():
    fake = FakeSupabaseClient({"account": [], "signal_snapshot": []})
    app.dependency_overrides[require_supabase_client] = lambda: fake
    try:
        response = TestClient(app).post(
            "/ingest/csv",
            files={
                "file": (
                    "invoices.csv",
                    "account_email,due_date,paid_date\nclient@example.com,2026-09-01,2026-09-02\n",
                    "text/csv",
                )
            },
        )
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_openapi_marks_protected_routes_with_http_bearer_auth():
    schema = TestClient(app).get("/openapi.json").json()

    assert schema["components"]["securitySchemes"]["HTTPBearer"] == {
        "type": "http",
        "scheme": "bearer",
    }
    assert {"HTTPBearer": []} in schema["paths"]["/accounts"]["get"]["security"]
    assert "security" not in schema["paths"]["/health"]["get"]


def test_authenticated_user_without_membership_is_forbidden():
    fake = _client_with_auth({"agency_member": []}, _FakeAuth(user_id="user-1"))
    app.dependency_overrides[require_supabase_client] = lambda: fake
    try:
        response = TestClient(app).get(
            "/accounts", headers={"Authorization": "Bearer valid-token"}
        )
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 403


def test_cross_agency_score_recompute_is_hidden_and_performs_no_writes():
    hidden_id = "44444444-4444-4444-8444-444444444444"
    fake = _client_with_auth(
        {
            "agency_member": [{"user_id": "user-1", "agency_id": "agency-a"}],
            "account": [
                {
                    "id": hidden_id,
                    "agency_id": "agency-b",
                    "name": "Hidden",
                    "contract_value_monthly": 5000,
                }
            ],
            "signal_snapshot": [
                {
                    "account_id": hidden_id,
                    "period_start": "2026-09-01",
                    "avg_response_time_hours": 4,
                    "meetings_cancelled": 0,
                    "invoice_days_late": 0,
                    "meetings_scheduled": 4,
                }
            ],
        },
        _FakeAuth(user_id="user-1"),
    )
    app.dependency_overrides[require_supabase_client] = lambda: fake
    try:
        response = TestClient(app).post(
            f"/score/recompute/{hidden_id}",
            headers={"Authorization": "Bearer valid-token"},
        )
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 404
    assert fake._tables.get("health_score", []) == []
    assert fake._tables.get("baseline", []) == []


def test_batch_scoring_only_processes_authenticated_agency():
    def stable_history(account_id: str) -> list[dict]:
        return [
            {
                "account_id": account_id,
                "period_start": f"2026-01-{day:02d}",
                "avg_response_time_hours": 4,
                "meetings_cancelled": 0,
                "invoice_days_late": 0,
                "meetings_scheduled": 4,
            }
            for day in range(1, 9)
        ]

    fake = _client_with_auth(
        {
            "agency_member": [{"user_id": "user-1", "agency_id": "agency-a"}],
            "account": [
                {
                    "id": "account-a",
                    "agency_id": "agency-a",
                    "name": "Visible",
                    "contract_value_monthly": 1000,
                },
                {
                    "id": "account-b",
                    "agency_id": "agency-b",
                    "name": "Hidden",
                    "contract_value_monthly": 9000,
                },
            ],
            "signal_snapshot": stable_history("account-a")
            + stable_history("account-b"),
        },
        _FakeAuth(user_id="user-1"),
    )
    app.dependency_overrides[require_supabase_client] = lambda: fake
    try:
        response = TestClient(app).post(
            "/score/recompute", headers={"Authorization": "Bearer valid-token"}
        )
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 200
    assert [item["account_id"] for item in response.json()["results"]] == ["account-a"]
    assert {row["account_id"] for row in fake._tables["health_score"]} == {"account-a"}


def test_csv_ingestion_cannot_match_another_agencys_account():
    fake = _client_with_auth(
        {
            "agency_member": [{"user_id": "user-1", "agency_id": "agency-a"}],
            "account": [
                {
                    "id": "account-b",
                    "agency_id": "agency-b",
                    "primary_contact_email": "hidden@example.com",
                }
            ],
            "signal_snapshot": [
                {
                    "id": "snapshot-b",
                    "account_id": "account-b",
                    "period_start": "2026-08-03",
                    "period_end": "2026-08-09",
                    "invoice_days_late": 0,
                }
            ],
        },
        _FakeAuth(user_id="user-1"),
    )
    app.dependency_overrides[require_supabase_client] = lambda: fake
    csv_content = (
        b"account_email,invoice_date,due_date,paid_date\n"
        b"hidden@example.com,2026-08-01,2026-08-05,2026-08-20\n"
    )
    try:
        response = TestClient(app).post(
            "/ingest/csv",
            headers={"Authorization": "Bearer valid-token"},
            files={"file": ("invoices.csv", csv_content, "text/csv")},
        )
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 200
    assert response.json()["snapshots_updated"] == 0
    assert fake._tables["signal_snapshot"][0]["invoice_days_late"] == 0


def test_google_ingestion_rejects_cross_agency_account_before_google_access(
    monkeypatch,
):
    from app.routers import ingest

    hidden_id = "55555555-5555-4555-8555-555555555555"
    fake = _client_with_auth(
        {
            "agency_member": [{"user_id": "user-1", "agency_id": "agency-a"}],
            "account": [
                {
                    "id": hidden_id,
                    "agency_id": "agency-b",
                    "primary_contact_email": "hidden@example.com",
                }
            ],
        },
        _FakeAuth(user_id="user-1"),
    )
    app.dependency_overrides[require_supabase_client] = lambda: fake

    def unexpected_google_access():
        raise AssertionError("Google credentials must not be touched")

    monkeypatch.setattr(ingest, "get_google_credentials", unexpected_google_access)
    try:
        response = TestClient(app).post(
            f"/ingest/gmail-calendar/{hidden_id}",
            headers={"Authorization": "Bearer valid-token"},
        )
    finally:
        app.dependency_overrides.pop(require_supabase_client, None)

    assert response.status_code == 404
