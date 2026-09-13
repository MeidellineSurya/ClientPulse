# Tests for the pure Gmail metadata -> signal computation (no network,
# no Google API involved), plus fetch_message_metadata's bounding of how
# much of a real mailbox it's willing to scan.

from datetime import UTC, date, datetime

from app.services.gmail_signals import (
    MAX_MESSAGES_SCANNED,
    MessageMetadata,
    compute_email_signals,
    fetch_message_metadata,
)


class _FakeExecutable:
    def __init__(self, response):
        self._response = response

    def execute(self):
        return self._response


class _FakeMessagesResource:
    """Fakes service.users().messages().list()/.get() — records every id
    fetch_message_metadata calls .get() on, so tests can assert it stopped
    early instead of walking the whole fake mailbox."""

    def __init__(self, message_ids: list[str], details_by_id: dict[str, dict]):
        # message_ids is newest-first, matching real Gmail list() ordering.
        self._message_ids = message_ids
        self._details_by_id = details_by_id
        self.get_calls: list[str] = []

    def list(self, **_kwargs):
        return _FakeExecutable({"messages": [{"id": i} for i in self._message_ids]})

    def get(self, id, **_kwargs):  # noqa: A002 - matches the real API's kwarg name
        self.get_calls.append(id)
        return _FakeExecutable(self._details_by_id[id])


class _FakeService:
    def __init__(self, messages_resource: _FakeMessagesResource):
        self._messages_resource = messages_resource

    def users(self):
        return self

    def messages(self):
        return self._messages_resource


def _detail(message_id: str, thread_id: str, rfc2822_date: str, from_addr: str, to_addr: str) -> dict:
    return {
        "id": message_id,
        "threadId": thread_id,
        "payload": {
            "headers": [
                {"name": "From", "value": from_addr},
                {"name": "To", "value": to_addr},
                {"name": "Date", "value": rfc2822_date},
            ]
        },
    }


def test_fetch_message_metadata_stops_once_it_walks_past_the_period():
    # Newest-first mailbox: m1-m3 fall inside the requested period, m4
    # predates it. Nothing older than m4 should ever be fetched.
    details = {
        "m1": _detail("m1", "t1", "Mon, 3 Aug 2026 09:00:00 +0000", "client@x.com", "agency@x.com"),
        "m2": _detail("m2", "t1", "Mon, 3 Aug 2026 08:00:00 +0000", "client@x.com", "agency@x.com"),
        "m3": _detail("m3", "t1", "Mon, 3 Aug 2026 07:00:00 +0000", "client@x.com", "agency@x.com"),
        "m4": _detail("m4", "t1", "Sun, 26 Jul 2026 07:00:00 +0000", "client@x.com", "agency@x.com"),
        "m5": _detail("m5", "t1", "Sat, 25 Jul 2026 07:00:00 +0000", "client@x.com", "agency@x.com"),
    }
    messages_resource = _FakeMessagesResource(["m1", "m2", "m3", "m4", "m5"], details)
    service = _FakeService(messages_resource)

    result = fetch_message_metadata(service, "client@x.com", date(2026, 8, 1), date(2026, 8, 7))

    assert [m.message_id for m in result] == ["m1", "m2", "m3"]
    # m4 is fetched to discover it's out of range, but m5 (even older) never is.
    assert messages_resource.get_calls == ["m1", "m2", "m3", "m4"]


def test_fetch_message_metadata_never_scans_past_the_hard_cap():
    # Even if every message looks like it's in range (e.g. the newest-first
    # assumption doesn't hold, or a contact has none of their own messages
    # in a very large mailbox), the scan must still stop — never an
    # unbounded crawl of someone's real mailbox.
    ids = [f"m{i}" for i in range(MAX_MESSAGES_SCANNED + 50)]
    details = {
        i: _detail(i, i, "Mon, 3 Aug 2026 09:00:00 +0000", "someone-else@x.com", "agency@x.com")
        for i in ids
    }
    messages_resource = _FakeMessagesResource(ids, details)
    service = _FakeService(messages_resource)

    fetch_message_metadata(service, "client@x.com", date(2026, 8, 1), date(2026, 8, 7))

    assert len(messages_resource.get_calls) == MAX_MESSAGES_SCANNED


def msg(thread_id, from_addr, hour) -> MessageMetadata:
    return MessageMetadata(
        message_id=f"{thread_id}-{hour}",
        thread_id=thread_id,
        from_addr=from_addr,
        to_addr="",
        date=datetime(2026, 8, 3, hour, tzinfo=UTC),
    )


def test_computes_response_time_from_inbound_to_next_outbound():
    # Contact emails at hour 9, agency replies at hour 12 -> 3 hour response.
    messages = [
        msg("t1", "client@x.com", 9),
        msg("t1", "staff@agency.com", 12),
    ]

    avg_hours, thread_count = compute_email_signals(messages, "client@x.com")

    assert avg_hours == 3.0
    assert thread_count == 1


def test_consecutive_inbound_messages_only_count_the_latest():
    # Client sends two follow-ups before getting a reply — response time
    # should be measured from the second (most recent) inbound message.
    messages = [
        msg("t1", "client@x.com", 9),
        msg("t1", "client@x.com", 10),
        msg("t1", "staff@agency.com", 12),
    ]

    avg_hours, _ = compute_email_signals(messages, "client@x.com")

    assert avg_hours == 2.0


def test_thread_with_no_reply_counts_toward_thread_count_only():
    messages = [msg("t1", "client@x.com", 9)]

    avg_hours, thread_count = compute_email_signals(messages, "client@x.com")

    assert avg_hours == 0.0
    assert thread_count == 1


def test_multiple_threads_average_across_all_response_pairs():
    messages = [
        msg("t1", "client@x.com", 9),
        msg("t1", "staff@agency.com", 11),  # 2 hours
        msg("t2", "client@x.com", 9),
        msg("t2", "staff@agency.com", 13),  # 4 hours
    ]

    avg_hours, thread_count = compute_email_signals(messages, "client@x.com")

    assert avg_hours == 3.0
    assert thread_count == 2


def test_sender_matching_uses_exact_address_not_substring():
    messages = [
        msg("t1", "client@x.com", 9),
        msg("t1", "notclient@x.com", 12),
    ]

    avg_hours, _ = compute_email_signals(messages, "client@x.com")

    assert avg_hours == 3.0
