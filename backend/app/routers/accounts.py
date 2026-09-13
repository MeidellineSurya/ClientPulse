"""Read-only account views for the portfolio and account detail pages."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.auth import AuthContext, require_auth_context
from app.schemas import (
    AccountDetail,
    AccountSummary,
    HealthScorePoint,
    SignalSnapshotOut,
)
from app.services.accounts_repo import (
    fetch_account,
    fetch_all_accounts,
    fetch_full_signal_history,
    fetch_health_score_history,
    fetch_latest_health_score,
    fetch_latest_health_scores,
)
from app.services.alerts_repo import fetch_alerts_for_account

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountSummary])
def list_accounts(
    auth: AuthContext = Depends(require_auth_context),  # noqa: B008 - FastAPI dependency
) -> list[AccountSummary]:
    client = auth.client
    accounts = fetch_all_accounts(client, auth.agency_id)
    latest_scores = fetch_latest_health_scores(
        client, [account["id"] for account in accounts]
    )
    return [
        AccountSummary(
            id=account["id"],
            name=account["name"],
            contract_value_monthly=account["contract_value_monthly"],
            composite_score=(latest_scores.get(account["id"]) or {}).get(
                "composite_score"
            ),
            trend_slope=(latest_scores.get(account["id"]) or {}).get("trend_slope"),
            health_computed_at=(latest_scores.get(account["id"]) or {}).get(
                "computed_at"
            ),
        )
        for account in accounts
    ]


@router.get("/{account_id}", response_model=AccountDetail)
def get_account_detail(
    account_id: UUID,
    auth: AuthContext = Depends(require_auth_context),  # noqa: B008 - FastAPI dependency
) -> AccountDetail:
    client = auth.client
    account_key = str(account_id)
    account = fetch_account(client, account_key, auth.agency_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"account {account_key} not found")

    latest_score = fetch_latest_health_score(client, account_key) or {}
    signal_history = fetch_full_signal_history(client, account_key)
    alerts = fetch_alerts_for_account(client, account_key)

    return AccountDetail(
        id=account["id"],
        name=account["name"],
        contract_value_monthly=account["contract_value_monthly"],
        contract_start_date=account["contract_start_date"],
        primary_contact_email=account.get("primary_contact_email"),
        composite_score=latest_score.get("composite_score"),
        trend_slope=latest_score.get("trend_slope"),
        health_computed_at=latest_score.get("computed_at"),
        signal_history=[SignalSnapshotOut(**row) for row in signal_history],
        alerts=alerts,
    )


@router.get("/{account_id}/signals", response_model=list[SignalSnapshotOut])
def get_account_signals(
    account_id: UUID,
    auth: AuthContext = Depends(require_auth_context),  # noqa: B008 - FastAPI dependency
) -> list[SignalSnapshotOut]:
    client = auth.client
    account_key = str(account_id)
    account = fetch_account(client, account_key, auth.agency_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"account {account_key} not found")
    return [
        SignalSnapshotOut(**row)
        for row in fetch_full_signal_history(client, account_key)
    ]


@router.get("/{account_id}/health-history", response_model=list[HealthScorePoint])
def get_account_health_history(
    account_id: UUID,
    auth: AuthContext = Depends(require_auth_context),  # noqa: B008 - FastAPI dependency
) -> list[HealthScorePoint]:
    client = auth.client
    account_key = str(account_id)
    account = fetch_account(client, account_key, auth.agency_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"account {account_key} not found")
    return [
        HealthScorePoint(**row)
        for row in fetch_health_score_history(client, account_key)
    ]
