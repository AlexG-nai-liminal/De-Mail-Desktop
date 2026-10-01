"""Resolve the OAuth identity used by installed and development builds."""

from dataclasses import dataclass
from pathlib import Path

from .client_config import OAuthClientConfigError, load_desktop_client

PRODUCTION_CLIENT_NAME = "google-oauth-client.json"


@dataclass(frozen=True, slots=True)
class OAuthClientSource:
    path: Path
    is_production: bool

    @property
    def label(self) -> str:
        return "Built-in production client" if self.is_production else "Development client file"


def bundled_client_path(asset_root: Path | None = None) -> Path:
    root = asset_root or Path(__file__).resolve().parents[1] / "assets"
    return root / PRODUCTION_CLIENT_NAME


def resolve_oauth_client(
    manual_path: str = "", asset_root: Path | None = None
) -> OAuthClientSource | None:
    """Prefer the packaged client and fall back to an explicit developer file."""
    packaged = bundled_client_path(asset_root)
    if packaged.exists():
        load_desktop_client(packaged)
        return OAuthClientSource(packaged, True)

    value = manual_path.strip()
    if not value:
        return None
    path = Path(value)
    if not path.is_file():
        return None
    load_desktop_client(path)
    return OAuthClientSource(path, False)


def describe_oauth_source(
    manual_path: str = "", asset_root: Path | None = None
) -> str:
    try:
        source = resolve_oauth_client(manual_path, asset_root)
    except OAuthClientConfigError:
        return "OAuth client configuration needs attention"
    return source.label if source else "Production authorization is not configured"
