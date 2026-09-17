import json
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime

from demail.archive.eml_scanner import EmlScan
from demail.domain.selection import SelectionCriteria
from demail.gmail.client import GmailMessageMetadata, GmailMessageRef

from .database import Database


class ArchiveRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create_operation(
        self,
        *,
        account_email: str,
        account_messages_total: int,
        account_threads_total: int | None = None,
        criteria: SelectionCriteria,
        gmail_query: str | None,
        gmail_label_ids: tuple[str, ...],
        destination_path: str,
        archive_folder_name: str,
        messages: Sequence[GmailMessageRef],
        created_at: datetime,
    ) -> int:
        operation = {
            "created_at": created_at.astimezone(UTC).isoformat(),
            "account_email": account_email,
            "account_messages_total": account_messages_total,
            "account_threads_total": account_threads_total,
            "selection_json": json.dumps(
                {
                    "startDate": criteria.start_date,
                    "endDate": criteria.end_date,
                    "dateRanges": [
                        {"startDate": start, "endDate": end}
                        for start, end in criteria.date_ranges
                    ],
                    "labelId": criteria.label_id,
                    "labelName": criteria.label_name,
                    "sender": criteria.sender,
                    "searchQuery": criteria.search_query,
                    "includeSpamAndTrash": criteria.include_spam_and_trash,
                    "explicitMessageIds": list(criteria.explicit_message_ids),
                },
                separators=(",", ":"),
            ),
            "selection_description": criteria.describe(),
            "gmail_query": gmail_query,
            "gmail_label_ids": json.dumps(gmail_label_ids),
            "destination_path": destination_path,
            "archive_folder_name": archive_folder_name,
            "selected_count": len(messages),
        }
        with self.database.transaction() as connection:
            columns = tuple(operation)
            cursor = connection.execute(
                f"INSERT INTO archive_operations ({', '.join(columns)}) VALUES "
                f"({', '.join('?' for _ in columns)})",
                tuple(operation.values()),
            )
            operation_id = int(cursor.lastrowid)
            connection.executemany(
                "INSERT INTO archive_messages "
                "(operation_id, gmail_message_id, gmail_thread_id) VALUES (?, ?, ?)",
                ((operation_id, item.id, item.thread_id) for item in messages),
            )
        return operation_id

    def acquire_worker(
        self, operation_id: int, token: str, stale_before: datetime
    ) -> bool:
        with self.database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE archive_operations SET worker_token = ?, worker_acquired_at = ? "
                "WHERE id = ? AND (worker_token IS NULL OR worker_acquired_at < ?)",
                (token, datetime.now(UTC).isoformat(), operation_id, stale_before.isoformat()),
            )
            return cursor.rowcount == 1

    def release_worker(self, operation_id: int, token: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE archive_operations SET worker_token = NULL, worker_acquired_at = NULL "
                "WHERE id = ? AND worker_token = ?",
                (operation_id, token),
            )

    def operation(self, operation_id: int) -> sqlite3.Row | None:
        with self.database.connect() as connection:
            return connection.execute(
                "SELECT * FROM archive_operations WHERE id = ?", (operation_id,)
            ).fetchone()

    def operations(self, limit: int = 100) -> list[sqlite3.Row]:
        if not 1 <= limit <= 500:
            raise ValueError("History limit must be from 1 to 500")
        with self.database.connect() as connection:
            return connection.execute(
                "SELECT * FROM archive_operations ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()

    def pending_messages(self, operation_id: int) -> list[sqlite3.Row]:
        with self.database.connect() as connection:
            return connection.execute(
                "SELECT * FROM archive_messages WHERE operation_id = ? AND ("
                "(exported = 0 AND verification IN ('PENDING','EXPORT_FAILED')) OR "
                "verification IN ('MISSING','UNREADABLE','SIZE_MISMATCH','HASH_MISMATCH')"
                ") ORDER BY gmail_message_id",
                (operation_id,),
            ).fetchall()

    def messages(self, operation_id: int) -> list[sqlite3.Row]:
        with self.database.connect() as connection:
            return connection.execute(
                "SELECT * FROM archive_messages WHERE operation_id = ? ORDER BY gmail_message_id",
                (operation_id,),
            ).fetchall()

    def record_metadata(
        self, operation_id: int, metadata: GmailMessageMetadata, file_name: str
    ) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE archive_messages SET gmail_thread_id = ?, subject = ?, sender = ?, "
                "internal_date_ms = ?, label_ids = ?, file_name = ?, relative_path = ? "
                "WHERE operation_id = ? AND gmail_message_id = ?",
                (
                    metadata.thread_id,
                    metadata.subject,
                    metadata.sender,
                    metadata.internal_date_ms,
                    json.dumps(metadata.label_ids),
                    file_name,
                    f"messages/{file_name}",
                    operation_id,
                    metadata.id,
                ),
            )

    def mark_exported(
        self, operation_id: int, message_id: str, byte_size: int, sha256: str
    ) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE archive_messages SET byte_size = ?, sha256 = ?, exported = 1, "
                "verification = 'PENDING', failure_stage = NULL, failure_message = NULL, "
                "attempts = attempts + 1 WHERE operation_id = ? AND gmail_message_id = ?",
                (byte_size, sha256, operation_id, message_id),
            )

    def record_eml_scan(
        self, operation_id: int, message_id: str, scan: EmlScan
    ) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE archive_messages SET subject = COALESCE(?, subject), "
                "sender = COALESCE(?, sender), recipients = ?, "
                "cc_recipients = ?, bcc_recipients = ?, date_header = ?, "
                "rfc822_message_id = ?, attachment_count = ?, "
                "inline_attachment_count = ?, attachment_names = ? "
                "WHERE operation_id = ? AND gmail_message_id = ?",
                (
                    scan.subject,
                    scan.sender,
                    scan.recipients,
                    scan.cc_recipients,
                    scan.bcc_recipients,
                    scan.date_header,
                    scan.rfc822_message_id,
                    scan.attachment_count,
                    scan.inline_attachment_count,
                    json.dumps(scan.attachment_names),
                    operation_id,
                    message_id,
                ),
            )

    def mark_export_failed(self, operation_id: int, message_id: str, reason: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE archive_messages SET exported = 0, verification = 'EXPORT_FAILED', "
                "failure_stage = 'download', failure_message = ?, attempts = attempts + 1 "
                "WHERE operation_id = ? AND gmail_message_id = ?",
                (reason, operation_id, message_id),
            )

    def mark_verification(self, operation_id: int, message_id: str, result: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE archive_messages SET verification = ? "
                "WHERE operation_id = ? AND gmail_message_id = ?",
                (result, operation_id, message_id),
            )

    def set_status(self, operation_id: int, status: str, detail: str | None = None) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE archive_operations SET status = ?, status_detail = ? WHERE id = ?",
                (status, detail, operation_id),
            )

    def refresh_counts(self, operation_id: int) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE archive_operations SET "
                "exported_count = (SELECT COUNT(*) FROM archive_messages m "
                "WHERE m.operation_id = ? AND m.exported = 1), "
                "verified_count = (SELECT COUNT(*) FROM archive_messages m "
                "WHERE m.operation_id = ? AND m.verification = 'VERIFIED'), "
                "failed_count = (SELECT COUNT(*) FROM archive_messages m "
                "WHERE m.operation_id = ? AND m.verification NOT IN ('PENDING','VERIFIED')), "
                "total_bytes = (SELECT COALESCE(SUM(byte_size), 0) FROM archive_messages m "
                "WHERE m.operation_id = ? AND m.exported = 1), "
                "attachment_count = (SELECT COALESCE(SUM(attachment_count), 0) "
                "FROM archive_messages m WHERE m.operation_id = ? AND m.exported = 1), "
                "inline_attachment_count = (SELECT COALESCE(SUM(inline_attachment_count), 0) "
                "FROM archive_messages m WHERE m.operation_id = ? AND m.exported = 1) WHERE id = ?",
                (operation_id,) * 7,
            )

    def finalize_counts(
        self, operation_id: int, status: str, completed_at: datetime | None = None
    ) -> None:
        now = (completed_at or datetime.now(UTC)).astimezone(UTC).isoformat()
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE archive_operations SET "
                "exported_count = (SELECT COUNT(*) FROM archive_messages m "
                "WHERE m.operation_id = ? AND m.exported = 1), "
                "verified_count = (SELECT COUNT(*) FROM archive_messages m "
                "WHERE m.operation_id = ? AND m.verification = 'VERIFIED'), "
                "failed_count = (SELECT COUNT(*) FROM archive_messages m "
                "WHERE m.operation_id = ? AND m.verification NOT IN ('PENDING','VERIFIED')), "
                "total_bytes = (SELECT COALESCE(SUM(byte_size), 0) FROM archive_messages m "
                "WHERE m.operation_id = ? AND m.exported = 1), "
                "attachment_count = (SELECT COALESCE(SUM(attachment_count), 0) "
                "FROM archive_messages m WHERE m.operation_id = ? AND m.exported = 1), "
                "inline_attachment_count = (SELECT COALESCE(SUM(inline_attachment_count), 0) "
                "FROM archive_messages m WHERE m.operation_id = ? AND m.exported = 1), "
                "status = ?, completed_at = ?, verified_at = ? WHERE id = ?",
                (
                    operation_id,
                    operation_id,
                    operation_id,
                    operation_id,
                    operation_id,
                    operation_id,
                    status,
                    now,
                    now,
                    operation_id,
                ),
            )
