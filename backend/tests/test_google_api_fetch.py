from datetime import date

from app.services.calendar_signals import fetch_events
from app.services.gmail_signals import fetch_message_metadata


class _Request:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class _MessagesApi:
    def __init__(self, details):
        self.details = details
        self.list_calls = []

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        return _Request(
            {"messages": [{"id": message_id} for message_id in self.details]}
        )

    def get(self, **kwargs):
        return _Request(self.details[kwargs["id"]])


class _UsersApi:
    def __init__(self, messages_api):
        self.messages_api = messages_api

    def messages(self):
        return self.messages_api


class _GmailService:
    def __init__(self, details):
        self.messages_api = _MessagesApi(details)

    def users(self):
        return _UsersApi(self.messages_api)


class _EventsApi:
    def __init__(self):
        self.list_calls = []

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        if kwargs["pageToken"] is None:
            return _Request(
                {
                    "items": [
                        {
                            "status": "confirmed",
                            "attendees": [{"email": "client@example.com"}],
                        }
                    ],
                    "nextPageToken": "page-2",
                }
            )
        return _Request({"items": [{"status": "cancelled"}]})


class _CalendarService:
    def __init__(self):
        self.events_api = _EventsApi()

    def events(self):
        return self.events_api


def _message(message_id, from_addr, to_addr, sent_at):
    return {
        "id": message_id,
        "threadId": f"thread-{message_id}",
        "payload": {
            "headers": [
                {"name": "From", "value": from_addr},
                {"name": "To", "value": to_addr},
                {"name": "Date", "value": sent_at},
            ]
        },
    }


def test_metadata_scope_fetch_filters_contact_and_period_without_gmail_query():
    service = _GmailService(
        {
            "relevant": _message(
                "relevant",
                "Client <client@example.com>",
                "agency@example.com",
                "Wed, 02 Sep 2026 09:00:00 +0000",
            ),
            "other-contact": _message(
                "other-contact",
                "other@example.com",
                "agency@example.com",
                "Thu, 03 Sep 2026 09:00:00 +0000",
            ),
            "outside-period": _message(
                "outside-period",
                "client@example.com",
                "agency@example.com",
                "Thu, 20 Aug 2026 09:00:00 +0000",
            ),
        }
    )

    messages = fetch_message_metadata(
        service,
        "client@example.com",
        date(2026, 9, 1),
        date(2026, 9, 7),
    )

    assert [message.message_id for message in messages] == ["relevant"]
    assert service.messages_api.list_calls == [
        {
            "userId": "me",
            "pageToken": None,
            "maxResults": 100,
            "includeSpamTrash": False,
        }
    ]


def test_metadata_fetch_skips_message_with_invalid_date_header():
    service = _GmailService(
        {
            "invalid": _message(
                "invalid",
                "client@example.com",
                "agency@example.com",
                "not-a-date",
            )
        }
    )

    messages = fetch_message_metadata(
        service,
        "client@example.com",
        date(2026, 9, 1),
        date(2026, 9, 7),
    )

    assert messages == []


def test_calendar_fetch_uses_read_only_window_and_paginates_cancelled_events():
    service = _CalendarService()

    events = fetch_events(
        service,
        "client@example.com",
        date(2026, 9, 1),
        date(2026, 9, 7),
    )

    assert [event.status for event in events] == ["confirmed", "cancelled"]
    # Calendar cancelled exceptions may contain only IDs; the exact email query
    # still establishes that the deleted event belongs to this contact.
    assert events[1].attendee_emails == ["client@example.com"]
    assert service.events_api.list_calls == [
        {
            "calendarId": "primary",
            "timeMin": "2026-09-01T00:00:00Z",
            "timeMax": "2026-09-08T00:00:00Z",
            "q": "client@example.com",
            "singleEvents": True,
            "showDeleted": True,
            "pageToken": None,
        },
        {
            "calendarId": "primary",
            "timeMin": "2026-09-01T00:00:00Z",
            "timeMax": "2026-09-08T00:00:00Z",
            "q": "client@example.com",
            "singleEvents": True,
            "showDeleted": True,
            "pageToken": "page-2",
        },
    ]
