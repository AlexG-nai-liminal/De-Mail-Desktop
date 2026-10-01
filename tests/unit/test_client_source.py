import json
from pathlib import Path

import pytest

from demail.auth.client_config import OAuthClientConfigError
from demail.auth.client_source import resolve_oauth_client


def write_client(path: Path, client_id: str = "123-example.apps.googleusercontent.com") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": client_id,
                    "client_secret": "development-secret",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"],
                }
            }
        ),
        encoding="utf-8",
    )


def test_packaged_production_client_takes_precedence(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    production = assets / "google-oauth-client.json"
    development = tmp_path / "development.json"
    write_client(production, "100-production.apps.googleusercontent.com")
    write_client(development, "200-development.apps.googleusercontent.com")

    source = resolve_oauth_client(str(development), assets)

    assert source is not None
    assert source.path == production
    assert source.is_production is True


def test_development_client_is_available_when_package_has_none(tmp_path: Path) -> None:
    development = tmp_path / "development.json"
    write_client(development)
    source = resolve_oauth_client(str(development), tmp_path / "empty-assets")
    assert source is not None
    assert source.path == development
    assert source.is_production is False


@pytest.mark.parametrize("manual", ["", "   ", "missing.json"])
def test_missing_configuration_returns_none(tmp_path: Path, manual: str) -> None:
    assert resolve_oauth_client(manual, tmp_path / "assets") is None


def test_malformed_packaged_client_fails_closed(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    packaged = assets / "google-oauth-client.json"
    packaged.parent.mkdir()
    packaged.write_text("not-json", encoding="utf-8")
    development = tmp_path / "development.json"
    write_client(development)

    with pytest.raises(OAuthClientConfigError):
        resolve_oauth_client(str(development), assets)
