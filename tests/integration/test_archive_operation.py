import base64
import io
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from demail.archive.gmail_pipeline import archive_raw_response
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
            "a": b"From: a@example.com\r\n\r\none",
            "b": b"From: b@example.com\r\n\r\ntwo",
        }
    )
    engine, operation_id = prepare(repository, gmail, tmp_path / "chosen")
    engine.run(operation_id)
    operation = repository.operation(operation_id)
    assert operation is not None
    assert operation["status"] == "VERIFIED"
    assert operation["selected_count"] == operation["exported_count"] == 2
    assert operation["verified_count"] == 2
    folder = tmp_path / "chosen" / "de-Mail Archive" / operation["archive_folder_name"]
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schemaVersion"] == 1
    assert manifest["verification"]["status"] == "VERIFIED"
    assert manifest["archive"]["counts"] == {
        "selected": 2,
        "exported": 2,
        "failed": 0,
        "verified": 2,
    }
    assert [message["gmailMessageId"] for message in manifest["messages"]] == ["a", "b"]
    assert not (folder / "manifest.json.partial").exists()


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
    assert operation["worker_token"] is None
