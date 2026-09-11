"""Google installed-application OAuth flow using the system browser."""

from datetime import UTC
from pathlib import Path

from .client_config import load_desktop_client
from .token_store import CredentialStore, StoredCredentials

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
ARCHIVE_SCOPES = (GMAIL_READONLY_SCOPE,)


class OAuthAuthorization:
    def __init__(self, client_path: Path, store: CredentialStore) -> None:
        self.client_path = client_path
        self.store = store

    def authorize_with_system_browser(self) -> StoredCredentials:
        """Run the local-server installed-app flow and persist only protected credentials."""
        load_desktop_client(self.client_path)
        from google_auth_oauthlib.flow import InstalledAppFlow

        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.client_path), scopes=list(ARCHIVE_SCOPES)
        )
        credentials = flow.run_local_server(
            host="localhost",
            port=0,
            open_browser=True,
            authorization_prompt_message="Opening Google authorization in your browser...",
            success_message="Authorization complete. You may close this browser tab.",
            access_type="offline",
            prompt="consent",
        )
        granted = tuple(credentials.scopes or ())
        if set(granted) != set(ARCHIVE_SCOPES):
            raise PermissionError("Google did not grant exactly the required read-only scope.")
        if not credentials.refresh_token:
            raise PermissionError("Google did not return a refresh credential.")
        stored = StoredCredentials(
            token=credentials.token,
            refresh_token=credentials.refresh_token,
            token_uri=credentials.token_uri,
            client_id=credentials.client_id,
            client_secret=credentials.client_secret,
            scopes=granted,
            expiry=credentials.expiry.astimezone(UTC).isoformat() if credentials.expiry else None,
        )
        self.store.save(stored)
        return stored

