# Tests for the pure Calendar event -> signal computation (no network, no
# Google API involved).

from app.services.calendar_signals import CalendarEvent, compute_calendar_signals


def test_counts_scheduled_and_cancelled_separately():
    # Two confirmed meetings + one cancelled -> scheduled=2, cancelled=1.
    events = [
        CalendarEvent(status="confirmed", attendee_emails=["client@x.com"]),
        CalendarEvent(status="confirmed", attendee_emails=["client@x.com"]),
        CalendarEvent(status="cancelled", attendee_emails=["client@x.com"]),
    ]

    scheduled, cancelled = compute_calendar_signals(events, "client@x.com")

    assert scheduled == 2
    assert cancelled == 1


def test_ignores_events_without_the_contact_as_attendee():
    # An event where the client contact isn't an attendee shouldn't count
    # toward their signals, even though it's in the fetched event list.
    events = [
        CalendarEvent(status="confirmed", attendee_emails=["someone-else@x.com"]),
        CalendarEvent(status="confirmed", attendee_emails=["client@x.com"]),
    ]

    scheduled, cancelled = compute_calendar_signals(events, "client@x.com")

    assert scheduled == 1
    assert cancelled == 0


def test_matching_is_case_insensitive():
    # Attendee emails from the Calendar API and account.primary_contact_email
    # in Supabase could differ in case — matching should be case-insensitive.
    events = [CalendarEvent(status="confirmed", attendee_emails=["Client@X.com"])]

    scheduled, _ = compute_calendar_signals(events, "client@x.com")

    assert scheduled == 1
