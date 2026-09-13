"""One-time backfill: persists the per-period composite risk scores the
scoring engine already computes for each account's trend window (see
score_account_history in app/services/scoring_engine.py) but that
/score/recompute only ever saves the *last* of.

Why this exists: calling POST /score/recompute repeatedly against
unchanged signal_snapshot data always recomputes the same latest score and
inserts another identical health_score row - it can never produce a
trend line, because the earlier 1-2 scores in the 3-period trend window
are computed and then discarded. This script reruns that same scoring
math (via the real functions, not a reimplementation) and writes a
health_score row for every trend-window period that isn't already
represented, dated to that period's period_end - so the account-detail
chart and the accounts-table sparkline show the real drift already baked
into the seed data (see WORSENING_INDEXES in generate_seed.py) instead of
a flat line of duplicate "latest" values.

Idempotent: skips any (account, date) pair that already has a health_score
row, so re-running this is a no-op once backfilled.

Run from backend/ (so it picks up backend/.env):
    cd backend && python scripts/backfill_health_history.py
"""

from datetime import datetime, timezone

from app.db import get_supabase_client
from app.services.accounts_repo import fetch_all_accounts, fetch_health_score_history
from app.services.baseline_engine import TRACKED_SIGNALS, compute_baselines, derive_contact_changed, split_baseline_and_trend_windows
from app.services.scoring_engine import compute_composite_risk, compute_trend_slope
from app.services.scoring_repo import fetch_signal_history


def compute_period_scores(history: list[dict]) -> tuple[list[dict], list[float]]:
    """Mirrors score_account_history's own per-period loop (same baseline,
    same per-row composite_risk), just returning every period's score
    instead of only the last."""
    history = derive_contact_changed(history)
    baseline_window, trend_window = split_baseline_and_trend_windows(history)
    baselines = compute_baselines(baseline_window)

    period_scores = []
    for row in trend_window:
        current_signals = {signal: float(row[signal]) for signal in TRACKED_SIGNALS if row.get(signal) is not None}
        score, _ = compute_composite_risk(current_signals, baselines)
        period_scores.append(score)
    return trend_window, period_scores


def backfill_account(client, account_id: str, account_name: str) -> int:
    history = fetch_signal_history(client, account_id)
    if not history:
        return 0

    trend_window, period_scores = compute_period_scores(history)

    existing_dates = {row["computed_at"][:10] for row in fetch_health_score_history(client, account_id)}

    inserted = 0
    for i, (period, score) in enumerate(zip(trend_window, period_scores)):
        computed_at = f"{period['period_end']}T12:00:00+00:00"
        if computed_at[:10] in existing_dates:
            continue  # already have a point for this date - idempotent re-run
        trend_slope = round(compute_trend_slope(period_scores[: i + 1]), 4)
        client.table("health_score").insert(
            {
                "account_id": account_id,
                "computed_at": computed_at,
                "composite_score": score,
                "trend_slope": trend_slope,
            }
        ).execute()
        inserted += 1

    if inserted:
        print(f"  {account_name}: +{inserted} historical point(s) -> {period_scores}")
    return inserted


def main() -> None:
    client = get_supabase_client()
    accounts = fetch_all_accounts(client)
    print(f"Backfilling health_score history for {len(accounts)} accounts...")
    total = 0
    for account in accounts:
        total += backfill_account(client, account["id"], account["name"])
    print(f"Done. Inserted {total} historical health_score row(s) at {datetime.now(timezone.utc).isoformat()}.")


if __name__ == "__main__":
    main()
