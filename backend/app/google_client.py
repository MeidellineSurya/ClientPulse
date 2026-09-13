# Builds authenticated Gmail/Calendar API clients for the agency's
# connected mailbox. The refresh token is exchanged eagerly so invalid,
# revoked, or under-scoped OAuth credentials fail before ingestion begins.

from functools import lru_cache

from google.auth.transport.requests import Request
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
BODY_READING_GMAIL_SCOPES = frozenset(
    {
        "https://mail.google.com/",
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/gmail.readonly",
    }
)

TOKEN_URI = "https://oauth2.googleapis.com/token"


class GoogleIntegrationNotFound(RuntimeError):
    """The deployment's Google mailbox is not assigned to this agency."""


def _require_google_config(agency_id: str) -> None:
    if not settings.google_agency_id:
        raise RuntimeError(
            "GOOGLE_AGENCY_ID must be set to bind Gmail/Calendar ingestion to an agency"
        )
    if agency_id != settings.google_agency_id:
        raise GoogleIntegrationNotFound
    if not (
        settings.google_client_id
        and settings.google_client_secret
        and settings.google_refresh_token
    ):
        raise RuntimeError(
            "GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN must "
            "be set to pull Gmail/Calendar signals"
        )


@lru_cache
def get_google_credentials(agency_id: str) -> Credentials:
    # Cached like get_supabase_client — reused across requests instead of
    # re-authenticating every call. Credentials auto-refresh their access
    # token from the refresh token as needed.
    _require_google_config(agency_id)
    credentials = Credentials(
        token=None,
        refresh_token=settings.google_refresh_token,
        token_uri=TOKEN_URI,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=[GMAIL_METADATA_SCOPE, CALENDAR_READONLY_SCOPE],
    )
    # Fail during dependency setup rather than halfway through a multi-source
    # ingestion run. The cached credential refreshes again automatically when
    # Google expires its short-lived access token.
    credentials.refresh(Request())
    required_scopes = {GMAIL_METADATA_SCOPE, CALENDAR_READONLY_SCOPE}
    reported_scopes = credentials.granted_scopes
    granted_scopes = (
        set(reported_scopes) if reported_scopes is not None else required_scopes
    )
    if not required_scopes.issubset(granted_scopes):
        raise RuntimeError(
            "Google refresh token is missing the required Gmail metadata and "
            "Calendar read-only scopes"
        )
    if granted_scopes & BODY_READING_GMAIL_SCOPES:
        raise RuntimeError(
            "Google refresh token includes a prohibited body-reading Gmail scope"
        )
    if granted_scopes - required_scopes:
        raise RuntimeError("Google refresh token includes unapproved OAuth scopes")
    return credentials


def get_gmail_service(credentials: Credentials) -> Resource:
    return build("gmail", "v1", credentials=credentials)


def get_calendar_service(credentials: Credentials) -> Resource:
    return build("calendar", "v3", credentials=credentials)
