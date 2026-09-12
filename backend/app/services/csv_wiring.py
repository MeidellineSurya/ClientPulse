"""Matches parsed invoice rows to seeded accounts/periods (pure logic,
no I/O) so it's testable without a database."""

from dataclasses import dataclass
from datetime import date

from app.schemas import ParsedInvoiceRow


@dataclass
class UnmatchedRow:
    # A parsed row build_update_plan couldn't resolve to a signal_snapshot
    # write, plus why (surfaced back to the API caller).
    row_number: int
    account_email: str
    reason: str


def build_update_plan(
    parsed_rows: list[ParsedInvoiceRow],
    account_id_by_email: dict[str, str],
    snapshots_by_account: dict[str, list[dict]],
) -> tuple[dict[str, int], list[UnmatchedRow]]:
    """Returns (snapshot_id -> invoice_days_late to write, unmatched rows).

    Matches on due_date falling within a signal_snapshot's [period_start,
    period_end] window for that account. When multiple invoices land in the
    same period, the highest invoice_days_late wins — the worst lateness in
    a week is the more useful churn signal than whichever row came last.
    """
    updates: dict[str, int] = {}
    unmatched: list[UnmatchedRow] = []

    for row in parsed_rows:
        # Step 1: resolve the CSV's account_email to a seeded account_id.
        account_id = account_id_by_email.get(row.account_email)
        if account_id is None:
            unmatched.append(UnmatchedRow(row.row_number, row.account_email, "no account with this email"))
            continue

        # Step 2: find which of that account's weekly periods this
        # invoice's due_date falls into.
        snapshot_id = None
        for snap in snapshots_by_account.get(account_id, []):
            period_start = date.fromisoformat(str(snap["period_start"]))
            period_end = date.fromisoformat(str(snap["period_end"]))
            if period_start <= row.due_date <= period_end:
                snapshot_id = snap["id"]
                break

        if snapshot_id is None:
            unmatched.append(
                UnmatchedRow(row.row_number, row.account_email, "no signal_snapshot period covers due_date")
            )
            continue

        # Step 3: record the write, keeping the worst (max) lateness if more
        # than one invoice lands in the same period.
        updates[snapshot_id] = max(updates.get(snapshot_id, 0), row.invoice_days_late)

    return updates, unmatched
