"""Read-only, fail-closed update metadata checks against the public release feed."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from demail import __version__

REPOSITORY = "AlexG-nai-liminal/de-mail-desktop-releases"
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
RELEASES_URL = f"https://github.com/{REPOSITORY}/releases"
MAX_RESPONSE_BYTES = 256 * 1024
_SEMVER = re.compile(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)")


class Response(Protocol):
    headers: object

    def read(self, size: int = -1) -> bytes: ...

    def __enter__(self) -> Response: ...

    def __exit__(self, *args: object) -> None: ...


class UpdateState(str, Enum):
    CURRENT = "current"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class UpdateResult:
    state: UpdateState
    current_version: str
    latest_version: str | None = None
    release_url: str | None = None


def version_tuple(value: str) -> tuple[int, int, int]:
    """Validate and compare stable three-part release versions."""
    if not _SEMVER.fullmatch(value):
        raise ValueError("Version metadata is not a stable major.minor.patch value")
    major, minor, patch = value.split(".")
    return int(major), int(minor), int(patch)


def _headers_content_type(headers: object) -> str:
    getter = getattr(headers, "get", None)
    if not callable(getter):
        return ""
    value = getter("Content-Type", "")
    return value if isinstance(value, str) else ""


def _parse_release(payload: object, current_version: str) -> UpdateResult:
    if not isinstance(payload, dict):
        raise ValueError("Release metadata is not an object")
    if payload.get("draft") is not False or payload.get("prerelease") is not False:
        raise ValueError("Release metadata does not describe a published stable release")
    tag = payload.get("tag_name")
    if not isinstance(tag, str) or not tag.startswith("v"):
        raise ValueError("Release tag is missing or invalid")
    latest = tag[1:]
    latest_tuple = version_tuple(latest)
    current_tuple = version_tuple(current_version)
    assets = payload.get("assets")
    expected_setup = f"de-Mail-Desktop-Setup-{latest}.exe"
    if not isinstance(assets, list) or not any(
        isinstance(asset, dict) and asset.get("name") == expected_setup for asset in assets
    ):
        raise ValueError("Release metadata has no matching Windows setup asset")
    if latest_tuple > current_tuple:
        return UpdateResult(
            UpdateState.AVAILABLE,
            current_version,
            latest,
            f"{RELEASES_URL}/tag/v{latest}",
        )
    return UpdateResult(UpdateState.CURRENT, current_version, latest)


def check_for_update(
    current_version: str = __version__,
    *,
    opener=urlopen,
    timeout: float = 8.0,
    max_response_bytes: int = MAX_RESPONSE_BYTES,
) -> UpdateResult:
    """Read latest-release metadata without downloading or executing release assets."""
    if timeout <= 0 or max_response_bytes <= 0:
        return UpdateResult(UpdateState.UNAVAILABLE, current_version)
    request = Request(
        LATEST_RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"de-Mail-Desktop/{current_version}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with opener(request, timeout=timeout) as response:
            content_type = _headers_content_type(response.headers).lower()
            if not content_type.startswith("application/json"):
                raise ValueError("Update response is not JSON")
            raw = response.read(max_response_bytes + 1)
        if len(raw) > max_response_bytes:
            raise ValueError("Update response is too large")
        payload = json.loads(raw.decode("utf-8"))
        return _parse_release(payload, current_version)
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeError, ValueError):
        return UpdateResult(UpdateState.UNAVAILABLE, current_version)
