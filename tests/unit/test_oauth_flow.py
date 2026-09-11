import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from demail.auth.oauth import GMAIL_READONLY_SCOPE, OAuthAuthorization


class RecordingStore:
    def __init__(self) -> None:
        self.saved = None

    def save(self, credentials: object) -> None:
        self.saved = credentials


def client_file(tmp_path: Path) -> Path:
    path = tmp_path / "client.json"
    path.write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": "123-desktop.apps.googleusercontent.com",
                    "client_secret": "client-secret",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"],
                }
            }
        ),
        encoding="utf-8",
    )
    return path


def install_fake_google_flow(
    monkeypatch: pytest.MonkeyPatch, scopes: tuple[str, ...]
) -> dict[str, object]:
    recorded: dict[str, object] = {}
    credentials = SimpleNamespace(
        token="access",
        refresh_token="refresh",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="123-desktop.apps.googleusercontent.com",
        client_secret="client-secret",
        scopes=scopes,
        expiry=datetime(2026, 9, 9, tzinfo=UTC),
    )

    class FakeFlow:
        @classmethod
        def from_client_secrets_file(cls, path: str, scopes: list[str]) -> "FakeFlow":
            recorded["path"] = path
            recorded["requested_scopes"] = scopes
            return cls()

        def run_local_server(self, **options: object) -> object:
            recorded["options"] = options
            return credentials

    package = ModuleType("google_auth_oauthlib")
    module = ModuleType("google_auth_oauthlib.flow")
    module.InstalledAppFlow = FakeFlow  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google_auth_oauthlib", package)
    monkeypatch.setitem(sys.modules, "google_auth_oauthlib.flow", module)
    return recorded


def test_authorization_uses_system_browser_ephemeral_port_and_readonly_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = install_fake_google_flow(monkeypatch, (GMAIL_READONLY_SCOPE,))
    store = RecordingStore()
    result = OAuthAuthorization(client_file(tmp_path), store).authorize_with_system_browser()
    assert recorded["requested_scopes"] == [GMAIL_READONLY_SCOPE]
    options = recorded["options"]
    assert isinstance(options, dict)
    assert options["host"] == "localhost"
    assert options["port"] == 0
    assert options["open_browser"] is True
    assert options["access_type"] == "offline"
    assert store.saved == result


def test_unexpected_granted_scope_fails_closed_without_saving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_fake_google_flow(monkeypatch, (GMAIL_READONLY_SCOPE, "unexpected.scope"))
    store = RecordingStore()
    with pytest.raises(PermissionError, match="exactly"):
        OAuthAuthorization(client_file(tmp_path), store).authorize_with_system_browser()
    assert store.saved is None
