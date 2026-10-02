import json
from pathlib import Path

import pytest

from demail.auth.client_config import MAX_CLIENT_FILE_BYTES, OAuthClientConfigError
from demail.auth.client_source import resolve_oauth_client
from tools.configure_oauth import configure_client


def payload() -> bytes:
    return json.dumps(
        {
            "installed": {
                "client_id": "123-test.apps.googleusercontent.com",
                "client_secret": "test-only",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }
    ).encode()


def test_installed_identity_is_resolved_without_manual_selection(tmp_path: Path) -> None:
    source = tmp_path / "download.json"
    source.write_bytes(payload())
    target = tmp_path / "assets" / "google-oauth-client.json"
    assert configure_client(source, target) == target
    assert target.read_bytes() == source.read_bytes()
    assert resolve_oauth_client(asset_root=target.parent).is_production
    assert not target.with_suffix(".json.partial").exists()


@pytest.mark.parametrize(
    "bad",
    [b"", b"broken", b"[]", b"{}", b"\xff", b" " * (MAX_CLIENT_FILE_BYTES + 1)],
    ids=["empty", "invalid-json", "array", "no-client", "bad-utf8", "oversize"],
)
def test_malformed_identity_preserves_existing_client(tmp_path: Path, bad: bytes) -> None:
    source = tmp_path / "download.json"
    source.write_bytes(bad)
    target = tmp_path / "google-oauth-client.json"
    target.write_bytes(payload())
    with pytest.raises(OAuthClientConfigError):
        configure_client(source, target)
    assert target.read_bytes() == payload()


def test_failed_publication_cleans_partial_and_can_retry(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "download.json"
    source.write_bytes(payload())
    target = tmp_path / "google-oauth-client.json"
    target.write_bytes(b"previous")
    original = Path.replace
    with monkeypatch.context() as patch:
        patch.setattr(Path, "replace", lambda *args: (_ for _ in ()).throw(OSError("busy")))
        with pytest.raises(OSError, match="busy"):
            configure_client(source, target)
    assert target.read_bytes() == b"previous"
    assert not target.with_suffix(".json.partial").exists()
    assert Path.replace is original
    configure_client(source, target)
    assert target.read_bytes() == payload()


def test_missing_source_leaves_existing_identity_untouched(tmp_path: Path) -> None:
    target = tmp_path / "google-oauth-client.json"
    target.write_bytes(payload())
    with pytest.raises(FileNotFoundError):
        configure_client(tmp_path / "missing.json", target)
    assert target.read_bytes() == payload()
