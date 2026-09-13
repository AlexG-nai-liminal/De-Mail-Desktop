from datetime import UTC, datetime
from pathlib import Path

from demail.diagnostics.collector import DiagnosticCollector
from demail.diagnostics.report import render_report
from demail.domain.selection import SelectionCriteria
from demail.gmail.client import GmailMessageRef
from demail.persistence.archive_repository import ArchiveRepository
from demail.persistence.database import Database


def test_real_archive_state_produces_redacted_shape_only_report(tmp_path: Path) -> None:
    database = Database(tmp_path / "state.db")
    database.migrate()
    repository = ArchiveRepository(database)
    operation_id = repository.create_operation(
        account_email="private.person@gmail.com",
        account_messages_total=10,
        criteria=SelectionCriteria(sender="confidential.sender@example.com"),
        gmail_query="from:confidential.sender@example.com",
        gmail_label_ids=(),
        destination_path=str(tmp_path / "Personal Archive Name"),
        archive_folder_name="operation-with-private-description",
        messages=(GmailMessageRef("opaque-message-id", None),),
        created_at=datetime.now(UTC),
    )
    repository.set_status(
        operation_id,
        "FAILED",
        r"failed writing C:\Personal Archive Name\private-subject.eml",
    )
    text = render_report(DiagnosticCollector(repository, tmp_path).collect(stage="History"))
    assert "private.person" not in text
    assert "confidential.sender" not in text
    assert "Personal Archive Name" not in text
    assert "private-subject" not in text
    assert "@gmail.com" in text
    assert "Selected" in text
