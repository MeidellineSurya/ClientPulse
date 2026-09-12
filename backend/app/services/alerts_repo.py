"""Supabase reads/writes for the alerts inbox endpoints.

Account names are joined in Python (a second simple query + dict lookup)
rather than a postgrest embed — consistent with how the rest of this
backend joins across tables (see signal_snapshot_repo.py), and keeps this
module testable against the plain-table FakeSupabaseClient used in tests.
"""

from supabase import Client

ALERT_COLUMNS = "id, account_id, triggered_at, signals_fired, severity, ai_brief, suggested_action, status"


def _fetch_account_names(client: Client, account_ids: list[str]) -> dict[str, str]:
    if not account_ids:
        return {}
    resp = client.table("account").select("id, name").in_("id", account_ids).execute()
    return {row["id"]: row["name"] for row in resp.data}


def fetch_all_alerts(client: Client) -> list[dict]:
    """Every alert across every account, newest triggered_at first, each
    with the account's name attached for display."""
    resp = client.table("alert").select(ALERT_COLUMNS).execute()
    alerts = sorted(resp.data, key=lambda row: row["triggered_at"], reverse=True)
    names = _fetch_account_names(client, [a["account_id"] for a in alerts])
    return [{**alert, "account_name": names.get(alert["account_id"])} for alert in alerts]


def fetch_alerts_for_account(client: Client, account_id: str) -> list[dict]:
    """One account's alerts, newest triggered_at first — for the account
    detail endpoint (no account_name needed, the caller already has it)."""
    resp = client.table("alert").select(ALERT_COLUMNS).eq("account_id", account_id).execute()
    return sorted(resp.data, key=lambda row: row["triggered_at"], reverse=True)


def fetch_alert(client: Client, alert_id: str) -> dict | None:
    resp = client.table("alert").select(ALERT_COLUMNS).eq("id", alert_id).execute()
    return resp.data[0] if resp.data else None


def update_alert_status(client: Client, alert_id: str, status: str) -> dict:
    resp = client.table("alert").update({"status": status}).eq("id", alert_id).execute()
    return resp.data[0]
