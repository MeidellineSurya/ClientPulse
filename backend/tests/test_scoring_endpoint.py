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
    assert len(fake_client._tables["baseline"]) == 5  # one row per tracked signal


def test_recompute_account_score_worsening_account_fires_alert_and_persists_it():
    fake_client = FakeSupabaseClient(
        {
            "account": [{"id": "acc-1", "name": "Acme", "contract_value_monthly": 10000}],
            "signal_snapshot": _worsening_snapshots("acc-1"),
        }
    )
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
    assert round(sum(body["signal_contributions"].values()), 0) == 100
    # This fixture has no primary_contact_email data, so contact_changed
    # (weight 0.20) never drifts — the other four signals maxing out caps
    # composite_score at 80, not 100. revenue_at_risk should be close to
    # that share of the full annualized contract value ($120,000 x 0.8).
    assert body["revenue_at_risk"] > 90000


def test_recompute_account_score_with_no_contract_value_on_record_reports_zero_risk():
    # No "account" table entry at all for this id — fetch_contract_value
    # falls back to 0 rather than erroring, so the score itself is still
    # computed and returned.
    fake_client = FakeSupabaseClient({"signal_snapshot": _stable_snapshots("acc-1")})
    client = _override_client(fake_client)
    try:
        response = client.post("/score/recompute/acc-1")
    finally:
        app.dependency_overrides.pop(scoring._require_supabase_client, None)

    assert response.status_code == 200
    assert response.json()["revenue_at_risk"] == 0.0


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
            "account": [
                {"id": "acc-1", "name": "Acme", "contract_value_monthly": 10000},
                {"id": "acc-2", "name": "Beta", "contract_value_monthly": 5000},
            ],
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
    # acc-1 is stable (composite_score=0) -> zero revenue at risk, and the
    # portfolio-wide total should match the sum of the (single) result.
    assert body["results"][0]["revenue_at_risk"] == 0.0
    assert body["total_revenue_at_risk"] == 0.0


def test_recompute_all_scores_totals_revenue_at_risk_across_alerting_accounts_only():
    # acc-1 worsens (fires); acc-2 stays stable (doesn't) — the portfolio
    # total should only reflect acc-1's exposure, not acc-2's.
    fake_client = FakeSupabaseClient(
        {
            "account": [
                {"id": "acc-1", "name": "Acme", "contract_value_monthly": 10000},
                {"id": "acc-2", "name": "Beta", "contract_value_monthly": 8000},
            ],
            "signal_snapshot": _worsening_snapshots("acc-1") + _stable_snapshots("acc-2"),
        }
    )
    client = _override_client(fake_client)
    try:
        response = client.post("/score/recompute")
    finally:
        app.dependency_overrides.pop(scoring._require_supabase_client, None)

    assert response.status_code == 200
    body = response.json()
    results_by_id = {r["account_id"]: r for r in body["results"]}
    assert results_by_id["acc-1"]["alert_fired"] is True
    assert results_by_id["acc-2"]["alert_fired"] is False
    assert results_by_id["acc-2"]["revenue_at_risk"] == 0.0  # stable -> composite_score 0
    assert body["total_revenue_at_risk"] == results_by_id["acc-1"]["revenue_at_risk"]
    assert body["total_revenue_at_risk"] > 0


def test_recompute_all_scores_isolates_a_failing_account_instead_of_aborting_the_batch():
    # acc-bad has a malformed signal value (float() will raise on it) —
    # that must not prevent acc-good from being scored.
    fake_client = FakeSupabaseClient(
        {
            "account": [
                {"id": "acc-bad", "name": "Bad Co", "contract_value_monthly": 5000},
                {"id": "acc-good", "name": "Good Co", "contract_value_monthly": 5000},
            ],
            "signal_snapshot": [
                _snapshot("acc-bad", "2026-01-01", avg_response_time_hours="not-a-number"),
            ]
            + _stable_snapshots("acc-good"),
        }
    )
    client = _override_client(fake_client)
    try:
        response = client.post("/score/recompute")
    finally:
        app.dependency_overrides.pop(scoring._require_supabase_client, None)

    assert response.status_code == 200
    body = response.json()
    assert body["failed_account_ids"] == ["acc-bad"]
    assert [r["account_id"] for r in body["results"]] == ["acc-good"]
    assert body["accounts_scored"] == 1


def test_recompute_without_supabase_configured_returns_503(monkeypatch):
    from app.config import settings
    from app.db import get_supabase_client

    # A developer's real backend/.env (needed for live testing) would
    # otherwise leak into this test via the module-level settings
    # singleton, masking the "not configured" case this test exists to check.
    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "supabase_service_role_key", "")
    get_supabase_client.cache_clear()
    app.dependency_overrides.pop(scoring._require_supabase_client, None)
    client = TestClient(app)

    response = client.post("/score/recompute/acc-1")

    assert response.status_code == 503
