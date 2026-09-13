import pytest

from app import google_client


class _FakeCredentials:
    granted_scopes = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.refreshed_with = None

    def refresh(self, request):
        self.refreshed_with = request

    def has_scopes(self, scopes):
        return set(scopes).issubset(self.kwargs["scopes"])


class _FakeMissingScopeCredentials(_FakeCredentials):
    granted_scopes = (google_client.GMAIL_METADATA_SCOPE,)


class _FakeBroadScopeCredentials(_FakeCredentials):
    granted_scopes = (
        google_client.GMAIL_METADATA_SCOPE,
        google_client.CALENDAR_READONLY_SCOPE,
        "https://www.googleapis.com/auth/gmail.readonly",
    )


class _FakeUnexpectedScopeCredentials(_FakeCredentials):
    granted_scopes = (
        google_client.GMAIL_METADATA_SCOPE,
        google_client.CALENDAR_READONLY_SCOPE,
        "https://www.googleapis.com/auth/gmail.send",
    )


def _configure_google(monkeypatch):
    monkeypatch.setattr(google_client.settings, "google_client_id", "client-id")
    monkeypatch.setattr(google_client.settings, "google_client_secret", "client-secret")
    monkeypatch.setattr(google_client.settings, "google_refresh_token", "refresh-token")
    monkeypatch.setattr(google_client.settings, "google_agency_id", "agency-a")
    google_client.get_google_credentials.cache_clear()


def test_google_credentials_are_refreshed_before_use(monkeypatch):
    _configure_google(monkeypatch)
    request = object()
    monkeypatch.setattr(google_client, "Credentials", _FakeCredentials)
    monkeypatch.setattr(google_client, "Request", lambda: request, raising=False)

    try:
        credentials = google_client.get_google_credentials("agency-a")
    finally:
        google_client.get_google_credentials.cache_clear()

    assert credentials.refreshed_with is request
    assert credentials.kwargs["scopes"] == [
        google_client.GMAIL_METADATA_SCOPE,
        google_client.CALENDAR_READONLY_SCOPE,
    ]


def test_google_credentials_reject_refresh_token_without_required_scopes(monkeypatch):
    _configure_google(monkeypatch)
    monkeypatch.setattr(google_client, "Credentials", _FakeMissingScopeCredentials)
    monkeypatch.setattr(google_client, "Request", object, raising=False)

    try:
        with pytest.raises(
            RuntimeError, match="required Gmail metadata and Calendar read-only scopes"
        ):
            google_client.get_google_credentials("agency-a")
    finally:
        google_client.get_google_credentials.cache_clear()


def test_google_credentials_reject_body_reading_gmail_scope(monkeypatch):
    _configure_google(monkeypatch)
    monkeypatch.setattr(google_client, "Credentials", _FakeBroadScopeCredentials)
    monkeypatch.setattr(google_client, "Request", object, raising=False)

    try:
        with pytest.raises(RuntimeError, match="body-reading Gmail scope"):
            google_client.get_google_credentials("agency-a")
    finally:
        google_client.get_google_credentials.cache_clear()


def test_google_credentials_reject_any_unapproved_oauth_scope(monkeypatch):
    _configure_google(monkeypatch)
    monkeypatch.setattr(google_client, "Credentials", _FakeUnexpectedScopeCredentials)
    monkeypatch.setattr(google_client, "Request", object, raising=False)

    try:
        with pytest.raises(RuntimeError, match="unapproved OAuth scopes"):
            google_client.get_google_credentials("agency-a")
    finally:
        google_client.get_google_credentials.cache_clear()
