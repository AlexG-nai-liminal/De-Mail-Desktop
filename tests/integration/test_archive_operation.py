import base64
import io
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from demail.archive.eml_scanner import EmlScan
from demail.archive.gmail_pipeline import archive_raw_response
from demail.archive.verification import verify_file as actual_verify_file
from demail.auth.token_provider import GoogleAuthorizationError
from demail.domain.selection import SelectionCriteria
from demail.gmail.client import (
    GmailMessageMetadata,
    GmailMessageRef,
    GmailProfile,
    SelectionResult,
)
from demail.jobs.archive_operation import ArchiveOperationEngine, OperationAlreadyRunningError
from demail.persistence.archive_repository import ArchiveRepository
from demail.persistence.database import Database


class FakeGmail:
    def __init__(self, messages: dict[str, bytes], *, fail: set[str] | None = None) -> None:
        self.message_bytes = messages
        self.fail = fail or set()
        self.downloaded: list[str] = []
        self.metadata_calls: list[str] = []

    def profile(self) -> GmailProfile:
        return GmailProfile("archive@example.com", len(self.message_bytes), 1, "history")

    def resolve_selection(self, criteria: SelectionCriteria) -> SelectionResult:
        return SelectionResult(
            tuple(GmailMessageRef(key, f"thread-{key}") for key in self.message_bytes)
        )

    def metadata(self, message_id: str) -> GmailMessageMetadata:
        self.metadata_calls.append(message_id)
        return GmailMessageMetadata(
            id=message_id,
            thread_id=f"thread-{message_id}",
            internal_date_ms=1_673_787_600_000,
            subject=f"Subject {message_id}",
            sender="sender@example.com",
            label_ids=("INBOX",),
        )

    def download_raw(self, message_id: str, final_path: Path):
        self.downloaded.append(message_id)
        if message_id in self.fail:
            raise OSError("C:\\private\\Subject secret.eml could not be written")
        data = self.message_bytes[message_id]
        raw = base64.urlsafe_b64encode(data).decode().rstrip("=")
        return archive_raw_response(
            io.StringIO(f'{{"id":"{message_id}","raw":"{raw}"}}'),
            final_path,
            expected_message_id=message_id,
        )


@pytest.fixture
def repository(tmp_path: Path) -> ArchiveRepository:
    database = Database(tmp_path / "state.db")
    database.migrate()
    return ArchiveRepository(database)


def prepare(
    repository: ArchiveRepository, gmail: FakeGmail, destination: Path
) -> tuple[ArchiveOperationEngine, int]:
    engine = ArchiveOperationEngine(gmail, repository)
    operation_id = engine.prepare(
        SelectionCriteria(search_query="has:attachment"),
        destination,
        now=datetime(2026, 9, 9, 14, 30, tzinfo=UTC),
    )
    return engine, operation_id


def test_prepare_materializes_fixed_selection_before_any_download(
    repository: ArchiveRepository, tmp_path: Path
) -> None:
    gmail = FakeGmail({"a": b"one", "b": b"two"})
    _, operation_id = prepare(repository, gmail, tmp_path / "chosen")
    operation = repository.operation(operation_id)
    assert operation is not None
    assert operation["selected_count"] == 2
    assert len(repository.messages(operation_id)) == 2
    assert gmail.downloaded == []
    folder = tmp_path / "chosen" / "de-Mail Archive" / operation["archive_folder_name"]
    assert (folder / "messages").is_dir()


