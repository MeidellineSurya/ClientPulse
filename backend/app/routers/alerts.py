"""Read and safely update the portfolio alert inbox."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from app.auth import AuthContext, require_auth_context
from app.schemas import AlertOut, UpdateAlertStatusRequest
from app.services.alerts_repo import (
    fetch_account_name,
    fetch_alert,
    fetch_all_alerts,
    update_alert_status_if_current,
)

router = APIRouter(prefix="/alerts", tags=["alerts"])
AlertStatus = Literal["open", "acknowledged", "resolved"]


@router.get("", response_model=list[AlertOut])
def list_alerts(
    status: AlertStatus | None = None,
    auth: AuthContext = Depends(require_auth_context),  # noqa: B008 - FastAPI dependency
) -> list[AlertOut]:
    client = auth.client
    return [
        AlertOut(**row)
        for row in fetch_all_alerts(client, auth.agency_id, status=status)
    ]


def _transition_alert_status(
    alert_id: UUID,
    body: UpdateAlertStatusRequest,
    client: Client,
    agency_id: str,
) -> AlertOut:
    alert_key = str(alert_id)
    existing = fetch_alert(client, alert_key, agency_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"alert {alert_key} not found")
    if existing["status"] == "resolved" and body.status != "resolved":
        raise HTTPException(
            status_code=409, detail="resolved alerts cannot be reopened"
        )
    status_rank = {"open": 0, "acknowledged": 1, "resolved": 2}
    if status_rank[body.status] < status_rank[existing["status"]]:
        raise HTTPException(
            status_code=409, detail="alert status cannot move backwards"
        )
    account_name = fetch_account_name(client, existing["account_id"], agency_id)
    if existing["status"] == body.status:
        return AlertOut(**existing, account_name=account_name)

    updated = update_alert_status_if_current(
        client,
        alert_key,
        account_id=existing["account_id"],
        current_status=existing["status"],
        new_status=body.status,
    )
    if updated is None:
        raise HTTPException(status_code=409, detail="alert status changed concurrently")
    return AlertOut(**updated, account_name=account_name)


@router.post("/{alert_id}/status", response_model=AlertOut)
def set_alert_status(
    alert_id: UUID,
    body: UpdateAlertStatusRequest,
    auth: AuthContext = Depends(require_auth_context),  # noqa: B008 - FastAPI dependency
) -> AlertOut:
    return _transition_alert_status(alert_id, body, auth.client, auth.agency_id)


@router.patch("/{alert_id}", response_model=AlertOut)
def patch_alert_status(
    alert_id: UUID,
    body: UpdateAlertStatusRequest,
    auth: AuthContext = Depends(require_auth_context),  # noqa: B008 - FastAPI dependency
) -> AlertOut:
    return _transition_alert_status(alert_id, body, auth.client, auth.agency_id)
