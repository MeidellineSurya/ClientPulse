# Examples

## `invoice_history_example.csv`

A realistic invoice/payment history export, in the exact format
`POST /ingest/csv` expects — the same file shape an agency would export from
an accounting tool (Xero, QuickBooks, FreshBooks, etc.) and upload from the
Connections page.

**Required columns:** `account_email`, `invoice_date`, `due_date` (dates as
`YYYY-MM-DD`). `paid_date` is optional — leave it blank for an invoice that
hasn't been paid yet.

This example also includes `invoice_number`, `amount_due`, and `currency` —
not required by the importer (it only reads the four columns above and
ignores the rest), but included here to look like a genuine accounting
export rather than a bare minimal fixture.

The 8 rows use real account emails and real, current `signal_snapshot`
periods from the live project as of 2026-09-14, so uploading this file for
real would actually match and update those accounts — it's a working
example, not just an illustration. It's deliberately a realistic mix:

- 4 invoices paid on time (`invoice_days_late` computes to `0`)
- 2 paid a few days late (`5` days)
- 2 still unpaid as of today (`7` days late and counting — `invoice_days_late`
  is computed against today's date when `paid_date` is blank)