def test_complete_run_exports_verifies_and_publishes_manifest(
    repository: ArchiveRepository, tmp_path: Path
) -> None:
    gmail = FakeGmail(
        {
            "a": (
                b"Subject: Original A\r\nFrom: a@example.com\r\n"
                b"To: recipient@example.com\r\nDate: Tue, 9 Sep 2026 10:00:00 -0500\r\n"
                b"Message-ID: <a@example.com>\r\n"
                b"Content-Type: multipart/mixed; boundary=x\r\n\r\n"
                b"--x\r\nContent-Type: text/plain\r\n\r\none\r\n"
                b"--x\r\nContent-Type: application/pdf\r\n"
                b"Content-Disposition: attachment; filename=report.pdf\r\n\r\nPDF\r\n"
                b"--x--\r\n"
            ),
            "b": (
                b"From: b@example.com\r\nContent-Type: multipart/related; boundary=y\r\n\r\n"
                b"--y\r\nContent-Type: image/png\r\n"
                b"Content-Disposition: inline; filename=logo.png\r\n\r\nPNG\r\n"
                b"--y--\r\n"
            ),
        }
    )
    engine, operation_id = prepare(repository, gmail, tmp_path / "chosen")
    progress = []
    engine.run(operation_id, progress.append)
    operation = repository.operation(operation_id)
    assert operation is not None
    assert operation["status"] == "VERIFIED"
    assert operation["selected_count"] == operation["exported_count"] == 2
    assert operation["verified_count"] == 2
    folder = tmp_path / "chosen" / "de-Mail Archive" / operation["archive_folder_name"]
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schemaVersion"] == 1
    assert manifest["generator"].startswith("de-Mail Desktop ")
    assert manifest["verification"]["status"] == "VERIFIED"
    assert manifest["archive"]["completedAt"] == operation["completed_at"]
    assert manifest["verification"]["verifiedAt"] == operation["verified_at"]
    assert manifest["archive"]["counts"] == {
        "selected": 2,
        "exported": 2,
        "failed": 0,
        "verified": 2,
    }
    assert manifest["archive"]["account"]["gmailThreadsTotal"] == 1
    assert manifest["archive"]["destination"]["messagesFolderName"] == "messages"
    assert manifest["archive"]["selection"]["criteria"]["searchQuery"] == (
        "has:attachment"
    )
    assert manifest["archive"]["totalAttachments"] == 1
    assert manifest["archive"]["totalInlineAttachments"] == 1
    assert [message["gmailMessageId"] for message in manifest["messages"]] == ["a", "b"]
    first = manifest["messages"][0]
    assert first["subject"] == "Original A"
    assert first["to"] == "recipient@example.com"
    assert first["rfc822MessageId"] == "<a@example.com>"
    assert first["internalDate"] == "2023-01-15T13:00:00Z"
    assert first["attachmentCount"] == 1
    assert first["attachmentNames"] == ["report.pdf"]
    assert '":null' not in (folder / "manifest.json").read_text(encoding="utf-8")
    assert not (folder / "manifest.json.partial").exists()
    assert [(item.phase, item.completed, item.total) for item in progress] == [
        ("export", 0, 2),
        ("export", 1, 2),
        ("export", 2, 2),
        ("verify", 0, 2),
        ("verify", 1, 2),
        ("verify", 2, 2),
    ]


def test_download_failure_keeps_denominator_and_redacts_failure_detail(
    repository: ArchiveRepository, tmp_path: Path
) -> None:
    gmail = FakeGmail({"a": b"one", "b": b"two"}, fail={"b"})
    engine, operation_id = prepare(repository, gmail, tmp_path / "chosen")
    engine.run(operation_id)
    operation = repository.operation(operation_id)
    assert operation is not None
    assert operation["selected_count"] == 2
    assert operation["exported_count"] == 1
    assert operation["verified_count"] == 1
    assert operation["failed_count"] == 1
    assert operation["status"] == "PARTIAL"
    folder = tmp_path / "chosen" / "de-Mail Archive" / operation["archive_folder_name"]
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["verification"]["status"] == "INCOMPLETE"
    assert manifest["verification"]["verifiedAt"] == operation["verified_at"]
    assert manifest["failures"][0]["error"]
    assert manifest["failures"][0]["attempts"] == 1
    failed = next(
        row for row in repository.messages(operation_id) if row["gmail_message_id"] == "b"
    )
    assert "private" not in failed["failure_message"]
    assert "Subject" not in failed["failure_message"]


