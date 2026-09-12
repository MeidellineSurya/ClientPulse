"""Reads signal_snapshot history and writes baseline/health_score/alert
rows for the scoring engine. All Supabase I/O for scoring lives here so the
pure math in scoring_engine.py / baseline_engine.py stays testable without
a database.
"""

import uuid
from datetime import datetime, timezone

from supabase import Client

from app.services.baseline_engine import TRACKED_SIGNALS
from app.services.scoring_engine import SEVERITY_ORDER


def fetch_contract_value(client: Client, account_id: str) -> float:
    """One account's contract_value_monthly, for the revenue-at-risk
    calculation. Falls back to 0 if the account row is somehow missing it
    (shouldn't happen against a real schema.sql-backed table, which
    defaults this column to 0 and never allows null)."""
    resp = client.table("account").select("contract_value_monthly").eq("id", account_id).execute()
    if not resp.data:
        return 0.0
    return float(resp.data[0].get("contract_value_monthly", 0.0))


def fetch_accounts_with_contract_value(client: Client) -> dict[str, tuple[float, str]]:
    """account_id -> (contract_value_monthly, name) for every account, so
    the batch /score/recompute endpoint can get the account list, contract
    value, and display name (the latter for brief generation) in one query."""
    resp = client.table("account").select("id, name, contract_value_monthly").execute()
    return {row["id"]: (float(row.get("contract_value_monthly", 0.0)), row["name"]) for row in resp.data}


def fetch_signal_history(client: Client, account_id: str) -> list[dict]:
    """All signal_snapshot rows for one account, oldest period first."""
    resp = (
        client.table("signal_snapshot")
        .select("period_start, period_end, " + ", ".join(TRACKED_SIGNALS))
        .eq("account_id", account_id)
        .execute()
    )
    return sorted(resp.data, key=lambda row: row["period_start"])


def upsert_baselines(client: Client, account_id: str, baselines: dict[str, tuple[float, float | None]]) -> None:
    """Writes one baseline row per signal, replacing any existing row for
    that (account_id, signal_name) — schema.sql's unique constraint on that
    pair is what makes this an upsert rather than a plain insert.

    Batched into a single upsert call (supabase-py accepts a list of rows)
    instead of one round trip per signal — this runs once per account in
    /score/recompute's batch endpoint, so 4x fewer requests adds up.
    """
    payload = [
        {
            "account_id": account_id,
            "signal_name": signal_name,
            "rolling_avg": rolling_avg,
            "rolling_stddev": rolling_stddev,
        }
        for signal_name, (rolling_avg, rolling_stddev) in baselines.items()
    ]
    client.table("baseline").upsert(payload, on_conflict="account_id,signal_name").execute()


def insert_health_score(client: Client, account_id: str, composite_score: float, trend_slope: float) -> None:
    client.table("health_score").insert(
        {"account_id": account_id, "composite_score": composite_score, "trend_slope": trend_slope}
    ).execute()


def insert_alert(client: Client, account_id: str, signals_fired: list[str], severity: str) -> str:
    # id and triggered_at are set explicitly (rather than left to
    # schema.sql's column defaults) so they're available immediately to the
    # caller without a second round trip — the brief-generation step needs
    # the id right away to attach ai_brief/suggested_action to this row.
    alert_id = str(uuid.uuid4())
    client.table("alert").insert(
        {
            "id": alert_id,
            "account_id": account_id,
            "signals_fired": signals_fired,
            "severity": severity,
            "status": "open",
            "triggered_at": datetime.now(timezone.utc).isoformat(),
        }
    ).execute()
    return alert_id


def fetch_open_alert(client: Client, account_id: str) -> dict | None:
    """The account's most recent open/acknowledged alert, if any. Used to
    avoid firing a duplicate alert for the same still-unresolved issue every
    time /score/recompute runs."""
    resp = (
        client.table("alert")
        .select("id, severity, signals_fired, status, triggered_at")
        .eq("account_id", account_id)
        .in_("status", ["open", "acknowledged"])
        .execute()
    )
    if not resp.data:
        return None
    return max(resp.data, key=lambda row: row["triggered_at"])


def update_alert_severity(client: Client, alert_id: str, severity: str, signals_fired: list[str]) -> None:
    client.table("alert").update({"severity": severity, "signals_fired": signals_fired}).eq("id", alert_id).execute()


def upsert_alert(client: Client, account_id: str, signals_fired: list[str], severity: str) -> str:
    """Fires a new alert, or refreshes the account's existing open one in
    place, instead of always inserting — otherwise every /score/recompute
    call on a still-worsening account would add another row and flood the
    alerts inbox with duplicates of the same underlying issue. Always
    returns the alert's id, so the caller can attach a brief to it.

    severity only ever escalates (never downgrades) on an existing alert —
    triggered_at is preserved as "when this was first flagged" regardless.
    signals_fired, however, is always refreshed to the latest evaluation:
    an alert still open because of sustained risk should show what's
    *currently* driving it, even if severity hasn't changed — otherwise an
    account whose problem shifted from, say, late invoices to cancelled
    meetings would keep showing the stale original cause.
    """
    existing = fetch_open_alert(client, account_id)
    if existing is None:
        return insert_alert(client, account_id, signals_fired, severity)

    new_severity = (
        severity if SEVERITY_ORDER.index(severity) > SEVERITY_ORDER.index(existing["severity"]) else existing["severity"]
    )
    if new_severity != existing["severity"] or signals_fired != existing.get("signals_fired"):
        update_alert_severity(client, existing["id"], new_severity, signals_fired)
    return existing["id"]


def set_alert_brief(client: Client, alert_id: str, ai_brief: str, suggested_action: str) -> None:
    client.table("alert").update({"ai_brief": ai_brief, "suggested_action": suggested_action}).eq(
        "id", alert_id
    ).execute()
