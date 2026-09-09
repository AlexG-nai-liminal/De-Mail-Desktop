from collections.abc import Iterator
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO

DEFAULT_CHUNK_SIZE = 64 * 1024


@dataclass(frozen=True, slots=True)
class HashResult:
    byte_size: int
    sha256: str


def _chunks(stream: BinaryIO, chunk_size: int) -> Iterator[bytes]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    while chunk := stream.read(chunk_size):
        yield chunk


def hash_stream(stream: BinaryIO, chunk_size: int = DEFAULT_CHUNK_SIZE) -> HashResult:
    digest = sha256()
    byte_size = 0
    for chunk in _chunks(stream, chunk_size):
        digest.update(chunk)
        byte_size += len(chunk)
    return HashResult(byte_size=byte_size, sha256=digest.hexdigest())


def hash_file(path: Path, chunk_size: int = DEFAULT_CHUNK_SIZE) -> HashResult:
    with path.open("rb") as stream:
        return hash_stream(stream, chunk_size)

