# Pydantic request/response models for the /ingest/csv endpoint.

from datetime import date, datetime
from typing import Literal

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
    # What % of composite_score each signal is responsible for, e.g.
    # {"avg_response_time_hours": 68.2, ...} — an inspectable breakdown of
    # the score, not just the score itself. Always present, even when no
    # alert fired (useful for the account-detail view either way).
    signal_contributions: dict[str, float]
    # Annualized contract value weighted by composite_score — the dollar
    # figure behind the pitch's money case, not just the abstract score.
    revenue_at_risk: float


class RecomputeScoringResponse(BaseModel):
    # Response for POST /score/recompute: how many accounts were scored
    # (accounts with no signal_snapshot history yet are skipped, not
    # errored), the per-account results, and the portfolio-wide total —
    # feeds the Portfolio page's "total at-risk revenue" summary bar.
    # total_revenue_at_risk only sums accounts where alert_fired=True
    # (a crisp "$X across the accounts we've flagged"), not every account's
    # proportional exposure — see scoring.py's recompute_all_scores.
    accounts_scored: int
    alerts_fired: int
    total_revenue_at_risk: float
    results: list[AccountScoreResult]
    # Accounts skipped because scoring raised (e.g. malformed
    # signal_snapshot data) rather than because they had no history yet —
    # isolated per-account so one bad account can't 500 the whole batch.
    failed_account_ids: list[str] = []


class AlertOut(BaseModel):
    # One alert row. account_name is joined in for display (see
    # app/services/alerts_repo.py) — None on the account-detail endpoint's
    # nested alerts, where the caller already has the account in hand.
    id: str
    account_id: str
    account_name: str | None = None
    triggered_at: datetime
    signals_fired: list[str]
    severity: str
    ai_brief: str | None
    suggested_action: str | None
    status: str


class UpdateAlertStatusRequest(BaseModel):
    # Body for POST /alerts/{id}/status. Literal mirrors schema.sql's
    # alert.status CHECK constraint, so an invalid value 422s automatically
    # instead of reaching the database.
    status: Literal["open", "acknowledged", "resolved"]


class HealthScorePoint(BaseModel):
    # One historical health_score row, for the account-detail page's
    # composite-score-over-time chart.
    composite_score: float
    trend_slope: float
    computed_at: datetime


class AccountSummary(BaseModel):
    # One row of GET /accounts — the portfolio table. composite_score/
    # trend_slope/health_computed_at are None for an account that hasn't
    # been scored yet (no health_score row written for it).
    id: str
    name: str
    contract_value_monthly: float
    composite_score: float | None
    trend_slope: float | None
    health_computed_at: datetime | None


class SignalSnapshotOut(BaseModel):
    # One signal_snapshot row, for chart data (GET /accounts/{id}/signals
    # and the signal_history list on GET /accounts/{id}).
    period_start: date
    period_end: date
    avg_response_time_hours: float
    meetings_scheduled: int
    meetings_cancelled: int
    invoice_days_late: int
    email_thread_count: int
    # Raw per-period contact email — not shown directly, but AccountDetail's
    # contact_changed_at/previous_contact_email (below) are derived from this
    # across the list. See baseline_engine.derive_contact_changed.
    primary_contact_email: str | None = None


class AccountDetail(BaseModel):
    # GET /accounts/{id}: account info + latest score + full signal history
    # + this account's alerts, in one response.
    id: str
    name: str
    contract_value_monthly: float
    contract_start_date: date
    primary_contact_email: str | None
    composite_score: float | None
    trend_slope: float | None
    health_computed_at: datetime | None
    signal_history: list[SignalSnapshotOut]
    alerts: list[AlertOut]
    # Most recent point-of-contact change detected in signal_history, if
    # any — see HANDOFF.md §13 and baseline_engine.derive_contact_changed.
    # None whenever this account has never had a detected contact change.
    contact_changed_at: date | None = None
    previous_contact_email: str | None = None
