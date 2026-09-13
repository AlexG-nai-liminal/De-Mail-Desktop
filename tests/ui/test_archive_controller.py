from pathlib import Path

import pytest

from demail.domain.selection import SelectionCriteria
from demail.jobs.archive_operation import ArchiveProgress
from demail.ui.archive import ArchiveController


class ImmediatePool:
    def start(self, task) -> None:
        task.run()


class Repository:
    def operation(self, operation_id: int):
        return {
            "destination_path": "C:/archive",
            "archive_folder_name": "operation",
            "status": "VERIFIED",
            "selected_count": 1,
            "exported_count": 1,
            "verified_count": 1,
            "failed_count": 0,
            "total_bytes": 100,
        }


class Engine:
    def __init__(self) -> None:
        self.repository = Repository()

    def prepare(self, criteria: SelectionCriteria, destination: Path) -> int:
        assert criteria.search_query == "receipt"
        assert destination == Path("C:/chosen")
        return 12

    def run(self, operation_id: int, progress=None) -> None:
        assert operation_id == 12
        progress(ArchiveProgress("export", 1, 1))


def test_controller_runs_archive_and_returns_safe_summary(qtbot) -> None:
    controller = ArchiveController(Engine, ImmediatePool())
    progress = []
    controller.progress.connect(progress.append)
    with qtbot.waitSignal(controller.completed) as completed:
        controller.start(SelectionCriteria(search_query="receipt"), "C:/chosen")
    assert progress == [ArchiveProgress("export", 1, 1)]
    assert completed.args[0].operation_id == 12
    assert completed.args[0].verified_count == 1


def test_controller_redacts_unexpected_archive_failure(qtbot) -> None:
    class BrokenEngine(Engine):
        def prepare(self, criteria: SelectionCriteria, destination: Path) -> int:
            raise OSError("C:/private/customer-name secret")

    controller = ArchiveController(BrokenEngine, ImmediatePool())
    with qtbot.waitSignal(controller.failed) as failed:
        controller.start(SelectionCriteria(), "C:/chosen")
    assert "private" not in failed.args[0]
    assert "secret" not in failed.args[0]


def test_controller_resumes_existing_operation_without_preparing_again(qtbot) -> None:
    class ResumeEngine(Engine):
        def prepare(self, criteria: SelectionCriteria, destination: Path) -> int:
            raise AssertionError("resume must not materialize a new selection")

    controller = ArchiveController(ResumeEngine, ImmediatePool())
    with qtbot.waitSignal(controller.completed) as completed:
        controller.resume(12)
    assert completed.args[0].operation_id == 12


def test_controller_rejects_invalid_resume_identity() -> None:
    controller = ArchiveController(Engine, ImmediatePool())
    with pytest.raises(ValueError, match="positive"):
        controller.resume(0)
