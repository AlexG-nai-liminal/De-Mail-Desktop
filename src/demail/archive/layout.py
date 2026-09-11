from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .filenames import slug

ROOT_FOLDER_NAME = "de-Mail Archive"
MESSAGES_FOLDER_NAME = "messages"


@dataclass(frozen=True, slots=True)
class ArchiveFolders:
    operation: Path
    messages: Path


def create_archive_folders(
    destination: Path, created_at: datetime, description: str
) -> ArchiveFolders:
    root = destination / ROOT_FOLDER_NAME
    root.mkdir(parents=True, exist_ok=True)
    detail = slug(description, 48) or "archive"
    base = f"{created_at:%Y-%m-%d_%H%M} {detail}"
    for suffix in range(1, 10_000):
        name = base if suffix == 1 else f"{base} ({suffix})"
        operation = root / name
        try:
            operation.mkdir()
        except FileExistsError:
            continue
        messages = operation / MESSAGES_FOLDER_NAME
        try:
            messages.mkdir()
        except Exception:
            operation.rmdir()
            raise
        return ArchiveFolders(operation, messages)
    raise FileExistsError("Could not create a unique archive operation folder.")
