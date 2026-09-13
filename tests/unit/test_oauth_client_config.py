import json
from pathlib import Path

import pytest

from demail.auth.client_config import (
    MAX_CLIENT_FILE_BYTES,
    OAuthClientConfigError,
    load_desktop_client,
    require_same_project,
)


def write(path: Path, document: object) -> None:
    path.write_text(json.dumps(document), encoding="utf-8")


def desktop_document(client_id: str = "123-project.apps.googleusercontent.com") -> dict:
    return {
        "installed": {
            "client_id": client_id,
            "client_secret": "client-secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


def test_valid_desktop_client_is_loaded(tmp_path: Path) -> None:
    path = tmp_path / "client.json"
    write(path, desktop_document())
    client = load_desktop_client(path)
    assert client.project_number == "123"
    require_same_project(client, "123-android.apps.googleusercontent.com")


def test_android_client_is_rejected_with_actionable_message(tmp_path: Path) -> None:
    path = tmp_path / "android.json"
    write(path, {"android": {"client_id": "123-android.apps.googleusercontent.com"}})
    with pytest.raises(OAuthClientConfigError, match="Android OAuth client"):
        load_desktop_client(path)


@pytest.mark.parametrize(
    "document",
    [
        None,
        {},
        {"installed": []},
        {"installed": {"client_id": "id"}},
        {"installed": {**desktop_document()["installed"], "redirect_uris": "localhost"}},
        {"installed": {**desktop_document()["installed"], "redirect_uris": ["https://example.com"]}},
    ],
)
def test_malformed_or_wrong_client_configuration_is_rejected(
    tmp_path: Path, document: object
) -> None:
    path = tmp_path / "client.json"
    write(path, document)
    with pytest.raises(OAuthClientConfigError):
        load_desktop_client(path)


def test_invalid_json_is_rejected_without_exposing_contents(tmp_path: Path) -> None:
    path = tmp_path / "client.json"
    path.write_text("not json secret-value", encoding="utf-8")
    with pytest.raises(OAuthClientConfigError) as caught:
        load_desktop_client(path)
    assert "secret-value" not in str(caught.value)


def test_different_cloud_project_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "client.json"
    write(path, desktop_document("456-desktop.apps.googleusercontent.com"))
    with pytest.raises(OAuthClientConfigError, match="different Google Cloud project"):
        require_same_project(load_desktop_client(path), "123-android.apps.googleusercontent.com")


@pytest.mark.parametrize(
    "redirect",
    [
        "http://localhost.example.invalid",
        "http://localhost:8080",
        "http://localhost/callback",
        "https://localhost",
        "http://user@localhost",
        "http://localhost?forward=elsewhere",
        "http://localhost#fragment",
    ],
)
def test_deceptive_or_non_loopback_redirect_is_rejected(
    tmp_path: Path, redirect: str
) -> None:
    path = tmp_path / "client.json"
    document = desktop_document()
    document["installed"]["redirect_uris"] = [redirect]
    write(path, document)
    with pytest.raises(OAuthClientConfigError, match="localhost callback"):
        load_desktop_client(path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("auth_uri", "https://accounts.google.com.example.invalid/o/oauth2/auth"),
        ("auth_uri", "http://accounts.google.com/o/oauth2/auth"),
        ("token_uri", "https://oauth2.googleapis.com.example.invalid/token"),
    ],
)
def test_non_google_oauth_endpoint_is_rejected(
    tmp_path: Path, field: str, value: str
) -> None:
    path = tmp_path / "client.json"
    document = desktop_document()
    document["installed"][field] = value
    write(path, document)
    with pytest.raises(OAuthClientConfigError, match="official Google"):
        load_desktop_client(path)


def test_client_file_read_is_bounded(tmp_path: Path) -> None:
    path = tmp_path / "oversized.json"
    path.write_bytes(b" " * (MAX_CLIENT_FILE_BYTES + 1))
    with pytest.raises(OAuthClientConfigError, match="unexpectedly large"):
        load_desktop_client(path)
