import hashlib
import io
from pathlib import Path

import pytest

from demail.archive.hashing import hash_file, hash_stream


class BoundedReader(io.BytesIO):
    def __init__(self, data: bytes, maximum: int) -> None:
        super().__init__(data)
        self.maximum = maximum
        self.calls = 0

    def read(self, size: int = -1) -> bytes:
        assert 0 < size <= self.maximum
        self.calls += 1
        return super().read(size)


def test_hash_stream_reports_exact_bytes_and_digest() -> None:
    content = b"abc" * 100_000
    stream = BoundedReader(content, 4096)
    result = hash_stream(stream, chunk_size=4096)
    assert result.byte_size == len(content)
    assert result.sha256 == hashlib.sha256(content).hexdigest()
    assert stream.calls > 2


def test_empty_stream_has_standard_sha256() -> None:
    assert hash_stream(io.BytesIO()).sha256 == hashlib.sha256(b"").hexdigest()


def test_nonpositive_chunk_size_is_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        hash_stream(io.BytesIO(b"data"), chunk_size=0)


def test_file_is_read_from_disk(tmp_path: Path) -> None:
    path = tmp_path / "message.eml"
    path.write_bytes(b"From: alice@example.com\r\n\r\nBody")
    assert hash_file(path).byte_size == path.stat().st_size


def test_missing_file_failure_is_not_hidden(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        hash_file(tmp_path / "missing.eml")

