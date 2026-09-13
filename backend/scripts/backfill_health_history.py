"""Backfill a no-lookahead composite-risk curve for each account.

For every period after the minimum baseline plus trend-window history exists,
this script runs the real scoring engine against that point-in-time prefix and
persists the resulting latest score. The account-detail chart and table
sparkline therefore show an actual trajectory rather than three repetitions of
today's score.

Idempotent: skips any (account, date) pair already represented.

Run from backend/ (so it picks up backend/.env):
    cd backend && python scripts/backfill_health_history.py
"""

from datetime import datetime, timezone

from app.config import settings
from app.db import get_supabase_client
from app.services.accounts_repo import fetch_all_accounts, fetch_health_score_history
from app.services.baseline_engine import MIN_BASELINE_SIZE, TREND_WINDOW
from app.services.scoring_engine import compute_trend_slope, score_account_history
from app.services.scoring_repo import fetch_signal_history


def compute_period_scores(history: list[dict]) -> tuple[list[dict], list[float]]:
    """Return a no-lookahead score curve from successive history prefixes.

    The first score is emitted once there are enough rows for both the minimum
    baseline and the three-period trend window. Each later point recomputes the
    real scoring engine using only data available as of that period.
    """
    first_scored_size = MIN_BASELINE_SIZE + TREND_WINDOW
    periods = []
    scores = []
    for prefix_size in range(first_scored_size, len(history) + 1):
        prefix = history[:prefix_size]
        result = score_account_history(prefix)
        periods.append(prefix[-1])
        scores.append(result.composite_score)
    return periods, scores


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
    if not settings.google_agency_id:
        raise SystemExit("GOOGLE_AGENCY_ID is required to scope the backfill")
    client = get_supabase_client()
    accounts = fetch_all_accounts(client, settings.google_agency_id)
    print(f"Backfilling health_score history for {len(accounts)} accounts...")
    total = 0
    for account in accounts:
        total += backfill_account(client, account["id"], account["name"])
    print(f"Done. Inserted {total} historical health_score row(s) at {datetime.now(timezone.utc).isoformat()}.")


if __name__ == "__main__":
    main()
