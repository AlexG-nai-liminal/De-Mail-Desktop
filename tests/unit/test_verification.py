import hashlib
from pathlib import Path

from demail.archive.verification import VerificationResult, verify_file


def test_verification_reopens_and_matches_size_and_hash(tmp_path: Path) -> None:
    data = b"exact archive bytes"
    path = tmp_path / "message.eml"
    path.write_bytes(data)
    result = verify_file(path, len(data), hashlib.sha256(data).hexdigest())
    assert result.result == VerificationResult.VERIFIED


def test_missing_file_is_distinct_from_mismatch(tmp_path: Path) -> None:
    result = verify_file(tmp_path / "missing.eml", 1, "00" * 32)
    assert result.result == VerificationResult.MISSING


def test_size_mismatch_wins_before_hash_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "message.eml"
    path.write_bytes(b"changed length")
    result = verify_file(path, 2, "00" * 32)
    assert result.result == VerificationResult.SIZE_MISMATCH


def test_equal_size_corruption_is_hash_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "message.eml"
    path.write_bytes(b"bad")
    result = verify_file(path, 3, hashlib.sha256(b"old").hexdigest())
    assert result.result == VerificationResult.HASH_MISMATCH

