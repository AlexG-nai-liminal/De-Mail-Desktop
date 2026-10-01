import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from demail.archive.eml_scanner import scan_eml
from demail.archive.filenames import eml_filename
from demail.archive.layout import create_archive_folders, require_safe_archive_component
from demail.archive.manifest import write_manifest
from demail.archive.verification import VerificationResult, verify_file
from demail.auth.token_provider import GoogleAuthorizationError
from demail.domain.selection import SelectionCriteria
from demail.gmail.client import (
    GmailApiError,
    GmailMessageMetadata,
    GmailProfile,
    SelectionResult,
)
from demail.gmail.query import build_query
from demail.jobs.worker_lock import WorkerLockedError, archive_worker_lock
from demail.persistence.archive_repository import ArchiveRepository


class GmailArchiveSource(Protocol):
    def profile(self) -> GmailProfile: ...

    def resolve_selection(self, criteria: SelectionCriteria) -> SelectionResult: ...

    def metadata(self, message_id: str) -> GmailMessageMetadata: ...

    def download_raw(self, message_id: str, final_path: Path): ...


class OperationAlreadyRunningError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ArchiveProgress:
    phase: str
    completed: int
    total: int

    def __post_init__(self) -> None:
        if self.phase not in {"export", "verify"}:
            raise ValueError("Archive progress phase is invalid.")
        if self.total < 0 or not 0 <= self.completed <= self.total:
            raise ValueError("Archive progress counts are invalid.")


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
                account_threads_total=profile.threads_total,
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

    def run(
        self,
        operation_id: int,
        progress: Callable[[ArchiveProgress], None] | None = None,
    ) -> None:
        try:
            with archive_worker_lock(self.repository.database.path, operation_id):
                self._run_locked(operation_id, progress)
        except WorkerLockedError as error:
            raise OperationAlreadyRunningError(str(error)) from error

    def _run_locked(
        self,
        operation_id: int,
        progress: Callable[[ArchiveProgress], None] | None,
    ) -> None:
        token = uuid.uuid4().hex
        if not self.repository.acquire_worker(
            operation_id, token, datetime.now(UTC) - timedelta(hours=1)
        ):
            raise OperationAlreadyRunningError("This archive operation is already running.")
        try:
            self._run_owned(operation_id, progress)
        finally:
            self.repository.release_worker(operation_id, token)

    def _run_owned(
        self,
        operation_id: int,
        progress: Callable[[ArchiveProgress], None] | None,
    ) -> None:
        operation = self.repository.operation(operation_id)
        if operation is None:
            raise ValueError("Archive operation does not exist.")
        profile = self.gmail.profile()
        if (
            not profile.email_address.strip()
            or profile.email_address.casefold() != str(operation["account_email"]).casefold()
        ):
            raise GoogleAuthorizationError(
                "Reconnect the Google account used to create this archive before resuming."
            )
        try:
            archive_folder_name = require_safe_archive_component(
                str(operation["archive_folder_name"])
            )
        except ValueError:
            self.repository.set_status(operation_id, "FAILED", "Archive state is invalid.")
            return
        operation_folder = (
            Path(operation["destination_path"])
            / "de-Mail Archive"
            / archive_folder_name
        )
        messages_folder = operation_folder / "messages"
        if not messages_folder.is_dir():
            self.repository.set_status(operation_id, "FAILED", "Archive folder is unavailable.")
            return

        total = operation["selected_count"]
        pending = self.repository.pending_messages(operation_id)
        completed_before = total - len(pending)
        self.repository.set_status(operation_id, "EXPORTING")
        if progress:
            progress(ArchiveProgress("export", completed_before, total))
        processed = completed_before
        pause_detail: str | None = None
        for row in pending:
            message_id = row["gmail_message_id"]
            try:
                metadata = self.gmail.metadata(message_id)
                if metadata.id != message_id:
                    raise ValueError("Gmail returned a different message identity.")
                file_name = (
                    require_safe_archive_component(str(row["file_name"]), suffix=".eml")
                    if row["file_name"]
                    else eml_filename(metadata.internal_date_ms, metadata.subject, message_id)
                )
                self.repository.record_metadata(operation_id, metadata, file_name)
                archived = self.gmail.download_raw(message_id, messages_folder / file_name)
                scan = scan_eml(archived.file.path)
                self.repository.record_eml_scan(operation_id, message_id, scan)
                self.repository.mark_exported(
                    operation_id, message_id, archived.file.byte_size, archived.file.sha256
                )
            except Exception as error:
                self.repository.mark_export_failed(
                    operation_id, message_id, self._safe_failure(error)
                )
                pause_detail = self._pause_detail(error)
            processed += 1
            if progress:
                progress(ArchiveProgress("export", min(processed, total), total))
            if pause_detail:
                break

        self.repository.set_status(operation_id, "VERIFYING")
        rows = self.repository.messages(operation_id)
        if progress:
            progress(ArchiveProgress("verify", 0, total))
        for processed, row in enumerate(rows, start=1):
            if row["exported"] and row["sha256"]:
                try:
                    file_name = require_safe_archive_component(
                        str(row["file_name"]), suffix=".eml"
                    )
                except ValueError:
                    self.repository.mark_verification(
                        operation_id, row["gmail_message_id"], VerificationResult.UNREADABLE
                    )
                else:
                    result = verify_file(
                        messages_folder / file_name, row["byte_size"], row["sha256"]
                    )
                    self.repository.mark_verification(
                        operation_id, row["gmail_message_id"], result.result
                    )
            if progress:
                progress(ArchiveProgress("verify", processed, total))

        rows = self.repository.messages(operation_id)
        verified = sum(row["verification"] == VerificationResult.VERIFIED for row in rows)
        status = "VERIFIED" if verified == operation["selected_count"] == len(rows) else "PARTIAL"
        # Publish the manifest before the database can claim this operation is
        # terminal. A crash can leave a resumable VERIFYING row, but never a
        # VERIFIED row whose manifest was not published.
        self.repository.refresh_counts(operation_id)
        provisional = self.repository.operation(operation_id)
        if provisional is None:
            raise RuntimeError("Archive operation disappeared before manifest publication.")
        manifest_operation = dict(provisional)
        manifest_operation["status"] = status
        completed_at = datetime.now(UTC)
        manifest_operation["completed_at"] = completed_at.isoformat()
        manifest_operation["verified_at"] = completed_at.isoformat()
        write_manifest(
            operation_folder / "manifest.json",
            manifest_operation,
            rows,
        )
        self.repository.finalize_counts(operation_id, status, completed_at)
        if pause_detail:
            self.repository.set_status(operation_id, status, pause_detail)

    @staticmethod
    def _safe_failure(error: Exception) -> str:
        if isinstance(error, OSError):
            return "The message could not be written to the destination."
        return "The message could not be archived safely."

    @staticmethod
    def _pause_detail(error: Exception) -> str | None:
        if isinstance(error, GoogleAuthorizationError) or (
            isinstance(error, GmailApiError) and error.status_code in {401, 403}
        ):
            return "Google authorization is unavailable. Reconnect, then resume."
        if isinstance(error, OSError):
            return "The destination became unavailable. Reconnect it, then resume."
        if isinstance(error, GmailApiError) and error.connection_failure:
            return "The Gmail connection was interrupted. Check the network, then resume."
        return None
