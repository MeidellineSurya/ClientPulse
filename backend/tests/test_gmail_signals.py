# Tests for the pure Gmail metadata -> signal computation (no network,
# no Google API involved).

from datetime import UTC, datetime

from app.services.gmail_signals import MessageMetadata, compute_email_signals


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
