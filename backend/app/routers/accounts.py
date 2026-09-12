"""GET /accounts and GET /accounts/{id}[/signals]: read-only views over
account + health_score + signal_snapshot + alert for the Portfolio and
Account Detail pages. No writes happen here — /score/recompute (scoring.py)
and /ingest/* (ingest.py) own writing to those tables.
"""

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from app.dependencies import require_supabase_client
from app.schemas import AccountDetail, AccountSummary, SignalSnapshotOut
from app.services.accounts_repo import (
    fetch_account,
    fetch_all_accounts,
    fetch_full_signal_history,
    fetch_latest_health_score,
    fetch_latest_health_scores,
)
from app.services.alerts_repo import fetch_alerts_for_account

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountSummary])
def list_accounts(client: Client = Depends(require_supabase_client)) -> list[AccountSummary]:
    accounts = fetch_all_accounts(client)
    latest_scores = fetch_latest_health_scores(client)
    return [
        AccountSummary(
            id=account["id"],
            name=account["name"],
            contract_value_monthly=account["contract_value_monthly"],
            composite_score=(latest_scores.get(account["id"]) or {}).get("composite_score"),
            trend_slope=(latest_scores.get(account["id"]) or {}).get("trend_slope"),
            health_computed_at=(latest_scores.get(account["id"]) or {}).get("computed_at"),
        )
        for account in accounts
    ]


@router.get("/{account_id}", response_model=AccountDetail)
def get_account_detail(account_id: str, client: Client = Depends(require_supabase_client)) -> AccountDetail:
    account = fetch_account(client, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"account {account_id} not found")

    latest_score = fetch_latest_health_score(client, account_id) or {}
    signal_history = fetch_full_signal_history(client, account_id)
    alerts = fetch_alerts_for_account(client, account_id)

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
    account_id: str, client: Client = Depends(require_supabase_client)
) -> list[SignalSnapshotOut]:
    account = fetch_account(client, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"account {account_id} not found")
    return [SignalSnapshotOut(**row) for row in fetch_full_signal_history(client, account_id)]
