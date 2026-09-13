import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

LATEST_SCHEMA_VERSION = 2

MIGRATIONS: dict[int, str] = {
    1: """
    CREATE TABLE archive_operations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        completed_at TEXT,
        verified_at TEXT,
        account_email TEXT NOT NULL,
        account_messages_total INTEGER,
        account_threads_total INTEGER,
        selection_json TEXT NOT NULL,
        selection_description TEXT NOT NULL,
        gmail_query TEXT,
        gmail_label_ids TEXT NOT NULL DEFAULT '[]',
        destination_path TEXT NOT NULL,
        archive_folder_name TEXT NOT NULL,
        selected_count INTEGER NOT NULL CHECK (selected_count >= 0),
        status TEXT NOT NULL DEFAULT 'QUEUED' CHECK (status IN
            ('QUEUED','EXPORTING','VERIFYING','VERIFIED','PARTIAL','FAILED','CANCELLED')),
        status_detail TEXT,
        exported_count INTEGER NOT NULL DEFAULT 0 CHECK (exported_count >= 0),
        failed_count INTEGER NOT NULL DEFAULT 0 CHECK (failed_count >= 0),
        verified_count INTEGER NOT NULL DEFAULT 0 CHECK (verified_count >= 0),
        total_bytes INTEGER NOT NULL DEFAULT 0 CHECK (total_bytes >= 0),
        attachment_count INTEGER NOT NULL DEFAULT 0 CHECK (attachment_count >= 0),
        worker_token TEXT,
        worker_acquired_at TEXT
    );
    CREATE TABLE archive_messages (
        operation_id INTEGER NOT NULL REFERENCES archive_operations(id) ON DELETE CASCADE,
        gmail_message_id TEXT NOT NULL,
        gmail_thread_id TEXT,
        subject TEXT,
        sender TEXT,
        recipients TEXT,
        cc_recipients TEXT,
        bcc_recipients TEXT,
        date_header TEXT,
        internal_date_ms INTEGER,
        rfc822_message_id TEXT,
        label_ids TEXT,
        file_name TEXT,
        relative_path TEXT,
        byte_size INTEGER NOT NULL DEFAULT 0 CHECK (byte_size >= 0),
        sha256 TEXT,
        attachment_count INTEGER NOT NULL DEFAULT 0 CHECK (attachment_count >= 0),
        inline_attachment_count INTEGER NOT NULL DEFAULT 0 CHECK (inline_attachment_count >= 0),
        attachment_names TEXT,
        exported INTEGER NOT NULL DEFAULT 0 CHECK (exported IN (0, 1)),
        verification TEXT NOT NULL DEFAULT 'PENDING' CHECK (verification IN
            ('PENDING','VERIFIED','MISSING','UNREADABLE','SIZE_MISMATCH','HASH_MISMATCH','EXPORT_FAILED')),
        failure_stage TEXT,
        failure_message TEXT,
        attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
        PRIMARY KEY (operation_id, gmail_message_id)
    );
    CREATE INDEX archive_messages_pending
        ON archive_messages(operation_id, exported, verification, gmail_message_id);
    CREATE TABLE archive_destinations (
        path_key TEXT PRIMARY KEY COLLATE NOCASE,
        display_path TEXT NOT NULL,
        last_used_at TEXT NOT NULL
    );
    """,
    2: """
    ALTER TABLE archive_operations ADD COLUMN inline_attachment_count INTEGER NOT NULL
        DEFAULT 0 CHECK (inline_attachment_count >= 0);
    """,
}


class MigrationError(RuntimeError):
    pass


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def migrate(self) -> None:
        with self.connect() as connection:
            current = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if current > LATEST_SCHEMA_VERSION:
                raise MigrationError(
                    f"Database schema {current} is newer than supported schema "
                    f"{LATEST_SCHEMA_VERSION}"
                )
            for version in range(current + 1, LATEST_SCHEMA_VERSION + 1):
                try:
                    connection.executescript(
                        f"BEGIN IMMEDIATE;\n{MIGRATIONS[version]}\n"
                        f"PRAGMA user_version = {version};\nCOMMIT;"
                    )
                except (KeyError, sqlite3.DatabaseError) as error:
                    connection.rollback()
                    raise MigrationError(f"Migration to schema {version} failed") from error

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def create_operation_with_messages(
        self,
        operation: dict[str, object],
        message_ids: Sequence[str],
    ) -> int:
        if len(message_ids) != len(set(message_ids)):
            raise ValueError("message_ids must be unique")
        if operation.get("selected_count") != len(message_ids):
            raise ValueError("selected_count must equal the number of materialized messages")
        columns = tuple(operation)
        placeholders = ", ".join("?" for _ in columns)
        with self.transaction() as connection:
            cursor = connection.execute(
                f"INSERT INTO archive_operations ({', '.join(columns)}) VALUES ({placeholders})",
                tuple(operation[column] for column in columns),
            )
            operation_id = int(cursor.lastrowid)
            connection.executemany(
                "INSERT INTO archive_messages (operation_id, gmail_message_id) VALUES (?, ?)",
                ((operation_id, message_id) for message_id in message_ids),
            )
        return operation_id
