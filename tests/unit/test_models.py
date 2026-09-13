from datetime import UTC, datetime

import pytest

from demail.domain.models import (
    ArchiveHistoryItem,
    ArchiveMessage,
    ArchiveOperation,
    OperationStatus,
)


def test_operation_status_lifecycle_categories() -> None:
    assert not OperationStatus.EXPORTING.is_terminal
    assert OperationStatus.VERIFIED.is_terminal
    assert OperationStatus.CANCELLED.is_terminal


def test_domain_models_reject_unsafe_counts_and_blank_identity() -> None:
    with pytest.raises(ValueError, match="negative"):
        ArchiveMessage("message-id", byte_size=-1)
    with pytest.raises(ValueError, match="blank"):
        ArchiveMessage(" ")
    with pytest.raises(ValueError, match="selected_count"):
        ArchiveOperation(
            account_email="a@example.com",
            selection_json="{}",
            selection_description="All mail",
            destination_path=r"C:\Archives",
            archive_folder_name="archive",
            selected_count=-1,
            created_at=datetime.now(UTC),
        )


def history_item(**changes) -> ArchiveHistoryItem:
    values = {
        "operation_id": 1,
        "created_at": "2026-09-12T10:00:00+00:00",
        "account_email": "archive@example.com",
        "selection_description": "All mail",
        "destination_path": r"C:\Archives",
        "archive_folder_name": "operation",
        "status": OperationStatus.PARTIAL,
        "selected_count": 2,
        "exported_count": 1,
        "verified_count": 1,
        "failed_count": 1,
        "total_bytes": 100,
    }
    values.update(changes)
    return ArchiveHistoryItem(**values)


def test_history_resume_rules_and_archive_path() -> None:
    item = history_item()
    assert item.can_resume
    assert item.archive_path.name == "operation"
    assert not history_item(
        status=OperationStatus.VERIFIED,
        exported_count=2,
        verified_count=2,
        failed_count=0,
    ).can_resume
    assert not history_item(worker_locked=True).can_resume


@pytest.mark.parametrize(
    "changes",
    [
        {"operation_id": 0},
        {"account_email": " "},
        {"destination_path": ""},
        {"archive_folder_name": " "},
        {"selected_count": -1},
        {"selected_count": 1, "exported_count": 2},
        {"exported_count": 1, "verified_count": 2},
    ],
)
def test_history_rejects_impossible_counts(changes: dict) -> None:
    with pytest.raises(ValueError):
        history_item(**changes)
