import base64
import io
import json

import pytest

from demail.gmail.raw_message import GmailResponseError, read_raw_message


def encoded(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


class BoundedTextReader(io.StringIO):
    def read(self, size: int = -1) -> str:
        assert 0 < size <= 8192
        return super().read(size)


def test_extracts_metadata_and_raw_bytes_in_any_field_order() -> None:
    message = b"Subject: hi\r\n\r\nhello"
    response = json.dumps(
        {
            "unknown": {"nested": [1, {"value": "ignored"}]},
            "raw": encoded(message),
            "id": "abc",
            "threadId": "thread",
            "internalDate": "1673787600000",
            "sizeEstimate": 22,
            "historyId": "99",
            "snippet": "hello \u2603",
            "labelIds": ["INBOX", "Label_1"],
        }
    )
    output = io.BytesIO()
    envelope = read_raw_message(BoundedTextReader(response), output)
    assert output.getvalue() == message
    assert envelope.id == "abc"
    assert envelope.thread_id == "thread"
    assert envelope.internal_date_ms == 1_673_787_600_000
    assert envelope.size_estimate == 22
    assert envelope.label_ids == ("INBOX", "Label_1")
    assert envelope.raw_present


def test_large_body_is_consumed_with_bounded_source_reads() -> None:
    message = b"x" * 2_000_000
    response = '{"id":"large","raw":"' + encoded(message) + '"}'
    output = io.BytesIO()
    read_raw_message(BoundedTextReader(response), output)
    assert output.getvalue() == message


@pytest.mark.parametrize(
    "response",
    [
        "",
        "[]",
        '{"raw":"unterminated}',
        '{"raw":"YWJj\\n"}',
        '{"raw":"YWJj","raw":"YWJj"}',
        '{"raw":"YWJj"} trailing',
        '{"labelIds":["A"}',
    ],
)
def test_malformed_json_is_rejected(response: str) -> None:
    with pytest.raises((GmailResponseError, ValueError)):
        read_raw_message(io.StringIO(response), io.BytesIO())


def test_missing_or_nonnumeric_optional_metadata_is_safe() -> None:
    envelope = read_raw_message(
        io.StringIO('{"internalDate":"not-a-number","sizeEstimate":null}'), io.BytesIO()
    )
    assert envelope.internal_date_ms is None
    assert envelope.size_estimate is None
    assert not envelope.raw_present


def test_duplicate_identity_field_is_rejected() -> None:
    with pytest.raises(GmailResponseError, match="duplicate id field"):
        read_raw_message(
            io.StringIO('{"id":"first","id":"second","raw":"YQ"}'), io.BytesIO()
        )
