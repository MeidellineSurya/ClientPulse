"""GET /alerts and POST /alerts/{id}/status: the alerts inbox — read every
alert across the portfolio, and let an account manager change one's status
(open/acknowledged/resolved). Alerts themselves are only ever *created* by
the scoring engine (scoring_repo.upsert_alert) — this router only reads and
updates status.
"""

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from app.dependencies import require_supabase_client
from app.schemas import AlertOut, UpdateAlertStatusRequest
from app.services.alerts_repo import fetch_alert, fetch_all_alerts, update_alert_status

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
def list_alerts(client: Client = Depends(require_supabase_client)) -> list[AlertOut]:
    return fetch_all_alerts(client)


@router.post("/{alert_id}/status", response_model=AlertOut)
def set_alert_status(
    alert_id: str, body: UpdateAlertStatusRequest, client: Client = Depends(require_supabase_client)
) -> AlertOut:
    existing = fetch_alert(client, alert_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"alert {alert_id} not found")
    updated = update_alert_status(client, alert_id, body.status)
    return AlertOut(**updated)
