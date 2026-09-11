from pathlib import Path

import pytest

from demail.gmail.client import GmailApiError, GmailProfile
from demail.ui.connection import GoogleConnectionService


class Authorization:
    def __init__(self) -> None:
        self.calls = 0

    def authorize_with_system_browser(self) -> None:
        self.calls += 1


class Gmail:
    def __init__(self, result: GmailProfile | Exception) -> None:
        self.result = result

    def profile(self) -> GmailProfile:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def profile() -> GmailProfile:
    return GmailProfile("archive@example.com", 100, 80, "history")


def test_existing_authorization_is_reused_without_browser() -> None:
    authorization = Authorization()
    service = GoogleConnectionService(
        Path("client.json"),
        authorization,  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        gmail_factory=lambda _: Gmail(profile()),  # type: ignore[arg-type]
    )
    assert service.connect().email_address == "archive@example.com"
    assert authorization.calls == 0


@pytest.mark.parametrize("first_error", [PermissionError(), GmailApiError("rejected", 401)])
def test_missing_or_rejected_authorization_opens_browser_once(first_error: Exception) -> None:
    authorization = Authorization()
    responses = iter((Gmail(first_error), Gmail(profile())))
    service = GoogleConnectionService(
        Path("client.json"),
        authorization,  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        gmail_factory=lambda _: next(responses),  # type: ignore[arg-type]
    )
    assert service.connect().messages_total == 100
    assert authorization.calls == 1


def test_network_failure_does_not_reopen_authorization() -> None:
    authorization = Authorization()
    service = GoogleConnectionService(
        Path("client.json"),
        authorization,  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        gmail_factory=lambda _: Gmail(GmailApiError("offline", 503)),  # type: ignore[arg-type]
    )
    with pytest.raises(GmailApiError):
        service.connect()
    assert authorization.calls == 0
