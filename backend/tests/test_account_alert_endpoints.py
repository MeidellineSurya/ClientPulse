from app.main import app
from app.routers import accounts, alerts
from fastapi.testclient import TestClient

from tests.fakes import FakeSupabaseClient

client = TestClient(app)


def test_malformed_account_and_alert_ids_are_rejected_before_database_access():
    fake = FakeSupabaseClient({"account": [], "alert": []})
    app.dependency_overrides[accounts._require_supabase_client] = lambda: fake
    app.dependency_overrides[alerts._require_supabase_client] = lambda: fake
    try:
        account_response = client.get("/accounts/not-a-uuid")
        alert_response = client.patch(
            "/alerts/not-a-uuid", json={"status": "acknowledged"}
        )
    finally:
        app.dependency_overrides.clear()

    assert account_response.status_code == 422
    assert alert_response.status_code == 422


def test_accounts_returns_503_when_database_is_not_configured():
    response = client.get("/accounts")

    assert response.status_code == 503
    assert "SUPABASE_URL" in response.json()["detail"]


def test_accounts_returns_sorted_portfolio_with_latest_score_and_active_alert_count():
    fake = FakeSupabaseClient(
        {
            "account": [
                {
                    "id": "acct-z",
                    "agency_id": "agency-1",
                    "name": "Zulu Studio",
                    "contract_value_monthly": 9000,
                    "contract_start_date": "2025-01-01",
                    "primary_contact_email": "zulu@example.com",
                    "created_at": "2025-01-01T00:00:00+00:00",
                },
                {
                    "id": "11111111-1111-4111-8111-111111111111",
                    "agency_id": "agency-1",
                    "name": "Alpha Agency",
                    "contract_value_monthly": 12000,
                    "contract_start_date": "2025-02-01",
                    "primary_contact_email": "alpha@example.com",
                    "created_at": "2025-02-01T00:00:00+00:00",
                },
            ],
            "health_score": [
                {
                    "account_id": "11111111-1111-4111-8111-111111111111",
                    "computed_at": "2026-09-01T00:00:00+00:00",
                    "composite_score": 42.0,
                    "trend_slope": 1.0,
                },
                {
                    "account_id": "11111111-1111-4111-8111-111111111111",
                    "computed_at": "2026-09-08T00:00:00+00:00",
                    "composite_score": 71.5,
                    "trend_slope": 4.2,
                },
            ],
            "alert": [
                {
                    "account_id": "11111111-1111-4111-8111-111111111111",
                    "status": "open",
                },
                {
                    "account_id": "11111111-1111-4111-8111-111111111111",
                    "status": "resolved",
                },
            ],
        }
    )
    app.dependency_overrides[accounts._require_supabase_client] = lambda: fake
    try:
        response = client.get("/accounts")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["name"] for item in body["accounts"]] == [
        "Alpha Agency",
        "Zulu Studio",
    ]
    assert body["accounts"][0]["latest_composite_score"] == 71.5
    assert body["accounts"][0]["active_alert_count"] == 1
    assert body["accounts"][1]["latest_composite_score"] is None


