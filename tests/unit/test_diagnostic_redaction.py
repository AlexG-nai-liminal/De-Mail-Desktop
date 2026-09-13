import pytest

from demail.diagnostics.redaction import MAX_LENGTH, mask_account, redact


@pytest.mark.parametrize(
    ("private", "text", "survives"),
    [
        (
            "Divorce-settlement-draft",
            "Could not write 2023-02-04_0912_Divorce-settlement-draft_18c9.eml",
            ".eml",
        ),
        ("alice", "Auth failed for alice@gmail.com", "@gmail.com"),
        ("bob.smith", "from alice@example.org to bob.smith+tag@company.co.uk", "@company.co.uk"),
        ("ya29", "Authorization: Bearer ya29.a0AfB_private-token", "Bearer"),
        ("c2VjcmV0", "Authorization: Basic c2VjcmV0", "Authorization"),
        ("secret-value", "refresh_token=secret-value", "refresh_token"),
        ("Personal Folder", r"no space at C:\Personal Folder\Emails", "no space"),
        ("PrivateShare", r"failed at \\server\PrivateShare\mail", "failed"),
        ("Alexs", "no space at /storage/emulated/0/Alexs Archive/Emails", "no space"),
        ("Secret", "file:///C:/Secret/archive.eml", "file://"),
        (
            "18c9a1b2c3d4e5f60718293a4b5c6d7e8f90",
            "failed for 18c9a1b2c3d4e5f60718293a4b5c6d7e8f90",
            "failed",
        ),
    ],
)
def test_private_diagnostic_values_are_redacted(
    private: str, text: str, survives: str
) -> None:
    output = redact(text)
    assert private.casefold() not in output.casefold()
    assert survives in output


def test_ordinary_status_and_counts_survive() -> None:
    text = "Export stopped after batch 12 with HTTP 429, after 2431 of 9056 messages"
    assert redact(text) == text


def test_blank_and_runaway_text_are_bounded() -> None:
    assert redact(None) == ""
    assert redact("   ") == ""
    assert len(redact("x" * 10_000)) <= MAX_LENGTH


def test_account_masking_preserves_only_provider() -> None:
    assert mask_account("person@gmail.com") == "•••@gmail.com"
    assert mask_account(None) == "not connected"
    assert mask_account("malformed") == "•••"
