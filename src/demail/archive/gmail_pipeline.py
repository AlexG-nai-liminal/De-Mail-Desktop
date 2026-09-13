"""Compose Gmail streaming decode with atomic archive storage."""

from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from demail.gmail.raw_message import RawMessageEnvelope, read_raw_message

from .atomic_file import ArchivedFile, AtomicArchiveFile


@dataclass(frozen=True, slots=True)
class ArchivedRawMessage:
    envelope: RawMessageEnvelope
    file: ArchivedFile


def archive_raw_response(
    source: TextIO, final_path: Path, *, expected_message_id: str | None = None
) -> ArchivedRawMessage:
    """Stream one Gmail response to disk and publish it only when complete."""
    with AtomicArchiveFile(final_path) as target:
        envelope = read_raw_message(source, target)
        if not envelope.raw_present:
            raise ValueError("Gmail response did not contain a raw message body")
        if expected_message_id is not None and envelope.id != expected_message_id:
            raise ValueError("Gmail returned a different message identity than requested")
        archived_file = target.finish()
    return ArchivedRawMessage(envelope=envelope, file=archived_file)
