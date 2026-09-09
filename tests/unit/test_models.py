from datetime import UTC, datetime

import pytest

from demail.domain.models import ArchiveMessage, ArchiveOperation, OperationStatus


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

