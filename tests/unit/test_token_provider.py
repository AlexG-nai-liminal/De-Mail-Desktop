from datetime import UTC, datetime, timedelta

import pytest

from demail.auth.oauth import GMAIL_READONLY_SCOPE
from demail.auth.token_provider import GoogleTokenProvider
from demail.auth.token_store import StoredCredentials


class Store:
    def __init__(self, value: StoredCredentials | None) -> None:
        self.value = value
        self.saved: StoredCredentials | None = None

    def load(self) -> StoredCredentials | None:
        return self.value

    def save(self, value: StoredCredentials) -> None:
        self.saved = value
        self.value = value


def stored(*, token: str = "access", expiry: datetime | None = None) -> StoredCredentials:
    return StoredCredentials(
        token=token,
        refresh_token="refresh",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="123-desktop.apps.googleusercontent.com",
        client_secret="client-secret",
        scopes=(GMAIL_READONLY_SCOPE,),
        expiry=expiry.isoformat() if expiry else None,
    )


def test_valid_saved_access_token_is_reused_without_refresh() -> None:
    store = Store(stored(expiry=datetime.now(UTC) + timedelta(hours=1)))
    assert GoogleTokenProvider(store).access_token() == "access"  # type: ignore[arg-type]
    assert store.saved is None


def test_missing_authorization_fails_closed() -> None:
    with pytest.raises(PermissionError, match="not connected"):
        GoogleTokenProvider(Store(None)).access_token()  # type: ignore[arg-type]


def test_unexpected_scope_is_never_used() -> None:
    value = stored(expiry=datetime.now(UTC) + timedelta(hours=1))
    wrong = StoredCredentials(
        token=value.token,
        refresh_token=value.refresh_token,
        token_uri=value.token_uri,
        client_id=value.client_id,
        client_secret=value.client_secret,
        scopes=(GMAIL_READONLY_SCOPE, "unexpected.scope"),
        expiry=value.expiry,
    )
    with pytest.raises(PermissionError, match="required scope"):
        GoogleTokenProvider(Store(wrong)).access_token()  # type: ignore[arg-type]


def test_expired_token_is_refreshed_and_saved(monkeypatch: pytest.MonkeyPatch) -> None:
    store = Store(stored(expiry=datetime.now(UTC) - timedelta(hours=1)))

    def refresh(credentials, request: object) -> None:
        credentials.token = "renewed"
        credentials.expiry = datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1)

    monkeypatch.setattr("google.oauth2.credentials.Credentials.refresh", refresh)
    assert GoogleTokenProvider(store).access_token() == "renewed"  # type: ignore[arg-type]
    assert store.saved is not None
    assert store.saved.token == "renewed"
