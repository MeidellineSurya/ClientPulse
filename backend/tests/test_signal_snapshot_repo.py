# Tests for signal_snapshot_repo's Gmail/Calendar upsert logic, using the
# shared fake Supabase client — no real database needed.

from app.services.signal_snapshot_repo import upsert_gmail_calendar_signals
from tests.fakes import FakeSupabaseClient


def test_upsert_updates_existing_snapshot_without_touching_invoice_days_late():
    # A signal_snapshot row already exists for this account/period (e.g.
    # seeded) — the Gmail/Calendar columns should update in place while
    # invoice_days_late (owned by CSV ingestion) stays untouched.
    client = FakeSupabaseClient(
        {
            "signal_snapshot": [
                {
                    "id": "snap-1",
                    "account_id": "acc-1",
                    "period_start": "2026-08-03",
                    "period_end": "2026-08-09",
                    "invoice_days_late": 7,
                    "avg_response_time_hours": 0,
                    "email_thread_count": 0,
                    "meetings_scheduled": 0,
                    "meetings_cancelled": 0,
                },
            ]
        }
    )

    upsert_gmail_calendar_signals(client, "acc-1", "2026-08-03", "2026-08-09", 4.5, 20, 3, 1)

    row = client._tables["signal_snapshot"][0]
    assert row["avg_response_time_hours"] == 4.5
    assert row["email_thread_count"] == 20
    assert row["meetings_scheduled"] == 3
    assert row["meetings_cancelled"] == 1
    assert row["invoice_days_late"] == 7  # untouched — CSV ingestion owns this column


def test_upsert_inserts_new_snapshot_when_period_not_seeded():
    # No row exists yet for this account/period (e.g. the current week,
    # which the 8-week seed data doesn't cover) — should insert a new row
    # rather than silently doing nothing.
    client = FakeSupabaseClient({"signal_snapshot": []})

    upsert_gmail_calendar_signals(client, "acc-1", "2026-09-07", "2026-09-13", 2.0, 10, 1, 0)

    rows = client._tables["signal_snapshot"]
    assert len(rows) == 1
    assert rows[0]["account_id"] == "acc-1"
    assert rows[0]["period_start"] == "2026-09-07"
    assert rows[0]["period_end"] == "2026-09-13"
    assert rows[0]["email_thread_count"] == 10
