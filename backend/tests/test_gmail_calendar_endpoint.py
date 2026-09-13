from datetime import UTC, datetime

from app.main import app
from app.routers import ingest
from app.services.calendar_signals import CalendarEvent
from app.services.gmail_signals import MessageMetadata
from fastapi.testclient import TestClient
from google.auth.exceptions import RefreshError, TransportError
from googleapiclient.errors import HttpError
from httplib2 import Response, ServerNotFoundError

from tests.fakes import FakeSupabaseClient


def _client_with_account() -> FakeSupabaseClient:
    return FakeSupabaseClient(
        {
            "account": [
                {
                    "id": "11111111-1111-4111-8111-111111111111",
                    "primary_contact_email": "client@example.com",
                }
            ],
            "signal_snapshot": [],
        }
    )


def test_gmail_calendar_ingestion_writes_computed_live_signals(monkeypatch):
    fake = _client_with_account()
    fake._tables["signal_snapshot"].append(
        {
            "id": "snapshot-1",
            "account_id": "11111111-1111-4111-8111-111111111111",
            "period_start": "2026-09-01",
            "period_end": "2026-09-07",
            "invoice_days_late": 4,
        }
    )
    app.dependency_overrides[ingest._require_supabase_client] = lambda: fake
    monkeypatch.setattr(ingest, "get_google_credentials", lambda: object())
    monkeypatch.setattr(ingest, "get_gmail_service", lambda _credentials: object())
    monkeypatch.setattr(ingest, "get_calendar_service", lambda _credentials: object())
    monkeypatch.setattr(
        ingest,
        "fetch_message_metadata",
        lambda *_args: [
            MessageMetadata(
                message_id="inbound",
                thread_id="thread-1",
                from_addr="client@example.com",
                to_addr="agency@example.com",
                date=datetime(2026, 9, 2, 9, tzinfo=UTC),
            ),
            MessageMetadata(
                message_id="reply",
                thread_id="thread-1",
                from_addr="agency@example.com",
                to_addr="client@example.com",
                date=datetime(2026, 9, 2, 12, tzinfo=UTC),
            ),
        ],
    )
    monkeypatch.setattr(
        ingest,
        "fetch_events",
        lambda *_args: [
            CalendarEvent("confirmed", ["client@example.com"]),
            CalendarEvent("cancelled", ["client@example.com"]),
        ],
    )

    try:
        response = TestClient(app).post(
            "/ingest/gmail-calendar/11111111-1111-4111-8111-111111111111"
            "?period_start=2026-09-01&period_end=2026-09-07"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "account_id": "11111111-1111-4111-8111-111111111111",
        "period_start": "2026-09-01",
        "period_end": "2026-09-07",
        "avg_response_time_hours": 3.0,
        "email_thread_count": 1,
        "meetings_scheduled": 1,
        "meetings_cancelled": 1,
    }
    assert fake._tables["signal_snapshot"][0] == {
        "id": "snapshot-1",
        "account_id": "11111111-1111-4111-8111-111111111111",
        "period_start": "2026-09-01",
        "period_end": "2026-09-07",
        "invoice_days_late": 4,
        "avg_response_time_hours": 3.0,
        "email_thread_count": 1,
        "meetings_scheduled": 1,
        "meetings_cancelled": 1,
        "primary_contact_email": "client@example.com",
    }


def test_gmail_calendar_rejects_malformed_account_id():
    fake = FakeSupabaseClient({"account": [], "signal_snapshot": []})
    app.dependency_overrides[ingest._require_supabase_client] = lambda: fake
    try:
        response = TestClient(app).post("/ingest/gmail-calendar/not-a-uuid")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_gmail_calendar_rejects_partial_period():
    fake = _client_with_account()
    app.dependency_overrides[ingest._require_supabase_client] = lambda: fake
    try:
        response = TestClient(app).post(
            "/ingest/gmail-calendar/11111111-1111-4111-8111-111111111111?period_start=2026-09-01"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "period_start and period_end must be provided together"
    )


def test_gmail_calendar_rejects_reversed_period():
    fake = _client_with_account()
    app.dependency_overrides[ingest._require_supabase_client] = lambda: fake
    try:
        response = TestClient(app).post(
            "/ingest/gmail-calendar/11111111-1111-4111-8111-111111111111"
            "?period_start=2026-09-08&period_end=2026-09-01"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["detail"] == "period_end must not be before period_start"


def test_gmail_calendar_returns_503_when_google_oauth_refresh_fails(monkeypatch):
    fake = _client_with_account()
    app.dependency_overrides[ingest._require_supabase_client] = lambda: fake

    def fail_credentials():
        raise RefreshError("refresh token was rejected")

    monkeypatch.setattr(ingest, "get_google_credentials", fail_credentials)
    try:
        response = TestClient(app, raise_server_exceptions=False).post(
            "/ingest/gmail-calendar/11111111-1111-4111-8111-111111111111"
            "?period_start=2026-09-01&period_end=2026-09-07"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert (
        response.json()["detail"] == "Google OAuth credentials could not be refreshed"
    )


def test_gmail_calendar_returns_503_when_google_oauth_transport_fails(monkeypatch):
    fake = _client_with_account()
    app.dependency_overrides[ingest._require_supabase_client] = lambda: fake

    def fail_credentials():
        raise TransportError("token endpoint unavailable")

    monkeypatch.setattr(ingest, "get_google_credentials", fail_credentials)
    try:
        response = TestClient(app, raise_server_exceptions=False).post(
            "/ingest/gmail-calendar/11111111-1111-4111-8111-111111111111"
            "?period_start=2026-09-01&period_end=2026-09-07"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert (
        response.json()["detail"] == "Google OAuth credentials could not be refreshed"
    )


def test_gmail_calendar_returns_502_when_google_api_request_fails(monkeypatch):
    fake = _client_with_account()
    app.dependency_overrides[ingest._require_supabase_client] = lambda: fake
    monkeypatch.setattr(ingest, "get_google_credentials", lambda: object())
    monkeypatch.setattr(ingest, "get_gmail_service", lambda _credentials: object())
    monkeypatch.setattr(ingest, "get_calendar_service", lambda _credentials: object())

    def fail_fetch(*_args):
        raise HttpError(Response({"status": "403"}), b'{"error":"denied"}')

    monkeypatch.setattr(ingest, "fetch_message_metadata", fail_fetch)
    try:
        response = TestClient(app, raise_server_exceptions=False).post(
            "/ingest/gmail-calendar/11111111-1111-4111-8111-111111111111"
            "?period_start=2026-09-01&period_end=2026-09-07"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json()["detail"] == "Google Gmail/Calendar request failed"


def test_gmail_calendar_returns_502_when_google_transport_fails(monkeypatch):
    fake = _client_with_account()
    app.dependency_overrides[ingest._require_supabase_client] = lambda: fake
    monkeypatch.setattr(ingest, "get_google_credentials", lambda: object())
    monkeypatch.setattr(ingest, "get_gmail_service", lambda _credentials: object())
    monkeypatch.setattr(ingest, "get_calendar_service", lambda _credentials: object())

    def fail_fetch(*_args):
        raise ServerNotFoundError("gmail.googleapis.com")

    monkeypatch.setattr(ingest, "fetch_message_metadata", fail_fetch)
    try:
        response = TestClient(app, raise_server_exceptions=False).post(
            "/ingest/gmail-calendar/11111111-1111-4111-8111-111111111111"
            "?period_start=2026-09-01&period_end=2026-09-07"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json()["detail"] == "Google Gmail/Calendar request failed"
