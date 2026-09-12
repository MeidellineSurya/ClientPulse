# Builds authenticated Gmail/Calendar API clients for the agency's
# connected mailbox. Scaffold only — not exercised against a live Google
# account in this environment (no OAuth credentials available here); wire
# up real GOOGLE_* env vars (see backend/.env.example) to actually use it.

from functools import lru_cache

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build

from app.config import settings

# gmail.metadata is the OAuth scope that structurally enforces our privacy
# commitment: it lets us list messages/threads and read headers (From, To,
# Date) but the Gmail API refuses to return the message body under this
# scope at all. Never request gmail.readonly or gmail.modify here — those
# would allow reading message content, which the product explicitly rules out.
GMAIL_METADATA_SCOPE = "https://www.googleapis.com/auth/gmail.metadata"
CALENDAR_READONLY_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"

TOKEN_URI = "https://oauth2.googleapis.com/token"


def _require_google_config() -> None:
    if not (settings.google_client_id and settings.google_client_secret and settings.google_refresh_token):
        raise RuntimeError(
            "GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN must be set "
            "to pull Gmail/Calendar signals"
        )


@lru_cache
def get_google_credentials() -> Credentials:
    # Cached like get_supabase_client — reused across requests instead of
    # re-authenticating every call. Credentials auto-refresh their access
    # token from the refresh token as needed.
    _require_google_config()
    return Credentials(
        token=None,
        refresh_token=settings.google_refresh_token,
        token_uri=TOKEN_URI,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=[GMAIL_METADATA_SCOPE, CALENDAR_READONLY_SCOPE],
    )


def get_gmail_service(credentials: Credentials) -> Resource:
    return build("gmail", "v1", credentials=credentials)


def get_calendar_service(credentials: Credentials) -> Resource:
    return build("calendar", "v3", credentials=credentials)
