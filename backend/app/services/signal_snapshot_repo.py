"""Reads/writes signal_snapshot and account rows needed to wire CSV
invoice data to the right account and weekly period."""

from supabase import Client


def fetch_account_ids_by_email(client: Client, emails: list[str]) -> dict[str, str]:
    if not emails:
        return {}
    resp = (
        client.table("account")
        .select("id, primary_contact_email")
        .in_("primary_contact_email", emails)
        .execute()
    )
    return {row["primary_contact_email"]: row["id"] for row in resp.data}


def fetch_snapshots_by_account(client: Client, account_ids: list[str]) -> dict[str, list[dict]]:
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
    client.table("signal_snapshot").update({"invoice_days_late": days_late}).eq(
        "id", snapshot_id
    ).execute()
