from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .filenames import slug

ROOT_FOLDER_NAME = "de-Mail Archive"
MESSAGES_FOLDER_NAME = "messages"
INVALID_WINDOWS_COMPONENT_CHARACTERS = frozenset('<>:"/\\|?*')


@dataclass(frozen=True, slots=True)
class ArchiveFolders:
    operation: Path
    messages: Path


def require_safe_archive_component(value: str, *, suffix: str | None = None) -> str:
    if (
        not value
        or value in {".", ".."}
        or value[-1] in {" ", "."}
        or any(character in INVALID_WINDOWS_COMPONENT_CHARACTERS for character in value)
        or any(ord(character) < 32 for character in value)
        or (suffix is not None and not value.casefold().endswith(suffix.casefold()))
    ):
        raise ValueError("Archive state contains an unsafe path component.")
    return value


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
