"""Regression coverage for atomic, concurrency-safe alert brief persistence."""

from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.main import app
from app.routers import scoring
from app.services.scoring_engine import AccountScoringResult
from tests.fakes import FakeQuery, FakeSupabaseClient


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


def _worsening_snapshots(account_id: str) -> list[dict]:
    rows = []
    for index in range(8):
        progress = index / 7
        rows.append(
            _snapshot(
                account_id,
                f"2026-01-{index + 1:02d}",
                avg_response_time_hours=4.0 + progress * 20,
                meetings_cancelled=round(progress * 4),
                invoice_days_late=round(progress * 25),
                meetings_scheduled=max(0, round(5 - progress * 5)),
            )
        )
    return rows


def _result(severity: str = "high") -> AccountScoringResult:
    return AccountScoringResult(
        composite_score=90.0,
        trend_slope=2.0,
        baselines={},
        drifts={"avg_response_time_hours": 1.0},
        alert_fired=True,
        severity=severity,
        signals_fired=["avg_response_time_hours"],
        signal_contributions={"avg_response_time_hours": 100.0},
        period_scores=[70.0, 80.0, 90.0],
    )


def _tables(alerts: list[dict] | None = None) -> dict[str, list[dict]]:
    return {
        "account": [
            {
                "id": "acc-1",
                "name": "Acme",
                "contract_value_monthly": 10000,
            }
        ],
        "signal_snapshot": [_snapshot("acc-1", "2026-01-01")],
        "alert": alerts or [],
    }


def _post(client: FakeSupabaseClient):
    app.dependency_overrides[scoring._require_supabase_client] = lambda: client
    try:
        return TestClient(app).post("/score/recompute/acc-1")
    finally:
        app.dependency_overrides.pop(scoring._require_supabase_client, None)


class _RejectAlertUpdateQuery(FakeQuery):
    def update(self, payload: dict) -> FakeQuery:
        raise AssertionError("new alert brief must be included in the insert")


class _RejectAlertUpdateClient(FakeSupabaseClient):
    def table(self, name: str) -> FakeQuery:
        table = self._tables.setdefault(name, [])
        return _RejectAlertUpdateQuery(table) if name == "alert" else FakeQuery(table)


def test_new_alert_and_brief_are_persisted_in_one_alert_write(monkeypatch):
    monkeypatch.setattr(
        scoring,
        "build_alert_brief",
        lambda *_args: ("Evidence-bound brief", "Review internally."),
    )
    client = _RejectAlertUpdateClient(
        {
            "account": _tables()["account"],
            "signal_snapshot": _worsening_snapshots("acc-1"),
            "alert": [],
        }
    )

    response = _post(client)

    assert response.status_code == 200
    row = client._tables["alert"][0]
    assert row["ai_brief"] == "Evidence-bound brief"
    assert row["suggested_action"] == "Review internally."


def test_existing_higher_severity_alert_brief_matches_persisted_alert(monkeypatch):
    captured = {}

    def build_brief(_name, _value, result):
        captured["severity"] = result.severity
        return f"Brief for {result.severity} severity", "Review internally."

    monkeypatch.setattr(
        scoring, "score_account_history", lambda _history: _result("medium")
    )
    monkeypatch.setattr(scoring, "build_alert_brief", build_brief)
    existing = {
        "id": "alert-1",
        "account_id": "acc-1",
        "severity": "high",
        "signals_fired": ["invoice_days_late"],
        "status": "open",
        "triggered_at": "2026-01-01T00:00:00+00:00",
    }
    client = FakeSupabaseClient(_tables([existing]))

    response = _post(client)

    assert response.status_code == 200
    assert captured["severity"] == "high"
    assert existing["severity"] == "high"
    assert "high severity" in existing["ai_brief"]


class _ResolveBeforeUpdateQuery(FakeQuery):
    def update(self, payload: dict) -> FakeQuery:
        for row in self._table:
            if row.get("id") == "alert-1":
                row["status"] = "resolved"
                row["revision"] = row.get("revision", 0) + 1
        return super().update(payload)


class _ResolveBeforeUpdateClient(FakeSupabaseClient):
    def table(self, name: str) -> FakeQuery:
        table = self._tables.setdefault(name, [])
        return _ResolveBeforeUpdateQuery(table) if name == "alert" else FakeQuery(table)


def test_recompute_does_not_mutate_alert_resolved_during_brief_generation(monkeypatch):
    monkeypatch.setattr(scoring, "score_account_history", lambda _history: _result())
    monkeypatch.setattr(
        scoring, "build_alert_brief", lambda *_args: ("New brief", "New action")
    )
    existing = {
        "id": "alert-1",
        "account_id": "acc-1",
        "severity": "medium",
        "signals_fired": ["invoice_days_late"],
        "ai_brief": "Human-reviewed brief",
        "suggested_action": "Human-reviewed action",
        "status": "open",
        "triggered_at": "2026-01-01T00:00:00+00:00",
    }
    client = _ResolveBeforeUpdateClient(_tables([existing]))

    response = _post(client)

    assert response.status_code == 409
    assert existing["status"] == "resolved"
    assert existing["severity"] == "medium"
    assert existing["ai_brief"] == "Human-reviewed brief"