def test_resume_truncates_interrupted_partial_and_skips_completed_row(
    repository: ArchiveRepository, tmp_path: Path
) -> None:
    gmail = FakeGmail({"a": b"complete a", "b": b"complete b"})
    engine, operation_id = prepare(repository, gmail, tmp_path / "chosen")
    operation = repository.operation(operation_id)
    assert operation is not None
    folder = tmp_path / "chosen" / "de-Mail Archive" / operation["archive_folder_name"]
    metadata = gmail.metadata("a")
    file_name = "a3-01-15_1300_Subject-a_a.eml"
    repository.record_metadata(operation_id, metadata, file_name)
    archived = gmail.download_raw("a", folder / "messages" / file_name)
    repository.mark_exported(operation_id, "a", archived.file.byte_size, archived.file.sha256)
    (folder / "messages" / "orphan.eml.partial").write_bytes(b"old partial")
    gmail.downloaded.clear()
    engine.run(operation_id)
    assert gmail.downloaded == ["b"]
    assert repository.operation(operation_id)["status"] == "VERIFIED"


def test_resume_retries_a_previous_export_failure(
    repository: ArchiveRepository, tmp_path: Path
) -> None:
    gmail = FakeGmail({"a": b"recovered"}, fail={"a"})
    engine, operation_id = prepare(repository, gmail, tmp_path / "chosen")
    engine.run(operation_id)
    assert repository.operation(operation_id)["status"] == "PARTIAL"
    gmail.fail.clear()
    gmail.downloaded.clear()
    engine.run(operation_id)
    assert gmail.downloaded == ["a"]
    assert repository.operation(operation_id)["status"] == "VERIFIED"


def test_destination_failure_pauses_without_failing_every_remaining_message(
    repository: ArchiveRepository, tmp_path: Path
) -> None:
    gmail = FakeGmail({"a": b"one", "b": b"two", "c": b"three"}, fail={"a"})
    engine, operation_id = prepare(repository, gmail, tmp_path / "chosen")
    engine.run(operation_id)
    operation = repository.operation(operation_id)
    assert operation["status"] == "PARTIAL"
    assert "Reconnect" in operation["status_detail"]
    assert gmail.downloaded == ["a"]
    assert [row["verification"] for row in repository.messages(operation_id)] == [
        "EXPORT_FAILED",
        "PENDING",
        "PENDING",
    ]
    gmail.fail.clear()
    gmail.downloaded.clear()
    engine.run(operation_id)
    assert gmail.downloaded == ["a", "b", "c"]
    assert repository.operation(operation_id)["status"] == "VERIFIED"


def test_authorization_failure_pauses_remaining_requests_for_reconnect(
    repository: ArchiveRepository, tmp_path: Path
) -> None:
    class RevokedGmail(FakeGmail):
        def metadata(self, message_id: str) -> GmailMessageMetadata:
            raise GoogleAuthorizationError("revoked credential with private server response")

    gmail = RevokedGmail({"a": b"one", "b": b"two"})
    engine, operation_id = prepare(repository, gmail, tmp_path / "chosen")
    engine.run(operation_id)
    operation = repository.operation(operation_id)
    assert operation["status"] == "PARTIAL"
    assert operation["status_detail"] == (
        "Google authorization is unavailable. Reconnect, then resume."
    )
    rows = repository.messages(operation_id)
    assert [row["verification"] for row in rows] == ["EXPORT_FAILED", "PENDING"]
    assert "private" not in rows[0]["failure_message"]


def test_missing_exported_file_is_redownloaded_on_later_resume(
    repository: ArchiveRepository, tmp_path: Path
) -> None:
    gmail = FakeGmail({"a": b"restored bytes"})
    engine, operation_id = prepare(repository, gmail, tmp_path / "chosen")
    metadata = gmail.metadata("a")
    file_name = "missing_a.eml"
    repository.record_metadata(operation_id, metadata, file_name)
    repository.mark_exported(operation_id, "a", len(b"restored bytes"), "00" * 32)
    engine.run(operation_id)
    assert repository.messages(operation_id)[0]["verification"] == "MISSING"
    gmail.downloaded.clear()
    engine.run(operation_id)
    assert gmail.downloaded == ["a"]
    assert repository.operation(operation_id)["status"] == "VERIFIED"


