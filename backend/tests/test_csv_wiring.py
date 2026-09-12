from datetime import date

from app.schemas import ParsedInvoiceRow
from app.services.csv_wiring import build_update_plan


def make_row(row_number, email, due_date, days_late) -> ParsedInvoiceRow:
    return ParsedInvoiceRow(
        row_number=row_number,
        account_email=email,
        invoice_date=due_date,
        due_date=due_date,
        paid_date=None,
        invoice_days_late=days_late,
    )


def test_matches_row_to_account_and_period():
    rows = [make_row(2, "a@x.com", date(2026, 8, 5), 3)]
    accounts = {"a@x.com": "acc-1"}
    snapshots = {
        "acc-1": [
            {"id": "snap-1", "period_start": "2026-08-01", "period_end": "2026-08-07"},
        ]
    }

    updates, unmatched = build_update_plan(rows, accounts, snapshots)

    assert updates == {"snap-1": 3}
    assert unmatched == []


def test_unmatched_when_account_email_unknown():
    rows = [make_row(2, "ghost@x.com", date(2026, 8, 5), 3)]

    updates, unmatched = build_update_plan(rows, {}, {})

    assert updates == {}
    assert len(unmatched) == 1
    assert unmatched[0].reason == "no account with this email"


def test_unmatched_when_due_date_outside_all_periods():
    rows = [make_row(2, "a@x.com", date(2026, 12, 25), 3)]
    accounts = {"a@x.com": "acc-1"}
    snapshots = {
        "acc-1": [
            {"id": "snap-1", "period_start": "2026-08-01", "period_end": "2026-08-07"},
        ]
    }

    updates, unmatched = build_update_plan(rows, accounts, snapshots)

    assert updates == {}
    assert unmatched[0].reason == "no signal_snapshot period covers due_date"


def test_multiple_invoices_same_period_take_max_lateness():
    rows = [
        make_row(2, "a@x.com", date(2026, 8, 5), 3),
        make_row(3, "a@x.com", date(2026, 8, 6), 9),
        make_row(4, "a@x.com", date(2026, 8, 7), 1),
    ]
    accounts = {"a@x.com": "acc-1"}
    snapshots = {
        "acc-1": [
            {"id": "snap-1", "period_start": "2026-08-01", "period_end": "2026-08-07"},
        ]
    }

    updates, unmatched = build_update_plan(rows, accounts, snapshots)

    assert updates == {"snap-1": 9}
    assert unmatched == []
