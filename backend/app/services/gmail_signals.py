"""Pulls Gmail metadata for a client contact and computes
avg_response_time_hours for a signal_snapshot period.

Only ever requests format="metadata" with an explicit header allowlist —
never "full" or "raw" — so message bodies are never read, even transiently,
per the product's stated privacy commitment. Enforced structurally at the
OAuth scope level too (see GMAIL_METADATA_SCOPE in app/google_client.py).

The metadata fetcher uses the production Gmail API shape and deliberately
filters headers locally because Gmail forbids its server-side `q` parameter
under the metadata-only scope. fetch_message_metadata is the only function
that talks to Google; compute_email_signals remains pure.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from email.utils import getaddresses, parsedate_to_datetime

from googleapiclient.discovery import Resource

# Gmail's users.messages.list, with no query, returns messages newest-first
# by internal date. Once a listed message's Date header falls before the
# requested period, every message after it (further back in time) is out of
# range too, so the scan can stop there instead of walking the rest of the
# mailbox's history.
#
# MAX_MESSAGES_SCANNED is a hard backstop, not the expected case: it caps
# total work even if that ordering assumption is ever wrong (or a contact
# genuinely has no messages at all in a very large mailbox), so a single
# recompute call can never turn into an unbounded crawl of someone's entire
# email history — only gmail.metadata (headers), never message bodies, but
# still real inbox metadata that a period-scoped signal has no business
# touching wholesale.
MAX_MESSAGES_SCANNED = 500


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
    period_min = datetime.combine(period_start, time.min, tzinfo=UTC)
    period_max = datetime.combine(period_end + timedelta(days=1), time.min, tzinfo=UTC)
    target_email = contact_email.casefold()

    messages: list[MessageMetadata] = []
    page_token = None
    scanned = 0
    while True:
        # gmail.metadata deliberately forbids the Gmail `q` parameter, so
        # there's no server-side way to date-bound this list call — see the
        # module-level comment for how the loop bounds itself instead.
        list_resp = (
            service.users()
            .messages()
            .list(
                userId="me",
                pageToken=page_token,
                maxResults=100,
                includeSpamTrash=False,
            )
            .execute()
        )
        for item in list_resp.get("messages", []):
            scanned += 1
            if scanned > MAX_MESSAGES_SCANNED:
                return messages
            detail = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=item["id"],
                    format="metadata",
                    metadataHeaders=["From", "To", "Date"],
                )
                .execute()
            )
            headers = {
                h["name"].casefold(): h["value"]
                for h in detail.get("payload", {}).get("headers", [])
            }
            raw_date = headers.get("date")
            if not raw_date:
                continue
            try:
                sent_at = parsedate_to_datetime(raw_date)
            except (TypeError, ValueError):
                continue
            if sent_at.tzinfo is None:
                sent_at = sent_at.replace(tzinfo=UTC)
            sent_at = sent_at.astimezone(UTC)
            if sent_at < period_min:
                # Newest-first ordering means everything from here on is
                # even older than this — nothing further back can still be
                # inside [period_min, period_max).
                return messages
            addresses = {
                address.casefold()
                for _, address in getaddresses(
                    [headers.get("from", ""), headers.get("to", "")]
                )
            }
            if target_email not in addresses or sent_at >= period_max:
                continue
            messages.append(
                MessageMetadata(
                    message_id=detail["id"],
                    thread_id=detail["threadId"],
                    from_addr=headers.get("from", ""),
                    to_addr=headers.get("to", ""),
                    date=sent_at,
                )
            )
        page_token = list_resp.get("nextPageToken")
        if not page_token:
            break
    return messages


def compute_email_signals(
    messages: list[MessageMetadata], contact_email: str
) -> float:
    """Returns avg_response_time_hours.

    Response time is measured as the gap between an inbound message from
    contact_email and the next outbound message to them in the same
    thread (the agency's reply). Threads with no inbound->outbound pair
    don't contribute a response time sample.
    """
    contact_email = contact_email.casefold()

    by_thread: dict[str, list[MessageMetadata]] = {}
    for m in messages:
        by_thread.setdefault(m.thread_id, []).append(m)

    response_hours: list[float] = []
    for thread_messages in by_thread.values():
        thread_messages.sort(key=lambda m: m.date)
        pending_inbound_at = None
        for m in thread_messages:
            sender_addresses = {
                address.casefold() for _, address in getaddresses([m.from_addr])
            }
            is_inbound = contact_email in sender_addresses
            if is_inbound:
                # A new inbound message resets the clock — we only measure
                # the reply to the most recent thing the contact sent.
                pending_inbound_at = m.date
            elif pending_inbound_at is not None:
                delta_hours = (m.date - pending_inbound_at).total_seconds() / 3600
                response_hours.append(delta_hours)
                pending_inbound_at = None

    avg_response_time_hours = (
        sum(response_hours) / len(response_hours) if response_hours else 0.0
    )
    return round(avg_response_time_hours, 2)
