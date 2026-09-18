import json
from io import BytesIO
from urllib.error import URLError

import pytest

from demail.updates import (
    LATEST_RELEASE_API,
    RELEASES_URL,
    UpdateState,
    check_for_update,
    version_tuple,
)


class FakeResponse:
    def __init__(self, payload: bytes, content_type: str = "application/json") -> None:
        self.stream = BytesIO(payload)
        self.headers = {"Content-Type": content_type}

    def read(self, size: int = -1) -> bytes:
        return self.stream.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None


def release_payload(version: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "tag_name": f"v{version}",
        "draft": False,
        "prerelease": False,
        "html_url": "https://attacker.invalid/fake",
        "assets": [
            {
                "name": f"de-Mail-Desktop-Setup-{version}.exe",
                "browser_download_url": "https://attacker.invalid/payload.exe",
            }
        ],
    }
    payload.update(overrides)
    return payload


def checker(payload: object, *, content_type: str = "application/json", **options):
    raw = json.dumps(payload).encode("utf-8")

    def open_response(request, *, timeout):
        assert request.full_url == LATEST_RELEASE_API
        assert request.get_method() == "GET"
        assert request.data is None
        assert request.get_header("Accept") == "application/vnd.github+json"
        assert request.get_header("Authorization") is None
        assert timeout == 8.0
        return FakeResponse(raw, content_type)

    return check_for_update("0.2.0", opener=open_response, **options)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("0.0.0", (0, 0, 0)), ("0.2.0", (0, 2, 0)), ("12.345.6", (12, 345, 6))],
)
def test_version_tuple_accepts_stable_semantic_versions(value, expected) -> None:
    assert version_tuple(value) == expected


@pytest.mark.parametrize(
    "value", ["", "v1.2.3", "1.2", "1.2.3.4", "1.2.3-beta", "01.2.3", "a.b.c"]
)
def test_version_tuple_rejects_malformed_or_unstable_versions(value: str) -> None:
    with pytest.raises(ValueError):
        version_tuple(value)


def test_newer_published_release_is_available_at_a_constructed_trusted_url() -> None:
    result = checker(release_payload("0.3.0"))

    assert result.state is UpdateState.AVAILABLE
    assert result.current_version == "0.2.0"
    assert result.latest_version == "0.3.0"
    assert result.release_url == f"{RELEASES_URL}/tag/v0.3.0"
    assert "attacker.invalid" not in result.release_url


@pytest.mark.parametrize("latest", ["0.2.0", "0.1.9"])
def test_equal_or_older_published_release_reports_current(latest: str) -> None:
    result = checker(release_payload(latest))

    assert result.state is UpdateState.CURRENT
    assert result.release_url is None


@pytest.mark.parametrize(
    "payload",
    [
        [],
        release_payload("0.3.0", draft=True),
        release_payload("0.3.0", prerelease=True),
        release_payload("0.3.0", tag_name="release-0.3.0"),
        release_payload("0.3.0", tag_name="v0.3.0-beta"),
        release_payload("0.3.0", assets=[]),
        release_payload("0.3.0", assets=[{"name": "unexpected.exe"}]),
    ],
)
def test_untrusted_or_incomplete_release_metadata_fails_closed(payload: object) -> None:
    assert checker(payload).state is UpdateState.UNAVAILABLE


def test_non_json_content_type_and_malformed_json_fail_closed() -> None:
    assert checker(release_payload("0.3.0"), content_type="text/html").state is (
        UpdateState.UNAVAILABLE
    )

    result = check_for_update(
        "0.2.0", opener=lambda *_args, **_kwargs: FakeResponse(b"{not json")
    )
    assert result.state is UpdateState.UNAVAILABLE


def test_oversized_response_fails_closed_at_the_boundary() -> None:
    raw = json.dumps(release_payload("0.3.0")).encode("utf-8")
    opener = lambda *_args, **_kwargs: FakeResponse(raw)  # noqa: E731

    assert check_for_update(
        "0.2.0", opener=opener, max_response_bytes=len(raw)
    ).state is UpdateState.AVAILABLE
    assert check_for_update(
        "0.2.0", opener=opener, max_response_bytes=len(raw) - 1
    ).state is UpdateState.UNAVAILABLE


def test_network_failure_and_invalid_limits_fail_closed() -> None:
    def offline(*_args, **_kwargs):
        raise URLError("offline")

    assert check_for_update("0.2.0", opener=offline).state is UpdateState.UNAVAILABLE
    assert check_for_update("0.2.0", opener=offline, timeout=0).state is (
        UpdateState.UNAVAILABLE
    )
    assert check_for_update("0.2.0", opener=offline, max_response_bytes=0).state is (
        UpdateState.UNAVAILABLE
    )


def test_invalid_installed_version_cannot_be_tricked_into_an_update() -> None:
    raw = json.dumps(release_payload("9.9.9")).encode("utf-8")
    result = check_for_update(
        "development", opener=lambda *_args, **_kwargs: FakeResponse(raw)
    )
    assert result.state is UpdateState.UNAVAILABLE
