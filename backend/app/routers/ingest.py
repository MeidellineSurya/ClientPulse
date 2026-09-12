# POST /ingest/csv: parses an uploaded invoice CSV, matches each row to a
# seeded account + weekly signal_snapshot period, and writes invoice_days_late.
#
# POST /ingest/gmail-calendar/{account_id}: pulls Gmail metadata + Calendar
# events for one account's contact and writes the remaining signal_snapshot
# columns. Stretch goal — see app/google_client.py for the scaffold caveat.

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from supabase import Client

from app.db import get_supabase_client
from app.google_client import get_calendar_service, get_gmail_service, get_google_credentials
from app.schemas import CsvIngestResult, GmailCalendarIngestResult, UnmatchedInvoiceRow
from app.services.calendar_signals import compute_calendar_signals, fetch_events
from app.services.csv_ingest import parse_invoice_csv
from app.services.csv_wiring import build_update_plan
from app.services.gmail_signals import compute_email_signals, fetch_message_metadata
from app.services.period_utils import current_week_period
from app.services.signal_snapshot_repo import (
    fetch_account_email,
    fetch_account_ids_by_email,
    fetch_snapshots_by_account,
    update_invoice_days_late,
    upsert_gmail_calendar_signals,
)

router = APIRouter(prefix="/ingest", tags=["ingest"])


def _require_supabase_client() -> Client:
    # Wraps get_supabase_client() so a missing SUPABASE_* config surfaces as
    # a clean 503 instead of an unhandled 500.
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

    # Parse + validate the CSV; bad rows are collected as errors rather than
    # failing the whole upload (see app/services/csv_ingest.py).
    try:
        result = parse_invoice_csv(raw)
    except ValueError as exc:
        # Only structural problems (missing header/columns, bad encoding)
        # raise here — per-row issues are already in result.errors.
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not result.parsed:
        # Nothing valid to wire up (e.g. every row failed validation).
        return result

    # Look up which of the emails in this CSV correspond to real seeded
    # accounts, and fetch those accounts' signal_snapshot periods.
    emails = sorted({row.account_email for row in result.parsed})
    account_id_by_email = fetch_account_ids_by_email(client, emails)
    account_ids = sorted(set(account_id_by_email.values()))
    snapshots_by_account = fetch_snapshots_by_account(client, account_ids)

    # Pure matching logic: which signal_snapshot row should each invoice's
    # lateness be written to, and which rows have no match.
    updates, unmatched = build_update_plan(result.parsed, account_id_by_email, snapshots_by_account)

    # Apply the writes.
    for snapshot_id, days_late in updates.items():
        update_invoice_days_late(client, snapshot_id, days_late)

    result.snapshots_updated = len(updates)
    result.unmatched = [
        UnmatchedInvoiceRow(row_number=u.row_number, account_email=u.account_email, reason=u.reason)
        for u in unmatched
    ]
    return result


@router.post("/gmail-calendar/{account_id}", response_model=GmailCalendarIngestResult)
async def ingest_gmail_calendar(
    account_id: str,
    period_start: date | None = None,
    period_end: date | None = None,
    client: Client = Depends(_require_supabase_client),
) -> GmailCalendarIngestResult:
    # Defaults to the current Mon-Sun week if no period is given, so this
    # can be called on a schedule without callers tracking dates themselves.
    if period_start is None or period_end is None:
        period_start, period_end = current_week_period()

    contact_email = fetch_account_email(client, account_id)
    if contact_email is None:
        raise HTTPException(status_code=404, detail="account not found")

    try:
        credentials = get_google_credentials()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    gmail_service = get_gmail_service(credentials)
    calendar_service = get_calendar_service(credentials)

    messages = fetch_message_metadata(gmail_service, contact_email, period_start, period_end)
    avg_response_time_hours, email_thread_count = compute_email_signals(messages, contact_email)

    events = fetch_events(calendar_service, contact_email, period_start, period_end)
    meetings_scheduled, meetings_cancelled = compute_calendar_signals(events, contact_email)

    upsert_gmail_calendar_signals(
        client,
        account_id,
        period_start.isoformat(),
        period_end.isoformat(),
        avg_response_time_hours,
        email_thread_count,
        meetings_scheduled,
        meetings_cancelled,
    )

    return GmailCalendarIngestResult(
        account_id=account_id,
        period_start=period_start,
        period_end=period_end,
        avg_response_time_hours=avg_response_time_hours,
        email_thread_count=email_thread_count,
        meetings_scheduled=meetings_scheduled,
        meetings_cancelled=meetings_cancelled,
    )
