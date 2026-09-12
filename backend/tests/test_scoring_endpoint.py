# End-to-end tests for POST /score/recompute[/{account_id}], using a fake
# Supabase client (no real database needed) injected via FastAPI's
# dependency override.

from fastapi.testclient import TestClient

from app.main import app
from app.routers import scoring
from tests.fakes import FakeSupabaseClient


def _snapshot(account_id: str, period_start: str, **overrides) -> dict:
    row = {
        "account_id": account_id,
        "period_start": period_start,
        "avg_response_time_hours": 4.0,
        "meetings_cancelled": 0,
        "invoice_days_late": 0,
        "meetings_scheduled": 4,
    }
    row.update(overrides)
    return row


def _stable_snapshots(account_id: str) -> list[dict]:
    return [_snapshot(account_id, f"2026-01-{i + 1:02d}") for i in range(8)]


def _worsening_snapshots(account_id: str) -> list[dict]:
    rows = []
    for i in range(8):
        progress = i / 7
        rows.append(
            _snapshot(
                account_id,
                f"2026-01-{i + 1:02d}",
                avg_response_time_hours=4.0 + progress * 20,
                meetings_cancelled=round(progress * 4),
                invoice_days_late=round(progress * 25),
                meetings_scheduled=max(0, round(5 - progress * 5)),
            )
        )
    return rows


def _override_client(fake_client: FakeSupabaseClient) -> TestClient:
    app.dependency_overrides[scoring._require_supabase_client] = lambda: fake_client
    return TestClient(app)


def test_recompute_account_score_stable_account_does_not_fire_alert():
    fake_client = FakeSupabaseClient({"signal_snapshot": _stable_snapshots("acc-1")})
    client = _override_client(fake_client)
    try:
        response = client.post("/score/recompute/acc-1")
    finally:
        app.dependency_overrides.pop(scoring._require_supabase_client, None)

    assert response.status_code == 200
    body = response.json()
    assert body["alert_fired"] is False
    assert fake_client._tables["health_score"][0]["account_id"] == "acc-1"
    assert fake_client._tables.get("alert", []) == []  # no alert row written
    assert len(fake_client._tables["baseline"]) == 4  # one row per tracked signal


def test_recompute_account_score_worsening_account_fires_alert_and_persists_it():
    fake_client = FakeSupabaseClient({"signal_snapshot": _worsening_snapshots("acc-1")})
    client = _override_client(fake_client)
    try:
        response = client.post("/score/recompute/acc-1")
    finally:
        app.dependency_overrides.pop(scoring._require_supabase_client, None)

    assert response.status_code == 200
    body = response.json()
    assert body["alert_fired"] is True
    assert body["severity"] is not None
    assert len(fake_client._tables["alert"]) == 1
    assert fake_client._tables["alert"][0]["account_id"] == "acc-1"


def test_recompute_account_score_twice_does_not_duplicate_alert():
    # Calling /score/recompute more than once against the same unchanged,
    # still-worsening history (e.g. a re-triggered cron before new data has
    # arrived) must not add a second alert row for the same issue.
    fake_client = FakeSupabaseClient({"signal_snapshot": _worsening_snapshots("acc-1")})
    client = _override_client(fake_client)
    try:
        first = client.post("/score/recompute/acc-1")
        second = client.post("/score/recompute/acc-1")
    finally:
        app.dependency_overrides.pop(scoring._require_supabase_client, None)

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(fake_client._tables["alert"]) == 1


def test_recompute_account_score_404_when_no_history():
    fake_client = FakeSupabaseClient({"signal_snapshot": []})
    client = _override_client(fake_client)
    try:
        response = client.post("/score/recompute/ghost")
    finally:
        app.dependency_overrides.pop(scoring._require_supabase_client, None)

    assert response.status_code == 404


def test_recompute_all_scores_skips_accounts_without_history():
    fake_client = FakeSupabaseClient(
        {
            "account": [{"id": "acc-1"}, {"id": "acc-2"}],
            "signal_snapshot": _stable_snapshots("acc-1"),  # acc-2 has none yet
        }
    )
    client = _override_client(fake_client)
    try:
        response = client.post("/score/recompute")
    finally:
        app.dependency_overrides.pop(scoring._require_supabase_client, None)

    assert response.status_code == 200
    body = response.json()
    assert body["accounts_scored"] == 1
    assert body["alerts_fired"] == 0
    assert [r["account_id"] for r in body["results"]] == ["acc-1"]


def test_recompute_without_supabase_configured_returns_503():
    from app.db import get_supabase_client

    get_supabase_client.cache_clear()
    app.dependency_overrides.pop(scoring._require_supabase_client, None)
    client = TestClient(app)

    response = client.post("/score/recompute/acc-1")

    assert response.status_code == 503
