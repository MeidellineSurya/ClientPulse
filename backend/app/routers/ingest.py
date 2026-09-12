from fastapi import APIRouter, Depends, HTTPException, UploadFile
from supabase import Client

from app.db import get_supabase_client
from app.schemas import CsvIngestResult, UnmatchedInvoiceRow
from app.services.csv_ingest import parse_invoice_csv
from app.services.csv_wiring import build_update_plan
from app.services.signal_snapshot_repo import (
    fetch_account_ids_by_email,
    fetch_snapshots_by_account,
    update_invoice_days_late,
)

router = APIRouter(prefix="/ingest", tags=["ingest"])


def _require_supabase_client() -> Client:
    try:
        return get_supabase_client()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/csv", response_model=CsvIngestResult)
async def ingest_csv(
    file: UploadFile,
    client: Client = Depends(_require_supabase_client),
) -> CsvIngestResult:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        result = parse_invoice_csv(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not result.parsed:
        return result

    emails = sorted({row.account_email for row in result.parsed})
    account_id_by_email = fetch_account_ids_by_email(client, emails)
    account_ids = sorted(set(account_id_by_email.values()))
    snapshots_by_account = fetch_snapshots_by_account(client, account_ids)

    updates, unmatched = build_update_plan(result.parsed, account_id_by_email, snapshots_by_account)

    for snapshot_id, days_late in updates.items():
        update_invoice_days_late(client, snapshot_id, days_late)

    result.snapshots_updated = len(updates)
    result.unmatched = [
        UnmatchedInvoiceRow(row_number=u.row_number, account_email=u.account_email, reason=u.reason)
        for u in unmatched
    ]
    return result
