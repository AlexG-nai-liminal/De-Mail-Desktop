from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path


class OperationStatus(StrEnum):
    QUEUED = "QUEUED"
    EXPORTING = "EXPORTING"
    VERIFYING = "VERIFYING"
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    @property
    def is_terminal(self) -> bool:
        return self in {self.VERIFIED, self.PARTIAL, self.FAILED, self.CANCELLED}


class MessageVerification(StrEnum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    MISSING = "MISSING"
    UNREADABLE = "UNREADABLE"
    SIZE_MISMATCH = "SIZE_MISMATCH"
    HASH_MISMATCH = "HASH_MISMATCH"
    EXPORT_FAILED = "EXPORT_FAILED"


@dataclass(frozen=True, slots=True)
class ArchiveOperation:
    account_email: str
    selection_json: str
    selection_description: str
    destination_path: str
    archive_folder_name: str
    selected_count: int
    created_at: datetime
    gmail_query: str | None = None
    gmail_label_ids: tuple[str, ...] = ()
    status: OperationStatus = OperationStatus.QUEUED

    def __post_init__(self) -> None:
        if self.selected_count < 0:
            raise ValueError("selected_count cannot be negative")
        if not self.account_email.strip():
            raise ValueError("account_email cannot be blank")


@dataclass(frozen=True, slots=True)
class ArchiveMessage:
    gmail_message_id: str
    gmail_thread_id: str | None = None
    subject: str | None = None
    sender: str | None = None
    internal_date_ms: int | None = None
    file_name: str | None = None
    byte_size: int = 0
    sha256: str | None = None
    exported: bool = False
    verification: MessageVerification = MessageVerification.PENDING

    def __post_init__(self) -> None:
        if not self.gmail_message_id.strip():
            raise ValueError("gmail_message_id cannot be blank")
        if self.byte_size < 0:
            raise ValueError("byte_size cannot be negative")


@dataclass(frozen=True, slots=True)
class ArchiveHistoryItem:
    operation_id: int
    created_at: str
    account_email: str
    selection_description: str
    destination_path: str
    archive_folder_name: str
    status: OperationStatus
    selected_count: int
    exported_count: int
    verified_count: int
    failed_count: int
    total_bytes: int
    worker_locked: bool = False

    def __post_init__(self) -> None:
        if self.operation_id <= 0:
            raise ValueError("Archive operation ID must be positive")
        if not self.account_email.strip():
            raise ValueError("Archive history account cannot be blank")
        if not self.destination_path.strip() or not self.archive_folder_name.strip():
            raise ValueError("Archive history path cannot be blank")
        counts = (
            self.selected_count,
            self.exported_count,
            self.verified_count,
            self.failed_count,
            self.total_bytes,
        )
        if any(value < 0 for value in counts):
            raise ValueError("Archive history counts cannot be negative")
        if self.exported_count > self.selected_count:
            raise ValueError("Exported count cannot exceed selected count")
        if self.verified_count > self.exported_count:
            raise ValueError("Verified count cannot exceed exported count")
        if self.status == OperationStatus.VERIFIED and not (
            self.selected_count == self.exported_count == self.verified_count
            and self.failed_count == 0
        ):
            raise ValueError("Verified history must account for every selected message")

    @property
    def archive_path(self) -> Path:
        return Path(self.destination_path) / "de-Mail Archive" / self.archive_folder_name

    @property
    def can_resume(self) -> bool:
        return self.status != OperationStatus.VERIFIED and not self.worker_locked
