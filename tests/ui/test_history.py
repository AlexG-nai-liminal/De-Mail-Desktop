from pathlib import Path

from demail.domain.models import ArchiveHistoryItem, OperationStatus
from demail.ui.history import HistoryController, HistoryPage


class ImmediatePool:
    def start(self, task) -> None:
        task.run()


def item(tmp_path: Path, **changes) -> ArchiveHistoryItem:
    archive = tmp_path / "de-Mail Archive" / "operation"
    archive.mkdir(parents=True, exist_ok=True)
    values = {
        "operation_id": 7,
        "created_at": "2026-09-12T10:00:00+00:00",
        "account_email": "archive@example.com",
        "selection_description": "search receipt",
        "destination_path": str(tmp_path),
        "archive_folder_name": "operation",
        "status": OperationStatus.PARTIAL,
        "selected_count": 3,
        "exported_count": 2,
        "verified_count": 2,
        "failed_count": 1,
        "total_bytes": 100,
    }
    values.update(changes)
    return ArchiveHistoryItem(**values)


def test_history_page_shows_counts_and_emits_safe_actions(qtbot, tmp_path: Path) -> None:
    page = HistoryPage()
    qtbot.addWidget(page)
    page.set_items((item(tmp_path),))
    assert page.operations.count() == 1
    assert "Verified: 2" in page.detail.text()
    assert page.resume_button.isEnabled()
    assert page.open_button.isEnabled()
    with qtbot.waitSignal(page.resume_requested) as resume:
        page.resume_button.click()
    assert resume.args == [7]
    with qtbot.waitSignal(page.open_folder_requested) as opened:
        page.open_button.click()
    assert opened.args == [str(tmp_path / "de-Mail Archive" / "operation")]


def test_verified_or_locked_history_cannot_resume(qtbot, tmp_path: Path) -> None:
    page = HistoryPage()
    qtbot.addWidget(page)
    page.set_items(
        (
            item(
                tmp_path,
                status=OperationStatus.VERIFIED,
                exported_count=3,
                verified_count=3,
                failed_count=0,
            ),
        )
    )
    assert not page.resume_button.isEnabled()
    page.set_items((item(tmp_path, worker_locked=True),))
    assert not page.resume_button.isEnabled()
    assert "lock" in page.resume_button.toolTip().lower()


def test_empty_history_and_malformed_date_are_presented_safely(qtbot, tmp_path: Path) -> None:
    page = HistoryPage()
    qtbot.addWidget(page)
    page.set_items(())
    assert page.detail.text() == "No archive operations yet."
    page.set_items((item(tmp_path, created_at="not a date"),))
    assert "Unknown date" in page.operations.item(0).text()


class Repository:
    def operations(self, limit=100):
        return [
            {
                "id": 7,
                "created_at": "2026-09-12T10:00:00+00:00",
                "account_email": "archive@example.com",
                "selection_description": "All mail",
                "destination_path": "C:/archive",
                "archive_folder_name": "operation",
                "status": "PARTIAL",
                "selected_count": 1,
                "exported_count": 0,
                "verified_count": 0,
                "failed_count": 1,
                "total_bytes": 0,
                "worker_token": None,
                "worker_acquired_at": None,
            }
        ]


def test_history_controller_maps_persisted_rows(qtbot) -> None:
    controller = HistoryController(Repository, ImmediatePool())
    with qtbot.waitSignal(controller.loaded) as loaded:
        controller.load()
    assert loaded.args[0][0].operation_id == 7
    assert loaded.args[0][0].status == OperationStatus.PARTIAL


def test_history_controller_redacts_database_failure(qtbot) -> None:
    class BrokenRepository:
        def operations(self, limit=100):
            raise RuntimeError("private@example.com secret")

    controller = HistoryController(BrokenRepository, ImmediatePool())
    with qtbot.waitSignal(controller.failed) as failed:
        controller.load()
    assert "private@example.com" not in failed.args[0]


def test_stale_worker_lock_remains_recoverable(qtbot) -> None:
    class StaleRepository(Repository):
        def operations(self, limit=100):
            rows = super().operations(limit)
            rows[0]["worker_token"] = "orphaned-worker"
            rows[0]["worker_acquired_at"] = "2020-01-01T00:00:00+00:00"
            return rows

    controller = HistoryController(StaleRepository, ImmediatePool())
    with qtbot.waitSignal(controller.loaded) as loaded:
        controller.load()
    assert loaded.args[0][0].can_resume


def test_malformed_worker_timestamp_fails_closed(qtbot) -> None:
    class MalformedRepository(Repository):
        def operations(self, limit=100):
            rows = super().operations(limit)
            rows[0]["worker_token"] = "unknown-worker"
            rows[0]["worker_acquired_at"] = "not-a-time"
            return rows

    controller = HistoryController(MalformedRepository, ImmediatePool())
    with qtbot.waitSignal(controller.loaded) as loaded:
        controller.load()
    assert not loaded.args[0][0].can_resume
