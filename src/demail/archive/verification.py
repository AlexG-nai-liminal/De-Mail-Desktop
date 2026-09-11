from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .hashing import hash_file


class VerificationResult(StrEnum):
    VERIFIED = "VERIFIED"
    MISSING = "MISSING"
    UNREADABLE = "UNREADABLE"
    SIZE_MISMATCH = "SIZE_MISMATCH"
    HASH_MISMATCH = "HASH_MISMATCH"


@dataclass(frozen=True, slots=True)
class FileVerification:
    result: VerificationResult
    actual_size: int | None = None
    actual_sha256: str | None = None


def verify_file(path: Path, expected_size: int, expected_sha256: str) -> FileVerification:
    if not path.exists():
        return FileVerification(VerificationResult.MISSING)
    try:
        actual = hash_file(path)
    except OSError:
        return FileVerification(VerificationResult.UNREADABLE)
    if actual.byte_size != expected_size:
        return FileVerification(VerificationResult.SIZE_MISMATCH, actual.byte_size, actual.sha256)
    if actual.sha256.casefold() != expected_sha256.casefold():
        return FileVerification(VerificationResult.HASH_MISMATCH, actual.byte_size, actual.sha256)
    return FileVerification(VerificationResult.VERIFIED, actual.byte_size, actual.sha256)