def test_account_detail_returns_score_signal_and_alert_history():
    fake = FakeSupabaseClient(
        {
            "account": [
                {
                    "id": "11111111-1111-4111-8111-111111111111",
                    "agency_id": "agency-1",
                    "name": "Alpha Agency",
                    "contract_value_monthly": 12000,
                    "contract_start_date": "2025-02-01",
                    "primary_contact_email": "alpha@example.com",
                    "created_at": "2025-02-01T00:00:00+00:00",
                }
            ],
            "health_score": [
                {
                    "id": "score-2",
                    "account_id": "11111111-1111-4111-8111-111111111111",
                    "computed_at": "2026-09-08T00:00:00+00:00",
                    "composite_score": 71.5,
                    "trend_slope": 4.2,
                },
                {
                    "id": "score-1",
                    "account_id": "11111111-1111-4111-8111-111111111111",
                    "computed_at": "2026-09-01T00:00:00+00:00",
                    "composite_score": 42.0,
                    "trend_slope": 1.0,
                },
            ],
            "signal_snapshot": [
                {
                    "id": "signal-1",
                    "account_id": "11111111-1111-4111-8111-111111111111",
                    "period_start": "2026-09-01",
                    "period_end": "2026-09-07",
                    "avg_response_time_hours": 8.5,
                    "meetings_scheduled": 3,
                    "meetings_cancelled": 1,
                    "invoice_days_late": 4,
                    "email_thread_count": 12,
                }
            ],
            "alert": [
                {
                    "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    "account_id": "11111111-1111-4111-8111-111111111111",
                    "triggered_at": "2026-09-08T00:00:00+00:00",
                    "signals_fired": ["avg_response_time_hours"],
                    "severity": "high",
                    "ai_brief": "Relationship risk is worsening.",
                    "suggested_action": "Review the account internally.",
                    "status": "open",
                }
            ],
        }
    )
    app.dependency_overrides[accounts._require_supabase_client] = lambda: fake
    try:
        response = client.get("/accounts/11111111-1111-4111-8111-111111111111")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Alpha Agency"
    assert [score["id"] for score in body["score_history"]] == ["score-1", "score-2"]
    assert body["signal_history"][0]["avg_response_time_hours"] == 8.5
    assert body["alerts"][0]["id"] == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def test_account_detail_returns_404_for_unknown_account():
    fake = FakeSupabaseClient({"account": []})
    app.dependency_overrides[accounts._require_supabase_client] = lambda: fake
    try:
        response = TestClient(app, raise_server_exceptions=False).get(
            "/accounts/99999999-9999-4999-8999-999999999999"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "account not found"


def test_alerts_returns_503_when_database_is_not_configured():
    response = client.get("/alerts")

    assert response.status_code == 503
    assert "SUPABASE_URL" in response.json()["detail"]


def test_alerts_filters_by_status_and_includes_account_name():
    fake = FakeSupabaseClient(
        {
            "account": [
                {"id": "11111111-1111-4111-8111-111111111111", "name": "Alpha Agency"},
                {"id": "acct-z", "name": "Zulu Studio"},
            ],
            "alert": [
                {
                    "id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                    "account_id": "11111111-1111-4111-8111-111111111111",
                    "triggered_at": "2026-09-01T00:00:00+00:00",
                    "signals_fired": ["invoice_days_late"],
                    "severity": "medium",
                    "ai_brief": None,
                    "suggested_action": None,
                    "status": "resolved",
                },
                {
                    "id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
                    "account_id": "acct-z",
                    "triggered_at": "2026-09-10T00:00:00+00:00",
                    "signals_fired": ["meetings_cancelled"],
                    "severity": "high",
                    "ai_brief": "Meeting behaviour is worsening.",
                    "suggested_action": "Review the account internally.",
                    "status": "open",
                },
            ],
        }
    )
    app.dependency_overrides[alerts._require_supabase_client] = lambda: fake
    try:
        response = client.get("/alerts?status=open")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["alerts"][0]["id"] == "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
    assert body["alerts"][0]["account_name"] == "Zulu Studio"


def test_alert_status_can_be_acknowledged():
    alert_row = {
        "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "account_id": "11111111-1111-4111-8111-111111111111",
        "triggered_at": "2026-09-10T00:00:00+00:00",
        "signals_fired": ["meetings_cancelled"],
        "severity": "high",
        "ai_brief": "Meeting behaviour is worsening.",
        "suggested_action": "Review the account internally.",
        "status": "open",
    }
    fake = FakeSupabaseClient(
        {
            "account": [
                {"id": "11111111-1111-4111-8111-111111111111", "name": "Alpha Agency"}
            ],
            "alert": [alert_row],
        }
    )
    app.dependency_overrides[alerts._require_supabase_client] = lambda: fake
    try:
        response = client.patch(
            "/alerts/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            json={"status": "acknowledged"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "acknowledged"
    assert response.json()["account_name"] == "Alpha Agency"
    assert alert_row["status"] == "acknowledged"


def test_alert_status_update_returns_404_for_unknown_alert():
    fake = FakeSupabaseClient({"alert": []})
    app.dependency_overrides[alerts._require_supabase_client] = lambda: fake
    try:
        response = TestClient(app, raise_server_exceptions=False).patch(
            "/alerts/99999999-9999-4999-8999-999999999999",
            json={"status": "resolved"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "alert not found"


def test_resolved_alert_cannot_be_moved_back_to_acknowledged():
    alert_row = {
        "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "account_id": "11111111-1111-4111-8111-111111111111",
        "triggered_at": "2026-09-10T00:00:00+00:00",
        "signals_fired": [],
        "severity": "medium",
        "ai_brief": None,
        "suggested_action": None,
        "status": "resolved",
    }
    fake = FakeSupabaseClient(
        {
            "account": [
                {"id": "11111111-1111-4111-8111-111111111111", "name": "Alpha Agency"}
            ],
            "alert": [alert_row],
        }
    )
    app.dependency_overrides[alerts._require_supabase_client] = lambda: fake
    try:
        response = client.patch(
            "/alerts/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            json={"status": "acknowledged"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["detail"] == "resolved alerts cannot be reopened"
    assert alert_row["status"] == "resolved"
