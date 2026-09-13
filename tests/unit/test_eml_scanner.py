from pathlib import Path

import pytest

from demail.archive.eml_scanner import EmlScanner, scan_eml


def scan_bytes(data: bytes, chunk_size: int = 7):
    scanner = EmlScanner()
    for offset in range(0, len(data), chunk_size):
        scanner.write(data[offset : offset + chunk_size])
    return scanner.finish()


def test_extracts_folded_and_encoded_rfc822_headers() -> None:
    result = scan_bytes(
        b"Subject: =?utf-8?Q?Quarterly_=E2=9C=93?=\r\n"
        b"From: Sender <sender@example.com>\r\n"
        b"To: One <one@example.com>,\r\n two@example.com\r\n"
        b"Cc: cc@example.com\r\nBcc: hidden@example.com\r\n"
        b"Date: Tue, 9 Sep 2026 10:00:00 -0500\r\n"
        b"Message-ID: <original@example.com>\r\n\r\nBody"
    )
    assert result.subject == "Quarterly ✓"
    assert result.sender == "Sender <sender@example.com>"
    assert result.recipients == "One <one@example.com>, two@example.com"
    assert result.cc_recipients == "cc@example.com"
    assert result.bcc_recipients == "hidden@example.com"
    assert result.rfc822_message_id == "<original@example.com>"


def test_counts_regular_inline_nested_and_legacy_named_attachments() -> None:
    result = scan_bytes(
        b"Content-Type: multipart/mixed; boundary=outer\r\n\r\n"
        b"--outer\r\nContent-Type: multipart/related; boundary=inner\r\n\r\n"
        b"--inner\r\nContent-Type: text/html\r\n\r\nhello\r\n"
        b"--inner\r\nContent-Type: image/png\r\n"
        b"Content-Disposition: inline; filename=logo.png\r\n\r\nPNG\r\n"
        b"--inner--\r\n--outer\r\nContent-Type: application/pdf\r\n"
        b"Content-Disposition: attachment; filename=report.pdf\r\n\r\nPDF\r\n"
        b"--outer\r\nContent-Type: text/plain; name=legacy.txt\r\n\r\nTXT\r\n"
        b"--outer--\r\n"
    )
    assert result.attachment_count == 2
    assert result.inline_attachment_count == 1
    assert result.attachment_names == ("logo.png", "report.pdf", "legacy.txt")


def test_body_text_that_looks_like_headers_is_not_an_attachment() -> None:
    result = scan_bytes(
        b"Content-Type: text/plain\n\n"
        b"Content-Disposition: attachment; filename=not-real.txt\n"
    )
    assert result.attachment_count == 0
    assert result.attachment_names == ()


def test_decodes_rfc2231_attachment_name() -> None:
    result = scan_bytes(
        b"Content-Type: multipart/mixed; boundary=x\r\n\r\n"
        b"--x\r\nContent-Type: application/octet-stream\r\n"
        b"Content-Disposition: attachment; "
        b"filename*=utf-8''caf%C3%A9.txt\r\n\r\ndata\r\n--x--\r\n"
    )
    assert result.attachment_names == ("café.txt",)


def test_unterminated_multipart_and_header_only_message_are_tolerated() -> None:
    multipart = scan_bytes(
        b"Content-Type: multipart/mixed; boundary=x\n\n"
        b"--x\nContent-Disposition: attachment; filename=a.txt\n\ndata"
    )
    header_only = scan_bytes(b"Subject: No final separator")
    assert multipart.attachment_count == 1
    assert header_only.subject == "No final separator"


def test_scanner_enforces_bounds_and_finish_is_idempotent() -> None:
    scanner = EmlScanner(max_line_length=8, max_headers=1, max_attachment_names=1)
    scanner.write(b"Subject: this line is long\nFrom: ignored@example.com\n\nbody")
    first = scanner.finish()
    assert first.truncated_line_count == 2
    assert first.truncated_header_count == 1
    assert scanner.finish() == first
    with pytest.raises(RuntimeError, match="finished"):
        scanner.write(b"more")


@pytest.mark.parametrize(
    "arguments",
    [
        {"max_line_length": 0},
        {"max_headers": 0},
        {"max_attachment_names": 0},
    ],
)
def test_rejects_invalid_bounds(arguments: dict[str, int]) -> None:
    with pytest.raises(ValueError, match="positive"):
        EmlScanner(**arguments)


def test_scan_eml_rejects_bad_chunk_size_and_propagates_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.eml"
    with pytest.raises(ValueError, match="positive"):
        scan_eml(missing, chunk_size=0)
    with pytest.raises(FileNotFoundError):
        scan_eml(missing)
