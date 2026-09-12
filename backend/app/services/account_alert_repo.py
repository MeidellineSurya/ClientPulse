"""Supabase access for account portfolio and alert inbox endpoints."""

from typing import Literal

from supabase import Client  # type: ignore[attr-defined]

AlertStatus = Literal["open", "acknowledged", "resolved"]


def list_accounts(client: Client) -> list[dict]:
    return client.table("account").select("*").execute().data


def get_account(client: Client, account_id: str) -> dict | None:
    rows = client.table("account").select("*").eq("id", account_id).execute().data
    return rows[0] if rows else None


def list_health_scores(client: Client, account_id: str | None = None) -> list[dict]:
    query = client.table("health_score").select("*")
    if account_id is not None:
        query = query.eq("account_id", account_id)
    return query.execute().data


def list_signal_snapshots(client: Client, account_id: str) -> list[dict]:
    return (
        client.table("signal_snapshot")
        .select("*")
        .eq("account_id", account_id)
        .execute()
        .data
    )


def list_alerts(
    client: Client,
    *,
    status: AlertStatus | None = None,
    account_id: str | None = None,
) -> list[dict]:
    query = client.table("alert").select("*")
    if status is not None:
        query = query.eq("status", status)
    if account_id is not None:
        query = query.eq("account_id", account_id)
    return query.execute().data


def list_active_alerts(client: Client) -> list[dict]:
    return (
        client.table("alert")
        .select("account_id, status")
        .in_("status", ["open", "acknowledged"])
        .execute()
        .data
    )


def get_alert(client: Client, alert_id: str) -> dict | None:
    rows = client.table("alert").select("*").eq("id", alert_id).execute().data
    return rows[0] if rows else None


def account_names_by_id(client: Client) -> dict[str, str]:
    rows = client.table("account").select("id, name").execute().data
    return {row["id"]: row["name"] for row in rows}


def update_alert_status_if_current(
    client: Client,
    alert_id: str,
    *,
    current_status: AlertStatus,
    new_status: Literal["acknowledged", "resolved"],
) -> dict | None:
    rows = (
        client.table("alert")
        .update({"status": new_status})
        .eq("id", alert_id)
        .eq("status", current_status)
        .execute()
        .data
    )
    return rows[0] if rows else None