def test_database_failure_after_file_promotion_is_recoverable_without_duplicates(
    repository: ArchiveRepository, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gmail = FakeGmail({"a": b"one"})
    engine, operation_id = prepare(repository, gmail, tmp_path / "chosen")
    original = repository.mark_exported

    def fail_commit(*args: object) -> None:
        raise sqlite3.OperationalError("simulated state commit failure")

    monkeypatch.setattr(repository, "mark_exported", fail_commit)
    engine.run(operation_id)
    operation = repository.operation(operation_id)
    folder = tmp_path / "chosen" / "de-Mail Archive" / operation["archive_folder_name"]
    assert len(list((folder / "messages").glob("*.eml"))) == 1
    assert repository.messages(operation_id)[0]["verification"] == "EXPORT_FAILED"
    monkeypatch.setattr(repository, "mark_exported", original)
    gmail.downloaded.clear()
    engine.run(operation_id)
    assert gmail.downloaded == ["a"]
    assert len(list((folder / "messages").glob("*.eml"))) == 1
    assert repository.operation(operation_id)["status"] == "VERIFIED"


def test_scan_failure_after_file_promotion_is_retried_safely(
    repository: ArchiveRepository, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gmail = FakeGmail({"a": b"Subject: Original\r\n\r\nbody"})
    engine, operation_id = prepare(repository, gmail, tmp_path / "chosen")
    calls = 0

    def fail_once(path: Path) -> EmlScan:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("simulated scanner read failure")
        from demail.archive.eml_scanner import scan_eml as actual_scan

        return actual_scan(path)

    monkeypatch.setattr("demail.jobs.archive_operation.scan_eml", fail_once)
    engine.run(operation_id)
    assert repository.messages(operation_id)[0]["verification"] == "EXPORT_FAILED"
    gmail.downloaded.clear()
    engine.run(operation_id)
    assert gmail.downloaded == ["a"]
    assert repository.operation(operation_id)["status"] == "VERIFIED"


def test_verification_interruption_leaves_resumable_state_and_releases_worker(
    repository: ArchiveRepository, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gmail = FakeGmail({"a": b"one"})
    engine, operation_id = prepare(repository, gmail, tmp_path / "chosen")

    def interrupt_verification(*args: object) -> None:
        raise OSError("simulated drive disconnect during readback")

    monkeypatch.setattr("demail.jobs.archive_operation.verify_file", interrupt_verification)
    with pytest.raises(OSError, match="drive disconnect"):
        engine.run(operation_id)
    interrupted = repository.operation(operation_id)
    assert interrupted["status"] == "VERIFYING"
    assert interrupted["worker_token"] is None
    monkeypatch.setattr("demail.jobs.archive_operation.verify_file", actual_verify_file)
    gmail.downloaded.clear()
    engine.run(operation_id)
    assert gmail.downloaded == []
    assert repository.operation(operation_id)["status"] == "VERIFIED"


def test_active_worker_prevents_second_worker(
    repository: ArchiveRepository, tmp_path: Path
) -> None:
    gmail = FakeGmail({"a": b"one"})
    engine, operation_id = prepare(repository, gmail, tmp_path / "chosen")
    assert repository.acquire_worker(
        operation_id, "first-worker", datetime.now(UTC) - timedelta(hours=1)
    )
    with pytest.raises(OperationAlreadyRunningError):
        engine.run(operation_id)
    assert gmail.downloaded == []


def test_archive_folder_name_collision_creates_new_operation_folder(
    repository: ArchiveRepository, tmp_path: Path
) -> None:
    destination = tmp_path / "chosen"
    first_engine, first_id = prepare(repository, FakeGmail({"a": b"one"}), destination)
    second_engine, second_id = prepare(repository, FakeGmail({"b": b"two"}), destination)
    del first_engine, second_engine
    first = repository.operation(first_id)
    second = repository.operation(second_id)
    assert first["archive_folder_name"] != second["archive_folder_name"]
    assert second["archive_folder_name"].endswith("(2)")


def test_corrupted_operation_folder_component_fails_closed(
    repository: ArchiveRepository, tmp_path: Path
) -> None:
    gmail = FakeGmail({"a": b"body"})
    engine, operation_id = prepare(repository, gmail, tmp_path / "chosen")
    with repository.database.connect() as connection:
        connection.execute(
            "UPDATE archive_operations SET archive_folder_name = '..' WHERE id = ?",
            (operation_id,),
        )
    engine.run(operation_id)
    assert repository.operation(operation_id)["status"] == "FAILED"
    assert gmail.downloaded == []


def test_corrupted_message_filename_cannot_escape_archive_folder(
    repository: ArchiveRepository, tmp_path: Path
) -> None:
    gmail = FakeGmail({"a": b"body"})
    engine, operation_id = prepare(repository, gmail, tmp_path / "chosen")
    with repository.database.connect() as connection:
        connection.execute(
            "UPDATE archive_messages SET file_name = '../escape.eml', "
            "relative_path = '../escape.eml' WHERE operation_id = ?",
            (operation_id,),
        )
    engine.run(operation_id)
    row = repository.messages(operation_id)[0]
    assert row["verification"] == "EXPORT_FAILED"
    assert not (tmp_path / "chosen" / "de-Mail Archive" / "escape.eml").exists()
    assert gmail.downloaded == []
    operation = repository.operation(operation_id)
    folder = tmp_path / "chosen" / "de-Mail Archive" / operation["archive_folder_name"]
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["messages"][0]["path"] == "messages/"


def test_history_lists_newest_operation_first_and_enforces_limit(
    repository: ArchiveRepository, tmp_path: Path
) -> None:
    first = FakeGmail({"a": b"one"})
    second = FakeGmail({"b": b"two"})
    ArchiveOperationEngine(first, repository).prepare(
        SelectionCriteria(),
        tmp_path,
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )
    newest = ArchiveOperationEngine(second, repository).prepare(
        SelectionCriteria(),
        tmp_path,
        now=datetime(2026, 2, 1, tzinfo=UTC),
    )
    assert [row["id"] for row in repository.operations(limit=1)] == [newest]
    with pytest.raises(ValueError, match="limit"):
        repository.operations(limit=0)


def test_manifest_publication_failure_never_marks_operation_verified(
    repository: ArchiveRepository, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gmail = FakeGmail({"a": b"one"})
    engine, operation_id = prepare(repository, gmail, tmp_path / "chosen")

    def fail_manifest(*args: object, **kwargs: object) -> None:
        raise OSError("simulated manifest disk failure")

    monkeypatch.setattr("demail.jobs.archive_operation.write_manifest", fail_manifest)
    with pytest.raises(OSError, match="manifest disk failure"):
        engine.run(operation_id)
    operation = repository.operation(operation_id)
    assert operation is not None
    assert operation["status"] == "VERIFYING"
    assert operation["completed_at"] is None
    assert operation["worker_token"] is None


def test_database_prepare_failure_removes_untracked_operation_folder(
    repository: ArchiveRepository, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "chosen"
    engine = ArchiveOperationEngine(FakeGmail({"a": b"one"}), repository)

    def fail_create(**kwargs: object) -> int:
        raise sqlite3.OperationalError("simulated commit failure")

    monkeypatch.setattr(repository, "create_operation", fail_create)
    with pytest.raises(sqlite3.OperationalError, match="commit failure"):
        engine.prepare(SelectionCriteria(), destination)
    root = destination / "de-Mail Archive"
    assert not root.exists() or list(root.iterdir()) == []
