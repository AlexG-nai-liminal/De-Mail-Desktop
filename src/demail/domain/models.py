from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


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

