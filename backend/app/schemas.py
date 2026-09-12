from datetime import date

from pydantic import BaseModel


class ParsedInvoiceRow(BaseModel):
    row_number: int
    account_email: str
    invoice_date: date
    due_date: date
    paid_date: date | None
    invoice_days_late: int


class InvoiceRowError(BaseModel):
    row_number: int
    error: str


class CsvIngestResult(BaseModel):
    rows_received: int
    rows_parsed: int
    rows_failed: int
    errors: list[InvoiceRowError]
    parsed: list[ParsedInvoiceRow]
