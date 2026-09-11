import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from demail.archive.filenames import eml_filename
from demail.archive.layout import create_archive_folders
from demail.archive.manifest import write_manifest
from demail.archive.verification import VerificationResult, verify_file
from demail.domain.selection import SelectionCriteria
from demail.gmail.client import (
    GmailMessageMetadata,
    GmailProfile,
    SelectionResult,
)
from demail.gmail.query import build_query
from demail.persistence.archive_repository import ArchiveRepository


class GmailArchiveSource(Protocol):
    def profile(self) -> GmailProfile: ...

    def resolve_selection(self, criteria: SelectionCriteria) -> SelectionResult: ...

    def metadata(self, message_id: str) -> GmailMessageMetadata: ...

    def download_raw(self, message_id: str, final_path: Path): ...


class OperationAlreadyRunningError(RuntimeError):
    pass


class ArchiveOperationEngine:
    def __init__(self, gmail: GmailArchiveSource, repository: ArchiveRepository) -> None:
        self.gmail = gmail
        self.repository = repository

    def prepare(
        self, criteria: SelectionCriteria, destination: Path, now: datetime | None = None
    ) -> int:
        created_at = now or datetime.now(UTC)
        profile = self.gmail.profile()
        selection = self.gmail.resolve_selection(criteria)
        folders = create_archive_folders(destination, created_at, criteria.describe())
        query = None if criteria.is_manual_selection else build_query(criteria)
        try:
            return self.repository.create_operation(
                account_email=profile.email_address,
                account_messages_total=profile.messages_total,
                criteria=criteria,
                gmail_query=query.q if query else None,
                gmail_label_ids=query.label_ids if query else (),
                destination_path=str(destination),
                archive_folder_name=folders.operation.name,
                messages=selection.messages,
                created_at=created_at,
            )
        except Exception:
            folders.messages.rmdir()
            folders.operation.rmdir()
            raise

    def run(self, operation_id: int) -> None:
        token = uuid.uuid4().hex
        if not self.repository.acquire_worker(
            operation_id, token, datetime.now(UTC) - timedelta(hours=1)
        ):
            raise OperationAlreadyRunningError("This archive operation is already running.")
        try:
            self._run_owned(operation_id)
        finally:
            self.repository.release_worker(operation_id, token)

    def _run_owned(self, operation_id: int) -> None:
        operation = self.repository.operation(operation_id)
        if operation is None:
            raise ValueError("Archive operation does not exist.")
        operation_folder = (
            Path(operation["destination_path"])
            / "de-Mail Archive"
            / operation["archive_folder_name"]
        )
        messages_folder = operation_folder / "messages"
        if not messages_folder.is_dir():
            self.repository.set_status(operation_id, "FAILED", "Archive folder is unavailable.")
            return

        self.repository.set_status(operation_id, "EXPORTING")
        for row in self.repository.pending_messages(operation_id):
            message_id = row["gmail_message_id"]
            try:
                metadata = self.gmail.metadata(message_id)
                if metadata.id != message_id:
                    raise ValueError("Gmail returned a different message identity.")
                file_name = row["file_name"] or eml_filename(
                    metadata.internal_date_ms, metadata.subject, message_id
                )
                self.repository.record_metadata(operation_id, metadata, file_name)
                archived = self.gmail.download_raw(message_id, messages_folder / file_name)
                self.repository.mark_exported(
                    operation_id, message_id, archived.file.byte_size, archived.file.sha256
                )
            except Exception as error:
                self.repository.mark_export_failed(
                    operation_id, message_id, self._safe_failure(error)
                )

        self.repository.set_status(operation_id, "VERIFYING")
        for row in self.repository.messages(operation_id):
            if not row["exported"] or not row["relative_path"] or not row["sha256"]:
                continue
            result = verify_file(
                operation_folder / row["relative_path"], row["byte_size"], row["sha256"]
            )
            self.repository.mark_verification(operation_id, row["gmail_message_id"], result.result)

        rows = self.repository.messages(operation_id)
        verified = sum(row["verification"] == VerificationResult.VERIFIED for row in rows)
        status = "VERIFIED" if verified == operation["selected_count"] == len(rows) else "PARTIAL"
        # Publish the manifest before the database can claim this operation is
        # terminal. A crash can leave a resumable VERIFYING row, but never a
        # VERIFIED row whose manifest was not published.
        self.repository.finalize_counts(operation_id, "VERIFYING")
        provisional = self.repository.operation(operation_id)
        if provisional is None:
            raise RuntimeError("Archive operation disappeared before manifest publication.")
        manifest_operation = dict(provisional)
        manifest_operation["status"] = status
        if status == "VERIFIED":
            manifest_operation["verified_at"] = datetime.now(UTC).isoformat()
        write_manifest(
            operation_folder / "manifest.json",
            manifest_operation,
            self.repository.messages(operation_id),
        )
        self.repository.finalize_counts(operation_id, status)

    @staticmethod
    def _safe_failure(error: Exception) -> str:
        if isinstance(error, OSError):
            return "The message could not be written to the destination."
        return "The message could not be archived safely."
