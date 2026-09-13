"""Validation for Google Desktop OAuth client configuration."""

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

MAX_CLIENT_FILE_BYTES = 1024 * 1024
GOOGLE_AUTH_URIS = {
    "https://accounts.google.com/o/oauth2/auth",
    "https://accounts.google.com/o/oauth2/v2/auth",
}
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"


class OAuthClientConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DesktopOAuthClient:
    client_id: str
    client_secret: str
    auth_uri: str
    token_uri: str
    redirect_uris: tuple[str, ...]

    @property
    def project_number(self) -> str:
        return self.client_id.partition("-")[0]


def load_desktop_client(path: Path) -> DesktopOAuthClient:
    try:
        with path.open("rb") as stream:
            payload = stream.read(MAX_CLIENT_FILE_BYTES + 1)
        if len(payload) > MAX_CLIENT_FILE_BYTES:
            raise OAuthClientConfigError("The Google OAuth client file is unexpectedly large.")
        document = json.loads(payload.decode("utf-8"))
    except OAuthClientConfigError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise OAuthClientConfigError("The Google OAuth client file could not be read.") from error
    if not isinstance(document, dict) or "installed" not in document:
        if isinstance(document, dict) and "android" in document:
            raise OAuthClientConfigError(
                "This is an Android OAuth client. Choose a Desktop app OAuth client "
                "from the same project."
            )
        raise OAuthClientConfigError(
            "The Google OAuth client must have application type Desktop app."
        )
    installed = document["installed"]
    if not isinstance(installed, dict):
        raise OAuthClientConfigError("The Desktop OAuth client entry is malformed.")
    required = ("client_id", "client_secret", "auth_uri", "token_uri")
    missing = any(
        not isinstance(installed.get(key), str) or not installed[key].strip()
        for key in required
    )
    if missing:
        raise OAuthClientConfigError("The Desktop OAuth client is missing required fields.")
    if installed["auth_uri"] not in GOOGLE_AUTH_URIS or installed["token_uri"] != GOOGLE_TOKEN_URI:
        raise OAuthClientConfigError(
            "The Desktop OAuth client does not use the official Google authorization endpoints."
        )
    redirects = installed.get("redirect_uris", [])
    if not isinstance(redirects, list) or not all(isinstance(uri, str) for uri in redirects):
        raise OAuthClientConfigError("The Desktop OAuth redirect list is malformed.")
    if not any(_is_localhost_redirect(uri) for uri in redirects):
        raise OAuthClientConfigError(
            "The Desktop OAuth client does not allow a localhost callback."
        )
    return DesktopOAuthClient(
        client_id=installed["client_id"],
        client_secret=installed["client_secret"],
        auth_uri=installed["auth_uri"],
        token_uri=installed["token_uri"],
        redirect_uris=tuple(redirects),
    )


def _is_localhost_redirect(value: str) -> bool:
    try:
        parsed = urlparse(value)
        return (
            parsed.scheme == "http"
            and parsed.netloc == "localhost"
            and parsed.hostname == "localhost"
            and parsed.username is None
            and parsed.password is None
            and parsed.path in {"", "/"}
            and parsed.query == ""
            and parsed.fragment == ""
        )
    except ValueError:
        return False


def require_same_project(desktop: DesktopOAuthClient, existing_client_id: str) -> None:
    """Reject an accidental client from a different Google Cloud project."""
    existing_project = existing_client_id.partition("-")[0]
    if not existing_project or desktop.project_number != existing_project:
        raise OAuthClientConfigError(
            "The Desktop OAuth client belongs to a different Google Cloud project."
        )
