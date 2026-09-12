"""Alert inbox endpoints for ClientPulse."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.db import get_supabase_client
from app.schemas import AlertInboxItem, AlertListResponse, AlertStatusUpdate
from app.services.account_alert_repo import (
    account_names_by_id,
    get_account,
    get_alert,
    update_alert_status_if_current,
)
from app.services.account_alert_repo import (
    list_alerts as repo_list_alerts,
)
from supabase import Client  # type: ignore[attr-defined]

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _require_supabase_client() -> Client:
    try:
        return get_supabase_client()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("", response_model=AlertListResponse)
def list_alerts(
    status: Literal["open", "acknowledged", "resolved"] | None = None,
    client: Client = Depends(_require_supabase_client),  # noqa: B008 - FastAPI dependency
) -> AlertListResponse:
    alert_rows = repo_list_alerts(client, status=status)
    account_names = account_names_by_id(client)

    alerts = [
        AlertInboxItem(
            **row, account_name=account_names.get(row["account_id"], "Unknown account")
        )
        for row in sorted(
            alert_rows, key=lambda item: item["triggered_at"], reverse=True
        )
    ]
    return AlertListResponse(total=len(alerts), alerts=alerts)


@router.patch("/{alert_id}", response_model=AlertInboxItem)
def update_alert_status(
    alert_id: UUID,
    update: AlertStatusUpdate,
    client: Client = Depends(_require_supabase_client),  # noqa: B008 - FastAPI dependency
) -> AlertInboxItem:
    alert_key = str(alert_id)
    current = get_alert(client, alert_key)
    if current is None:
        raise HTTPException(status_code=404, detail="alert not found")
    if current["status"] == "resolved" and update.status != "resolved":
        raise HTTPException(
            status_code=409, detail="resolved alerts cannot be reopened"
        )

    if current["status"] == update.status:
        row = current
    else:
        updated = update_alert_status_if_current(
            client,
            alert_key,
            current_status=current["status"],
            new_status=update.status,
        )
        if updated is None:
            raise HTTPException(
                status_code=409, detail="alert status changed concurrently"
            )
        row = updated
    account = get_account(client, row["account_id"])
    account_name = account["name"] if account else "Unknown account"
    return AlertInboxItem(**row, account_name=account_name)
