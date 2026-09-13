# End-to-end tests for POST /ingest/csv, using a fake Supabase client (no
# real database needed) injected via FastAPI's dependency override.

from fastapi.testclient import TestClient

from app.auth import require_auth_context
from app.main import app
from tests.fakes import FakeSupabaseClient, authenticated_context


def _seed_fake_client() -> FakeSupabaseClient:
    # One account with one signal_snapshot period, mirroring the shape of
    # real seeded data closely enough to exercise the matching logic.
    return FakeSupabaseClient(
        {
            "account": [
                {
                    "id": "acc-1",
                    "primary_contact_email": "jordan.brooks@bluepeak-media.com",
                },
            ],
            "signal_snapshot": [
                {
                    "id": "snap-1",
                    "account_id": "acc-1",
                    "period_start": "2026-08-03",
                    "period_end": "2026-08-09",
                    "invoice_days_late": 0,
                },
            ],
        }
    )


def test_ingest_csv_updates_matching_snapshot():
    # A CSV row for a known account/period should update invoice_days_late
    # on the matching signal_snapshot row.
    fake_client = _seed_fake_client()
    app.dependency_overrides[require_auth_context] = lambda: authenticated_context(
        fake_client
    )
    client = TestClient(app)

    csv_content = (
        b"account_email,invoice_date,due_date,paid_date\n"
        b"jordan.brooks@bluepeak-media.com,2026-08-01,2026-08-05,2026-08-20\n"
    )

    try:
        response = client.post(
            "/ingest/csv", files={"file": ("invoices.csv", csv_content, "text/csv")}
        )
    finally:
        # Always clean up the override so it doesn't leak into other tests.
        app.dependency_overrides.pop(require_auth_context, None)

    assert response.status_code == 200
    body = response.json()
    assert body["snapshots_updated"] == 1
    assert body["unmatched"] == []
    assert fake_client._tables["signal_snapshot"][0]["invoice_days_late"] == 15


def test_ingest_csv_reports_unmatched_account():
    # An email that doesn't match any seeded account should be reported in
    # `unmatched`, not silently dropped or errored.
    fake_client = _seed_fake_client()
    app.dependency_overrides[require_auth_context] = lambda: authenticated_context(
        fake_client
    )
    client = TestClient(app)

    csv_content = (
        b"account_email,invoice_date,due_date,paid_date\n"
        b"ghost@nowhere.com,2026-08-01,2026-08-05,2026-08-20\n"
    )

    try:
        response = client.post(
            "/ingest/csv", files={"file": ("invoices.csv", csv_content, "text/csv")}
        )
    finally:
        app.dependency_overrides.pop(require_auth_context, None)

    assert response.status_code == 200
    body = response.json()
    assert body["snapshots_updated"] == 0
    assert body["unmatched"] == [
        {
            "row_number": 2,
            "account_email": "ghost@nowhere.com",
            "reason": "no account with this email",
        }
    ]


def test_ingest_csv_without_supabase_configured_returns_503(monkeypatch):
    # A developer's real backend/.env (needed for live testing) would
    # otherwise leak into this test via the module-level settings
    # singleton, masking the "not configured" case this test exists to check.
    from app.config import settings
    from app.db import get_supabase_client

    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "supabase_service_role_key", "")
    get_supabase_client.cache_clear()
    app.dependency_overrides.pop(require_auth_context, None)
    client = TestClient(app)

    csv_content = b"account_email,invoice_date,due_date,paid_date\na@x.com,2026-08-01,2026-08-05,\n"
    response = client.post(
        "/ingest/csv", files={"file": ("invoices.csv", csv_content, "text/csv")}
    )

    assert response.status_code == 503
