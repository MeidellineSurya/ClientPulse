# Tests for accounts_repo.py's Supabase reads, using the shared fake
# client — no real database needed.

from app.services.accounts_repo import (
    fetch_account,
    fetch_all_accounts,
    fetch_full_signal_history,
    fetch_health_score_history,
    fetch_latest_health_score,
    fetch_latest_health_scores,
)
from tests.fakes import TEST_AGENCY_ID, FakeSupabaseClient


def test_fetch_all_accounts_returns_every_row():
    client = FakeSupabaseClient(
        {"account": [{"id": "a1", "name": "Acme"}, {"id": "a2", "name": "Beta"}]}
    )
    assert [a["id"] for a in fetch_all_accounts(client, TEST_AGENCY_ID)] == ["a1", "a2"]


def test_fetch_account_returns_the_matching_row():
    client = FakeSupabaseClient({"account": [{"id": "a1", "name": "Acme"}]})
    assert fetch_account(client, "a1", TEST_AGENCY_ID)["name"] == "Acme"


def test_fetch_account_returns_none_when_missing():
    client = FakeSupabaseClient({"account": []})
    assert fetch_account(client, "ghost", TEST_AGENCY_ID) is None


def test_fetch_latest_health_scores_picks_the_most_recent_row_per_account():
    client = FakeSupabaseClient(
        {
            "health_score": [
                {
                    "account_id": "a1",
                    "composite_score": 20.0,
                    "trend_slope": 1.0,
                    "computed_at": "2026-01-01T00:00:00",
                },
                {
                    "account_id": "a1",
                    "composite_score": 60.0,
                    "trend_slope": 5.0,
                    "computed_at": "2026-02-01T00:00:00",
                },
                {
                    "account_id": "a2",
                    "composite_score": 10.0,
                    "trend_slope": 0.0,
                    "computed_at": "2026-01-15T00:00:00",
                },
            ]
        }
    )
    latest = fetch_latest_health_scores(client, ["a1", "a2"])
    assert latest["a1"]["composite_score"] == 60.0
    assert latest["a2"]["composite_score"] == 10.0


def test_fetch_latest_health_score_for_one_account():
    client = FakeSupabaseClient(
        {
            "health_score": [
                {
                    "account_id": "a1",
                    "composite_score": 20.0,
                    "trend_slope": 1.0,
                    "computed_at": "2026-01-01T00:00:00",
                },
                {
                    "account_id": "a1",
                    "composite_score": 60.0,
                    "trend_slope": 5.0,
                    "computed_at": "2026-02-01T00:00:00",
                },
            ]
        }
    )
    assert fetch_latest_health_score(client, "a1")["composite_score"] == 60.0


def test_fetch_latest_health_score_returns_none_when_never_scored():
    client = FakeSupabaseClient({"health_score": []})
    assert fetch_latest_health_score(client, "a1") is None


def test_fetch_health_score_history_sorted_oldest_first():
    client = FakeSupabaseClient(
        {
            "health_score": [
                {
                    "account_id": "a1",
                    "composite_score": 60.0,
                    "trend_slope": 5.0,
                    "computed_at": "2026-02-01T00:00:00",
                },
                {
                    "account_id": "a1",
                    "composite_score": 20.0,
                    "trend_slope": 1.0,
                    "computed_at": "2026-01-01T00:00:00",
                },
                {
                    "account_id": "a2",
                    "composite_score": 10.0,
                    "trend_slope": 0.0,
                    "computed_at": "2026-01-15T00:00:00",
                },
            ]
        }
    )
    history = fetch_health_score_history(client, "a1")
    assert [row["composite_score"] for row in history] == [20.0, 60.0]


def test_fetch_full_signal_history_sorted_oldest_first():
    client = FakeSupabaseClient(
        {
            "signal_snapshot": [
                {
                    "account_id": "a1",
                    "period_start": "2026-02-01",
                    "period_end": "2026-02-07",
                    "avg_response_time_hours": 5,
                    "meetings_scheduled": 2,
                    "meetings_cancelled": 0,
                    "invoice_days_late": 0,
                    "email_thread_count": 10,
                },
                {
                    "account_id": "a1",
                    "period_start": "2026-01-01",
                    "period_end": "2026-01-07",
                    "avg_response_time_hours": 3,
                    "meetings_scheduled": 3,
                    "meetings_cancelled": 0,
                    "invoice_days_late": 0,
                    "email_thread_count": 8,
                },
            ]
        }
    )
    history = fetch_full_signal_history(client, "a1")
    assert [row["period_start"] for row in history] == ["2026-01-01", "2026-02-01"]
