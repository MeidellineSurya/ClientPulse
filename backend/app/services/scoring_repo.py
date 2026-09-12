"""Reads signal_snapshot history and writes baseline/health_score/alert
rows for the scoring engine. All Supabase I/O for scoring lives here so the
pure math in scoring_engine.py / baseline_engine.py stays testable without
a database.
"""

from datetime import datetime, timezone

from supabase import Client

from app.services.baseline_engine import TRACKED_SIGNALS
from app.services.scoring_engine import SEVERITY_ORDER


def fetch_all_account_ids(client: Client) -> list[str]:
    resp = client.table("account").select("id").execute()
    return [row["id"] for row in resp.data]


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
    pair is what makes this an upsert rather than a plain insert."""
    for signal_name, (rolling_avg, rolling_stddev) in baselines.items():
        client.table("baseline").upsert(
            {
                "account_id": account_id,
                "signal_name": signal_name,
                "rolling_avg": rolling_avg,
                "rolling_stddev": rolling_stddev,
            },
            on_conflict="account_id,signal_name",
        ).execute()


def insert_health_score(client: Client, account_id: str, composite_score: float, trend_slope: float) -> None:
    client.table("health_score").insert(
        {"account_id": account_id, "composite_score": composite_score, "trend_slope": trend_slope}
    ).execute()


def insert_alert(client: Client, account_id: str, signals_fired: list[str], severity: str) -> None:
    # triggered_at is set explicitly (rather than left to schema.sql's
    # column default) so it's available immediately on the row this
    # function returns/writes — fetch_open_alert needs it to find the most
    # recent open alert without a second round trip.
    client.table("alert").insert(
        {
            "account_id": account_id,
            "signals_fired": signals_fired,
            "severity": severity,
            "status": "open",
            "triggered_at": datetime.now(timezone.utc).isoformat(),
        }
    ).execute()


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


def upsert_alert(client: Client, account_id: str, signals_fired: list[str], severity: str) -> None:
    """Fires a new alert, or escalates the account's existing open one in
    place, instead of always inserting — otherwise every /score/recompute
    call on a still-worsening account would add another row and flood the
    alerts inbox with duplicates of the same underlying issue.

    A steady or improved-but-still-alerting severity leaves the existing
    alert untouched (including its original triggered_at, i.e. when this
    was first flagged); only a genuine escalation updates it in place.
    """
    existing = fetch_open_alert(client, account_id)
    if existing is None:
        insert_alert(client, account_id, signals_fired, severity)
        return
    if SEVERITY_ORDER.index(severity) > SEVERITY_ORDER.index(existing["severity"]):
        update_alert_severity(client, existing["id"], severity, signals_fired)
