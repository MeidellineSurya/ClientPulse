# POST /ingest/csv: parses an uploaded invoice CSV, matches each row to a
# seeded account + weekly signal_snapshot period, and writes invoice_days_late.
#
# POST /ingest/gmail-calendar/{account_id}: pulls metadata-only Gmail headers
# plus read-only Calendar events for one account's contact, computes the
# behavioural signals, and upserts the requested signal_snapshot period.

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from google.auth.exceptions import GoogleAuthError
from googleapiclient.errors import HttpError
from httplib2 import HttpLib2Error

from app.auth import AuthContext, require_auth_context
from app.google_client import (
    GoogleIntegrationNotFound,
    get_calendar_service,
    get_gmail_service,
    get_google_credentials,
)
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


@router.post("/csv", response_model=CsvIngestResult)
async def ingest_csv(
    file: UploadFile,
    auth: AuthContext = Depends(require_auth_context),  # noqa: B008 - FastAPI dependency
) -> CsvIngestResult:
    client = auth.client
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
    account_id_by_email = fetch_account_ids_by_email(client, emails, auth.agency_id)
    account_ids = sorted(set(account_id_by_email.values()))
    snapshots_by_account = fetch_snapshots_by_account(client, account_ids)

    # Pure matching logic: which signal_snapshot row should each invoice's
    # lateness be written to, and which rows have no match.
    updates, unmatched = build_update_plan(
        result.parsed, account_id_by_email, snapshots_by_account
    )

    # Apply the writes.
    for snapshot_id, days_late in updates.items():
        update_invoice_days_late(client, snapshot_id, days_late)

    result.snapshots_updated = len(updates)
    result.unmatched = [
        UnmatchedInvoiceRow(
            row_number=u.row_number, account_email=u.account_email, reason=u.reason
        )
        for u in unmatched
    ]
    return result


@router.post("/gmail-calendar/{account_id}", response_model=GmailCalendarIngestResult)
async def ingest_gmail_calendar(
    account_id: UUID,
    period_start: date | None = None,
    period_end: date | None = None,
    auth: AuthContext = Depends(require_auth_context),  # noqa: B008 - FastAPI dependency
) -> GmailCalendarIngestResult:
    client = auth.client
    account_key = str(account_id)
    if (period_start is None) != (period_end is None):
        raise HTTPException(
            status_code=422,
            detail="period_start and period_end must be provided together",
        )

    # Defaults to the current Mon-Sun week when neither bound is given, so this
    # can be called on a schedule without callers tracking dates themselves.
    if period_start is None and period_end is None:
        period_start, period_end = current_week_period()
    assert period_start is not None and period_end is not None
    if period_end < period_start:
        raise HTTPException(
            status_code=422, detail="period_end must not be before period_start"
        )

    contact_email = fetch_account_email(client, account_key, auth.agency_id)
    if contact_email is None:
        raise HTTPException(status_code=404, detail="account not found")

    try:
        credentials = get_google_credentials(auth.agency_id)
        gmail_service = get_gmail_service(credentials)
        calendar_service = get_calendar_service(credentials)
        messages = fetch_message_metadata(
            gmail_service, contact_email, period_start, period_end
        )
        events = fetch_events(calendar_service, contact_email, period_start, period_end)
    except GoogleIntegrationNotFound as exc:
        raise HTTPException(
            status_code=404, detail="Google integration not found"
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GoogleAuthError as exc:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth credentials could not be refreshed",
        ) from exc
    except (HttpError, HttpLib2Error) as exc:
        raise HTTPException(
            status_code=502,
            detail="Google Gmail/Calendar request failed",
        ) from exc

    avg_response_time_hours = compute_email_signals(messages, contact_email)
    meetings_scheduled, meetings_cancelled = compute_calendar_signals(
        events, contact_email
    )

    upsert_gmail_calendar_signals(
        client,
        account_key,
        period_start.isoformat(),
        period_end.isoformat(),
        avg_response_time_hours,
        meetings_scheduled,
        meetings_cancelled,
        primary_contact_email=contact_email,
    )

    return GmailCalendarIngestResult(
        account_id=account_key,
        period_start=period_start,
        period_end=period_end,
        avg_response_time_hours=avg_response_time_hours,
        meetings_scheduled=meetings_scheduled,
        meetings_cancelled=meetings_cancelled,
    )
