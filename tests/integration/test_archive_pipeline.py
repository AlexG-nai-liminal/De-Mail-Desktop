import base64
import hashlib
import io
from pathlib import Path

import pytest

from demail.archive.atomic_file import AtomicArchiveFile
from demail.archive.gmail_pipeline import archive_raw_response


def response(data: bytes, message_id: str = "abc") -> io.StringIO:
    raw = base64.urlsafe_b64encode(data).decode().rstrip("=")
    return io.StringIO(f'{{"id":"{message_id}","raw":"{raw}"}}')


def test_pipeline_hashes_exact_published_bytes(tmp_path: Path) -> None:
    message = b"From: alice@example.com\r\nSubject: hi\r\n\r\nBody\x00\xff"
    final = tmp_path / "messages" / "abc.eml"
    result = archive_raw_response(response(message), final)
    assert final.read_bytes() == message
    assert result.file.byte_size == len(message)
    assert result.file.sha256 == hashlib.sha256(message).hexdigest()
    assert result.envelope.id == "abc"
    assert not final.with_name("abc.eml.partial").exists()


def test_retry_replaces_same_file_without_duplicate(tmp_path: Path) -> None:
    final = tmp_path / "abc.eml"
    archive_raw_response(response(b"first"), final)
    archive_raw_response(response(b"second"), final)
    assert final.read_bytes() == b"second"
    assert [path.name for path in tmp_path.iterdir()] == ["abc.eml"]


def test_parse_failure_keeps_existing_final_and_removes_partial(tmp_path: Path) -> None:
    final = tmp_path / "abc.eml"
    final.write_bytes(b"previous verified bytes")
    with pytest.raises(ValueError):
        archive_raw_response(io.StringIO('{"raw":"YWJj%%%"}'), final)
    assert final.read_bytes() == b"previous verified bytes"
    assert not final.with_name("abc.eml.partial").exists()


def test_missing_raw_is_not_published(tmp_path: Path) -> None:
    final = tmp_path / "abc.eml"
    with pytest.raises(ValueError, match="did not contain"):
        archive_raw_response(io.StringIO('{"id":"abc"}'), final)
    assert not final.exists()


def test_interrupted_partial_is_truncated_on_resume(tmp_path: Path) -> None:
    final = tmp_path / "abc.eml"
    partial = tmp_path / "abc.eml.partial"
    partial.write_bytes(b"interrupted garbage that must not survive")
    archive_raw_response(response(b"complete"), final)
    assert final.read_bytes() == b"complete"
    assert not partial.exists()


def test_exception_inside_atomic_writer_never_promotes(tmp_path: Path) -> None:
    final = tmp_path / "abc.eml"
    with pytest.raises(OSError, match="simulated disk failure"), AtomicArchiveFile(final) as target:
        target.write(b"partial")
        raise OSError("simulated disk failure")
    assert not final.exists()
    assert not final.with_name("abc.eml.partial").exists()
