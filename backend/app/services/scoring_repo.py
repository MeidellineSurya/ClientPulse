"""Reads signal_snapshot history and writes baseline/health_score/alert
rows for the scoring engine. All Supabase I/O for scoring lives here so the
pure math in scoring_engine.py / baseline_engine.py stays testable without
a database.
"""

from supabase import Client

from app.services.baseline_engine import TRACKED_SIGNALS


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
    client.table("alert").insert(
        {
            "account_id": account_id,
            "signals_fired": signals_fired,
            "severity": severity,
            "status": "open",
        }
    ).execute()
