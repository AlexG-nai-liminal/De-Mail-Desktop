"""Refreshable Google access tokens backed by protected storage."""

from datetime import UTC, datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from .oauth import ARCHIVE_SCOPES
from .token_store import CredentialStore, StoredCredentials


class GoogleTokenProvider:
    def __init__(self, store: CredentialStore) -> None:
        self.store = store

    def access_token(self) -> str:
        stored = self.store.load()
        if stored is None:
            raise PermissionError("Google authorization is not connected.")
        if set(stored.scopes) != set(ARCHIVE_SCOPES):
            raise PermissionError("Saved Google authorization does not have the required scope.")
        credentials = self._credentials(stored)
        if not credentials.valid:
            if not credentials.refresh_token:
                raise PermissionError("Google authorization cannot be refreshed.")
            try:
                credentials.refresh(Request())
            except Exception as error:
                raise PermissionError("Google authorization has expired or was revoked.") from error
            self.store.save(self._stored(credentials))
        if not credentials.token:
            raise PermissionError("Google did not provide an access token.")
        return credentials.token

    @staticmethod
    def _credentials(stored: StoredCredentials) -> Credentials:
        expiry = datetime.fromisoformat(stored.expiry) if stored.expiry else None
        if expiry is not None and expiry.tzinfo is not None:
            expiry = expiry.astimezone(UTC).replace(tzinfo=None)
        return Credentials(
            token=stored.token,
            refresh_token=stored.refresh_token,
            token_uri=stored.token_uri,
            client_id=stored.client_id,
            client_secret=stored.client_secret,
            scopes=list(stored.scopes),
            expiry=expiry,
        )

    @staticmethod
    def _stored(credentials: Credentials) -> StoredCredentials:
        if not credentials.refresh_token:
            raise PermissionError("Google did not provide a refresh credential.")
        return StoredCredentials(
            token=credentials.token,
            refresh_token=credentials.refresh_token,
            token_uri=credentials.token_uri,
            client_id=credentials.client_id,
            client_secret=credentials.client_secret,
            scopes=tuple(credentials.scopes or ()),
            expiry=(
                credentials.expiry.replace(tzinfo=UTC).isoformat()
                if credentials.expiry and credentials.expiry.tzinfo is None
                else credentials.expiry.astimezone(UTC).isoformat()
                if credentials.expiry
                else None
            ),
        )