class _RefreshSignalsBeforeUpdateQuery(FakeQuery):
    def update(self, payload: dict) -> FakeQuery:
        for row in self._table:
            if row.get("id") == "alert-1":
                row["signals_fired"] = ["meetings_cancelled"]
                row["ai_brief"] = "Newer brief"
                row["revision"] = row.get("revision", 0) + 1
        return super().update(payload)


class _RefreshSignalsBeforeUpdateClient(FakeSupabaseClient):
    def table(self, name: str) -> FakeQuery:
        table = self._tables.setdefault(name, [])
        return (
            _RefreshSignalsBeforeUpdateQuery(table)
            if name == "alert"
            else FakeQuery(table)
        )


def test_stale_recompute_cannot_overwrite_newer_alert_evidence(monkeypatch):
    monkeypatch.setattr(scoring, "score_account_history", lambda _history: _result())
    monkeypatch.setattr(
        scoring, "build_alert_brief", lambda *_args: ("Stale brief", "Stale action")
    )
    existing = {
        "id": "alert-1",
        "account_id": "acc-1",
        "severity": "medium",
        "signals_fired": ["invoice_days_late"],
        "ai_brief": "Original brief",
        "suggested_action": "Original action",
        "status": "open",
        "triggered_at": "2026-01-01T00:00:00+00:00",
    }
    client = _RefreshSignalsBeforeUpdateClient(_tables([existing]))

    response = _post(client)

    assert response.status_code == 409
    assert existing["signals_fired"] == ["meetings_cancelled"]
    assert existing["ai_brief"] == "Newer brief"


class _HumanEditBeforeUpdateQuery(FakeQuery):
    def update(self, payload: dict) -> FakeQuery:
        for row in self._table:
            if row.get("id") == "alert-1":
                row["ai_brief"] = "Human-reviewed brief"
                row["suggested_action"] = "Human-reviewed action"
                row["revision"] = row.get("revision", 0) + 1
        return super().update(payload)


class _HumanEditBeforeUpdateClient(FakeSupabaseClient):
    def table(self, name: str) -> FakeQuery:
        table = self._tables.setdefault(name, [])
        return (
            _HumanEditBeforeUpdateQuery(table) if name == "alert" else FakeQuery(table)
        )


def test_recompute_cannot_overwrite_concurrent_human_brief_edit(monkeypatch):
    monkeypatch.setattr(scoring, "score_account_history", lambda _history: _result())
    monkeypatch.setattr(
        scoring,
        "build_alert_brief",
        lambda *_args: ("Generated brief", "Generated action"),
    )
    existing = {
        "id": "alert-1",
        "account_id": "acc-1",
        "severity": "medium",
        "signals_fired": ["invoice_days_late"],
        "ai_brief": "Original brief",
        "suggested_action": "Original action",
        "status": "open",
        "triggered_at": "2026-01-01T00:00:00+00:00",
    }
    client = _HumanEditBeforeUpdateClient(_tables([existing]))

    response = _post(client)

    assert response.status_code == 409
    assert existing["ai_brief"] == "Human-reviewed brief"
    assert existing["suggested_action"] == "Human-reviewed action"


class _LoseConcurrentInsertQuery(FakeQuery):
    def execute(self):
        if self._insert_payload is not None:
            self._table.append(
                {
                    "id": "winner",
                    "account_id": self._insert_payload["account_id"],
                    "severity": self._insert_payload["severity"],
                    "signals_fired": self._insert_payload["signals_fired"],
                    "ai_brief": "Winning brief",
                    "suggested_action": "Winning action",
                    "status": "open",
                    "triggered_at": "2026-01-01T00:00:00+00:00",
                }
            )
            raise APIError(
                {
                    "code": "23505",
                    "message": "duplicate key value violates unique constraint",
                    "details": "",
                    "hint": "",
                }
            )
        return super().execute()


class _LoseConcurrentInsertClient(FakeSupabaseClient):
    def table(self, name: str) -> FakeQuery:
        table = self._tables.setdefault(name, [])
        return (
            _LoseConcurrentInsertQuery(table) if name == "alert" else FakeQuery(table)
        )


def test_concurrent_recompute_cannot_create_duplicate_active_alert(monkeypatch):
    monkeypatch.setattr(
        scoring,
        "build_alert_brief",
        lambda *_args: ("Losing brief", "Losing action"),
    )
    client = _LoseConcurrentInsertClient(
        {
            "account": _tables()["account"],
            "signal_snapshot": _worsening_snapshots("acc-1"),
            "alert": [],
        }
    )

    response = _post(client)

    assert response.status_code == 409
    assert [row["id"] for row in client._tables["alert"]] == ["winner"]
