"""Pulls Gmail metadata for a client contact and computes
avg_response_time_hours / email_thread_count for a signal_snapshot period.

Only ever requests format="metadata" with an explicit header allowlist —
never "full" or "raw" — so message bodies are never read, even transiently,
per the product's stated privacy commitment. Enforced structurally at the
OAuth scope level too (see GMAIL_METADATA_SCOPE in app/google_client.py).

Scaffold only: written against the real Gmail API shape but not exercised
against a live mailbox in this environment (no OAuth credentials available
here). fetch_message_metadata is the only function that talks to Google;
compute_email_signals is pure and unit-tested independently.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime

from googleapiclient.discovery import Resource


@dataclass
class MessageMetadata:
    message_id: str
    thread_id: str
    from_addr: str
    to_addr: str
    date: datetime


def fetch_message_metadata(
    service: Resource, contact_email: str, period_start: date, period_end: date
) -> list[MessageMetadata]:
    # Gmail search "before:" is exclusive, so add a day to include all of period_end.
    query = (
        f"(to:{contact_email} OR from:{contact_email}) "
        f"after:{period_start.strftime('%Y/%m/%d')} "
        f"before:{(period_end + timedelta(days=1)).strftime('%Y/%m/%d')}"
    )

    messages: list[MessageMetadata] = []
    page_token = None
    while True:
        list_resp = service.users().messages().list(userId="me", q=query, pageToken=page_token).execute()
        for item in list_resp.get("messages", []):
            detail = (
                service.users()
                .messages()
                .get(userId="me", id=item["id"], format="metadata", metadataHeaders=["From", "To", "Date"])
                .execute()
            )
            headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
            messages.append(
                MessageMetadata(
                    message_id=detail["id"],
                    thread_id=detail["threadId"],
                    from_addr=headers.get("From", ""),
                    to_addr=headers.get("To", ""),
                    date=parsedate_to_datetime(headers["Date"]),
                )
            )
        page_token = list_resp.get("nextPageToken")
        if not page_token:
            break
    return messages


def compute_email_signals(messages: list[MessageMetadata], contact_email: str) -> tuple[float, int]:
    """Returns (avg_response_time_hours, email_thread_count).

    Response time is measured as the gap between an inbound message from
    contact_email and the next outbound message to them in the same
    thread (the agency's reply). Threads with no inbound->outbound pair
    still count toward email_thread_count but don't contribute a response
    time sample.
    """
    contact_email = contact_email.lower()

    by_thread: dict[str, list[MessageMetadata]] = {}
    for m in messages:
        by_thread.setdefault(m.thread_id, []).append(m)

    response_hours: list[float] = []
    for thread_messages in by_thread.values():
        thread_messages.sort(key=lambda m: m.date)
        pending_inbound_at = None
        for m in thread_messages:
            is_inbound = contact_email in m.from_addr.lower()
            if is_inbound:
                # A new inbound message resets the clock — we only measure
                # the reply to the most recent thing the contact sent.
                pending_inbound_at = m.date
            elif pending_inbound_at is not None:
                delta_hours = (m.date - pending_inbound_at).total_seconds() / 3600
                response_hours.append(delta_hours)
                pending_inbound_at = None

    avg_response_time_hours = sum(response_hours) / len(response_hours) if response_hours else 0.0
    return round(avg_response_time_hours, 2), len(by_thread)
