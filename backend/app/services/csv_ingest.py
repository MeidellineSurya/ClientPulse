"""Parses invoice/payment CSVs into signal_snapshot.invoice_days_late values.

Expected columns (header row required): account_email, invoice_date,
due_date, paid_date. Dates are ISO format (YYYY-MM-DD). paid_date may be
blank for an invoice that hasn't been paid yet.

Matching parsed rows against seeded accounts/periods and writing to
Supabase happens in the ingest router, not here — this module only parses
and computes invoice_days_late.
"""

import csv
import io
from datetime import date

from app.schemas import CsvIngestResult, InvoiceRowError, ParsedInvoiceRow

REQUIRED_COLUMNS = {"account_email", "invoice_date", "due_date"}


def compute_days_late(due_date: date, paid_date: date | None, as_of: date) -> int:
    """Days between due_date and paid_date, or due_date and as_of if still unpaid.

    Never negative — paying early or on time is 0 days late, not a negative number.
    """
    reference = paid_date if paid_date is not None else as_of
    return max(0, (reference - due_date).days)


def _parse_date(value: str, field: str) -> date:
    value = value.strip()
    if not value:
        raise ValueError(f"{field} is required")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO date (YYYY-MM-DD), got {value!r}") from exc


def parse_invoice_csv(raw: bytes, as_of: date | None = None) -> CsvIngestResult:
    as_of = as_of or date.today()

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV file must be UTF-8 encoded") from exc

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV file has no header row")

    headers = {name.strip().lower() for name in reader.fieldnames}
    missing = REQUIRED_COLUMNS - headers
    if missing:
        raise ValueError(f"CSV is missing required column(s): {', '.join(sorted(missing))}")

    parsed: list[ParsedInvoiceRow] = []
    errors: list[InvoiceRowError] = []
    rows_received = 0

    for row_number, row in enumerate(reader, start=2):  # header is row 1
        rows_received += 1
        normalized = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        try:
            account_email = normalized.get("account_email", "")
            if not account_email:
                raise ValueError("account_email is required")

            invoice_date = _parse_date(normalized.get("invoice_date", ""), "invoice_date")
            due_date = _parse_date(normalized.get("due_date", ""), "due_date")

            paid_raw = normalized.get("paid_date", "")
            paid_date = _parse_date(paid_raw, "paid_date") if paid_raw else None

            if due_date < invoice_date:
                raise ValueError("due_date cannot be before invoice_date")
            if paid_date is not None and paid_date < invoice_date:
                raise ValueError("paid_date cannot be before invoice_date")

            days_late = compute_days_late(due_date, paid_date, as_of)

            parsed.append(
                ParsedInvoiceRow(
                    row_number=row_number,
                    account_email=account_email,
                    invoice_date=invoice_date,
                    due_date=due_date,
                    paid_date=paid_date,
                    invoice_days_late=days_late,
                )
            )
        except ValueError as exc:
            errors.append(InvoiceRowError(row_number=row_number, error=str(exc)))

    return CsvIngestResult(
        rows_received=rows_received,
        rows_parsed=len(parsed),
        rows_failed=len(errors),
        errors=errors,
        parsed=parsed,
    )
