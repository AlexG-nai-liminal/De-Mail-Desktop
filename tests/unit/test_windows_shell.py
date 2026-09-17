from pathlib import Path

import pytest

from demail.windows.shell import MAILTO_URI_LIMIT, open_email_draft, open_folder


def test_open_folder_uses_validated_absolute_directory(tmp_path: Path) -> None:
    opened = []
    open_folder(tmp_path, opened.append)
    assert opened == [str(tmp_path)]


@pytest.mark.parametrize("value", [Path("relative"), Path("C:/missing-folder")])
def test_open_folder_rejects_unsafe_or_missing_path(value: Path) -> None:
    with pytest.raises(OSError, match="unavailable"):
        open_folder(value, lambda _: None)


def test_email_draft_is_addressed_and_percent_encoded() -> None:
    opened: list[str] = []
    open_email_draft(
        "alex@liminalmemory.com",
        "de-Mail report",
        "Line one\nA private-looking value: a+b@example.com",
        opened.append,
    )
    assert opened == [
        "mailto:alex@liminalmemory.com?subject=de-Mail%20report&"
        "body=Line%20one%0AA%20private-looking%20value%3A%20a%2Bb%40example.com"
    ]


@pytest.mark.parametrize(
    ("recipient", "subject", "body"),
    [
        ("alex@liminalmemory.com\nBcc:other@example.com", "Report", "Body"),
        ("alex@liminalmemory.com", "Report\r\nBcc:other@example.com", "Body"),
        ("alex@liminalmemory.com", "Report", ""),
        ("not-an-address", "Report", "Body"),
    ],
)
def test_email_draft_rejects_malformed_or_injectable_values(
    recipient: str, subject: str, body: str
) -> None:
    with pytest.raises(ValueError):
        open_email_draft(recipient, subject, body, lambda _: None)


def test_email_draft_rejects_oversized_report() -> None:
    with pytest.raises(ValueError, match="too large"):
        open_email_draft(
            "alex@liminalmemory.com", "Report", "x" * MAILTO_URI_LIMIT, lambda _: None
        )


def test_email_draft_reports_launcher_failure() -> None:
    with pytest.raises(OSError, match="did not accept"):
        open_email_draft(
            "alex@liminalmemory.com", "Report", "Safe report", lambda _: False
        )
