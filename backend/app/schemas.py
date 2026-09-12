# Pydantic request/response models for the /ingest/csv endpoint.

from datetime import date

from pydantic import BaseModel


class ParsedInvoiceRow(BaseModel):
    # One successfully parsed & validated row from an uploaded invoice CSV,
    # with invoice_days_late already computed.
    row_number: int
    account_email: str
    invoice_date: date
    due_date: date
    paid_date: date | None
    invoice_days_late: int


class InvoiceRowError(BaseModel):
    # A CSV row that failed parsing/validation (bad dates, missing fields, etc).
    row_number: int
    error: str


class UnmatchedInvoiceRow(BaseModel):
    # A parsed row that couldn't be matched to a seeded account or
    # signal_snapshot period, so nothing was written for it.
    row_number: int
    account_email: str
    reason: str


class CsvIngestResult(BaseModel):
    # Full response for POST /ingest/csv: parsing stats plus, once wired to
    # Supabase, how many signal_snapshot rows were actually updated.
    rows_received: int
    rows_parsed: int
    rows_failed: int
    errors: list[InvoiceRowError]
    parsed: list[ParsedInvoiceRow]
    snapshots_updated: int = 0
    unmatched: list[UnmatchedInvoiceRow] = []


class GmailCalendarIngestResult(BaseModel):
    # Response for POST /ingest/gmail-calendar/{account_id}: the computed
    # signals for that account/period, after they've been written to
    # signal_snapshot.
    account_id: str
    period_start: date
    period_end: date
    avg_response_time_hours: float
    email_thread_count: int
    meetings_scheduled: int
    meetings_cancelled: int


class AccountScoreResult(BaseModel):
    # Response for POST /score/recompute/{account_id}, and one entry per
    # account in POST /score/recompute's batch response.
    account_id: str
    composite_score: float
    trend_slope: float
    alert_fired: bool
    severity: str | None
    signals_fired: list[str]


class RecomputeScoringResponse(BaseModel):
    # Response for POST /score/recompute: how many accounts were scored
    # (accounts with no signal_snapshot history yet are skipped, not
    # errored) and the per-account results.
    accounts_scored: int
    alerts_fired: int
    results: list[AccountScoreResult]
