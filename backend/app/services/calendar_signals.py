"""Pulls Calendar events for a client contact and computes
meetings_scheduled / meetings_cancelled for a signal_snapshot period.

Scaffold only: written against the real Calendar API shape but not
exercised against a live calendar in this environment (no OAuth
credentials available here). fetch_events is the only function that talks
to Google; compute_calendar_signals is pure and unit-tested independently.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from googleapiclient.discovery import Resource


@dataclass
class CalendarEvent:
    status: str
    attendee_emails: list[str] = field(default_factory=list)


def fetch_events(service: Resource, contact_email: str, period_start: date, period_end: date) -> list[CalendarEvent]:
    time_min = datetime.combine(period_start, datetime.min.time()).isoformat() + "Z"
    # +1 day so the window fully includes period_end.
    time_max = datetime.combine(period_end + timedelta(days=1), datetime.min.time()).isoformat() + "Z"

    events: list[CalendarEvent] = []
    page_token = None
    while True:
        resp = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                q=contact_email,
                singleEvents=True,
                # showDeleted so cancelled instances are included (needed
                # to count meetings_cancelled, not just meetings_scheduled).
                showDeleted=True,
                pageToken=page_token,
            )
            .execute()
        )
        for item in resp.get("items", []):
            attendees = [a.get("email", "") for a in item.get("attendees", [])]
            events.append(CalendarEvent(status=item.get("status", "confirmed"), attendee_emails=attendees))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return events


def compute_calendar_signals(events: list[CalendarEvent], contact_email: str) -> tuple[int, int]:
    """Returns (meetings_scheduled, meetings_cancelled) for events that
    include contact_email as an attendee."""
    contact_email = contact_email.lower()
    relevant = [e for e in events if any(a.lower() == contact_email for a in e.attendee_emails)]

    cancelled = sum(1 for e in relevant if e.status == "cancelled")
    scheduled = sum(1 for e in relevant if e.status != "cancelled")
    return scheduled, cancelled
