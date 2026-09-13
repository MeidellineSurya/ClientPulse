"""Reads/writes signal_snapshot and account rows needed to wire CSV
invoice data to the right account and weekly period."""

from supabase import Client


def fetch_account_ids_by_email(
    client: Client, emails: list[str], agency_id: str
) -> dict[str, str]:
    # Looks up which of the given emails match a seeded account's
    # primary_contact_email, returning email -> account_id for matches only.
    if not emails:
        return {}
    resp = (
        client.table("account")
        .select("id, primary_contact_email")
        .eq("agency_id", agency_id)
        .in_("primary_contact_email", emails)
        .execute()
    )
    return {row["primary_contact_email"]: row["id"] for row in resp.data}


def fetch_snapshots_by_account(
    client: Client, account_ids: list[str]
) -> dict[str, list[dict]]:
    # Fetches all signal_snapshot periods for the given accounts, grouped by
    # account_id, so csv_wiring can find which period a due_date falls in.
    if not account_ids:
        return {}
    resp = (
        client.table("signal_snapshot")
        .select("id, account_id, period_start, period_end")
        .in_("account_id", account_ids)
        .execute()
    )
    by_account: dict[str, list[dict]] = {}
    for row in resp.data:
        by_account.setdefault(row["account_id"], []).append(row)
    return by_account


def update_invoice_days_late(client: Client, snapshot_id: str, days_late: int) -> None:
    # Writes the computed lateness onto one existing signal_snapshot row.
    client.table("signal_snapshot").update({"invoice_days_late": days_late}).eq(
        "id", snapshot_id
    ).execute()


def fetch_account_email(client: Client, account_id: str, agency_id: str) -> str | None:
    # Looks up one account's primary_contact_email, used to query Gmail/Calendar.
    resp = (
        client.table("account")
        .select("primary_contact_email")
        .eq("id", account_id)
        .eq("agency_id", agency_id)
        .execute()
    )
    return resp.data[0]["primary_contact_email"] if resp.data else None


def find_snapshot_for_period(
    client: Client, account_id: str, period_start: str, period_end: str
) -> str | None:
    resp = (
        client.table("signal_snapshot")
        .select("id")
        .eq("account_id", account_id)
        .eq("period_start", period_start)
        .eq("period_end", period_end)
        .execute()
    )
    return resp.data[0]["id"] if resp.data else None


def upsert_gmail_calendar_signals(
    client: Client,
    account_id: str,
    period_start: str,
    period_end: str,
    avg_response_time_hours: float,
    email_thread_count: int,
    meetings_scheduled: int,
    meetings_cancelled: int,
) -> None:
    """Writes Gmail/Calendar-derived columns onto the signal_snapshot row
    for this account/period — updating it if the period was already
    seeded/created, inserting a new row otherwise (e.g. for the current,
    not-yet-seeded week). Never touches invoice_days_late, which CSV
    ingestion owns.
    """
    payload = {
        "avg_response_time_hours": avg_response_time_hours,
        "email_thread_count": email_thread_count,
        "meetings_scheduled": meetings_scheduled,
        "meetings_cancelled": meetings_cancelled,
    }
    snapshot_id = find_snapshot_for_period(client, account_id, period_start, period_end)
    if snapshot_id is not None:
        client.table("signal_snapshot").update(payload).eq("id", snapshot_id).execute()
    else:
        client.table("signal_snapshot").insert(
            {
                **payload,
                "account_id": account_id,
                "period_start": period_start,
                "period_end": period_end,
            }
        ).execute()
