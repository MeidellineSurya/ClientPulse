"""Read endpoints for ClientPulse accounts."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.db import get_supabase_client
from app.schemas import AccountDetail, AccountListResponse
from app.services.account_alert_repo import (
    get_account as repo_get_account,
)
from app.services.account_alert_repo import (
    list_accounts as repo_list_accounts,
)
from app.services.account_alert_repo import (
    list_active_alerts,
    list_alerts,
    list_health_scores,
    list_signal_snapshots,
)
from supabase import Client  # type: ignore[attr-defined]

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _require_supabase_client() -> Client:
    try:
        return get_supabase_client()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("", response_model=AccountListResponse)
def list_accounts(
    client: Client = Depends(_require_supabase_client),  # noqa: B008 - FastAPI dependency
) -> AccountListResponse:
    account_rows = repo_list_accounts(client)
    score_rows = list_health_scores(client)
    active_alert_rows = list_active_alerts(client)

    latest_scores: dict[str, dict] = {}
    for score in score_rows:
        account_id = score["account_id"]
        if (
            account_id not in latest_scores
            or score["computed_at"] > latest_scores[account_id]["computed_at"]
        ):
            latest_scores[account_id] = score

    active_counts: dict[str, int] = {}
    for alert in active_alert_rows:
        account_id = alert["account_id"]
        active_counts[account_id] = active_counts.get(account_id, 0) + 1

    accounts = []
    for row in sorted(account_rows, key=lambda item: item["name"].casefold()):
        latest = latest_scores.get(row["id"])
        accounts.append(
            {
                **row,
                "latest_composite_score": latest["composite_score"] if latest else None,
                "latest_trend_slope": latest["trend_slope"] if latest else None,
                "latest_score_at": latest["computed_at"] if latest else None,
                "active_alert_count": active_counts.get(row["id"], 0),
            }
        )
    return AccountListResponse(total=len(accounts), accounts=accounts)


@router.get("/{account_id}", response_model=AccountDetail)
def get_account_detail(
    account_id: UUID,
    client: Client = Depends(_require_supabase_client),  # noqa: B008 - FastAPI dependency
) -> AccountDetail:
    account_key = str(account_id)
    account = repo_get_account(client, account_key)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")

    score_rows = list_health_scores(client, account_key)
    signal_rows = list_signal_snapshots(client, account_key)
    alert_rows = list_alerts(client, account_id=account_key)

    scores = sorted(score_rows, key=lambda row: row["computed_at"])
    signals = sorted(signal_rows, key=lambda row: row["period_start"])
    alerts = sorted(alert_rows, key=lambda row: row["triggered_at"], reverse=True)
    latest = scores[-1] if scores else None
    active_alert_count = sum(
        1 for alert in alerts if alert["status"] in {"open", "acknowledged"}
    )

    return AccountDetail.model_validate(
        {
            **account,
            "latest_composite_score": latest["composite_score"] if latest else None,
            "latest_trend_slope": latest["trend_slope"] if latest else None,
            "latest_score_at": latest["computed_at"] if latest else None,
            "active_alert_count": active_alert_count,
            "score_history": scores,
            "signal_history": signals,
            "alerts": alerts,
        }
    )
