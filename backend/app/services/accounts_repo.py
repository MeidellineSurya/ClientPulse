"""Supabase reads for the account list/detail endpoints. Kept independent
of scoring_repo.py (even though both read signal_snapshot/health_score) so
this workstream doesn't couple to scoring's internals — it only needs the
full row shape for display, not the subset scoring computes drift from.
"""

from supabase import Client

from app.db import with_retry

SIGNAL_SNAPSHOT_COLUMNS = (
    "period_start, period_end, avg_response_time_hours, meetings_scheduled, "
    "meetings_cancelled, invoice_days_late, email_thread_count, primary_contact_email"
)


def fetch_all_accounts(client: Client, agency_id: str) -> list[dict]:
    resp = with_retry(lambda: client.table("account").select("*").eq("agency_id", agency_id).execute())
    return resp.data


def fetch_account(client: Client, account_id: str, agency_id: str) -> dict | None:
    resp = with_retry(
        lambda: client.table("account").select("*").eq("id", account_id).eq("agency_id", agency_id).execute()
    )
    return resp.data[0] if resp.data else None


def fetch_latest_health_scores(
    client: Client, account_ids: list[str]
) -> dict[str, dict]:
    """account_id -> its most recent health_score row, across every
    account. Used by the account list endpoint; Postgres has no
    "latest per group" in a single postgrest call, so this fetches
    everything and reduces in Python (fine at hackathon scale)."""
    if not account_ids:
        return {}
    resp = with_retry(
        lambda: client.table("health_score")
        .select("account_id, composite_score, trend_slope, computed_at")
        .in_("account_id", account_ids)
        .execute()
    )
    latest: dict[str, dict] = {}
    for row in resp.data:
        current = latest.get(row["account_id"])
        if current is None or row["computed_at"] > current["computed_at"]:
            latest[row["account_id"]] = row
    return latest


def fetch_latest_health_score(client: Client, account_id: str) -> dict | None:
    """Most recent health_score row for a single account, or None if it
    has never been scored yet."""
    resp = with_retry(
        lambda: client.table("health_score")
        .select("composite_score, trend_slope, computed_at")
        .eq("account_id", account_id)
        .execute()
    )
    if not resp.data:
        return None
    return max(resp.data, key=lambda row: row["computed_at"])


def fetch_health_score_history(client: Client, account_id: str) -> list[dict]:
    """Every health_score row ever computed for one account, oldest first —
    for the account-detail page's composite-score-over-time chart. Distinct
    from fetch_latest_health_score, which only needs the single most recent
    row."""
    resp = with_retry(
        lambda: client.table("health_score")
        .select("composite_score, trend_slope, computed_at")
        .eq("account_id", account_id)
        .execute()
    )
    return sorted(resp.data, key=lambda row: row["computed_at"])


def fetch_full_signal_history(client: Client, account_id: str) -> list[dict]:
    """All signal_snapshot rows for one account, oldest period first —
    everything the account-detail and per-account charts endpoints need to
    display, not just the subset scoring_repo.fetch_signal_history reads
    for drift computation."""
    resp = with_retry(
        lambda: client.table("signal_snapshot")
        .select(SIGNAL_SNAPSHOT_COLUMNS)
        .eq("account_id", account_id)
        .execute()
    )
    return sorted(resp.data, key=lambda row: row["period_start"])
