from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.routers import ingest


class _FakeQuery:
    def __init__(self, rows: list[dict]):
        self._rows = rows
        self._payload: dict | None = None

    def select(self, *_args, **_kwargs) -> "_FakeQuery":
        return self

    def in_(self, column: str, values) -> "_FakeQuery":
        values = set(values)
        self._rows = [r for r in self._rows if r.get(column) in values]
        return self

    def eq(self, column: str, value) -> "_FakeQuery":
        self._rows = [r for r in self._rows if r.get(column) == value]
        return self

    def update(self, payload: dict) -> "_FakeQuery":
        self._payload = payload
        return self

    def execute(self) -> SimpleNamespace:
        if self._payload is not None:
            for row in self._rows:
                row.update(self._payload)
        return SimpleNamespace(data=self._rows)


class FakeSupabaseClient:
    def __init__(self, tables: dict[str, list[dict]]):
        self._tables = tables

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(self._tables[name])


def _seed_fake_client() -> FakeSupabaseClient:
    return FakeSupabaseClient(
        {
            "account": [
                {"id": "acc-1", "primary_contact_email": "jordan.brooks@bluepeak-media.com"},
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
    fake_client = _seed_fake_client()
    app.dependency_overrides[ingest._require_supabase_client] = lambda: fake_client
    client = TestClient(app)

    csv_content = (
        b"account_email,invoice_date,due_date,paid_date\n"
        b"jordan.brooks@bluepeak-media.com,2026-08-01,2026-08-05,2026-08-20\n"
    )

    try:
        response = client.post("/ingest/csv", files={"file": ("invoices.csv", csv_content, "text/csv")})
    finally:
        app.dependency_overrides.pop(ingest._require_supabase_client, None)

    assert response.status_code == 200
    body = response.json()
    assert body["snapshots_updated"] == 1
    assert body["unmatched"] == []
    assert fake_client._tables["signal_snapshot"][0]["invoice_days_late"] == 15


def test_ingest_csv_reports_unmatched_account():
    fake_client = _seed_fake_client()
    app.dependency_overrides[ingest._require_supabase_client] = lambda: fake_client
    client = TestClient(app)

    csv_content = (
        b"account_email,invoice_date,due_date,paid_date\n"
        b"ghost@nowhere.com,2026-08-01,2026-08-05,2026-08-20\n"
    )

    try:
        response = client.post("/ingest/csv", files={"file": ("invoices.csv", csv_content, "text/csv")})
    finally:
        app.dependency_overrides.pop(ingest._require_supabase_client, None)

    assert response.status_code == 200
    body = response.json()
    assert body["snapshots_updated"] == 0
    assert body["unmatched"] == [
        {"row_number": 2, "account_email": "ghost@nowhere.com", "reason": "no account with this email"}
    ]


def test_ingest_csv_without_supabase_configured_returns_503():
    from app.db import get_supabase_client

    get_supabase_client.cache_clear()
    app.dependency_overrides.pop(ingest._require_supabase_client, None)
    client = TestClient(app)

    csv_content = b"account_email,invoice_date,due_date,paid_date\na@x.com,2026-08-01,2026-08-05,\n"
    response = client.post("/ingest/csv", files={"file": ("invoices.csv", csv_content, "text/csv")})

    assert response.status_code == 503
