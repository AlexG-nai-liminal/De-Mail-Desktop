"""Background controller for archive preparation, export, and verification."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from demail.domain.selection import SelectionCriteria
from demail.jobs.archive_operation import ArchiveProgress


@dataclass(frozen=True, slots=True)
class ArchiveRunResult:
    operation_id: int
    status: str
    selected_count: int
    exported_count: int
    verified_count: int
    failed_count: int
    total_bytes: int
    archive_path: Path


class ArchiveRepositoryReader(Protocol):
    def operation(self, operation_id: int): ...


class ArchiveEngine(Protocol):
    repository: ArchiveRepositoryReader

    def prepare(self, criteria: SelectionCriteria, destination: Path) -> int: ...

    def run(
        self, operation_id: int, progress: Callable[[ArchiveProgress], None] | None = None
    ) -> None: ...


class _ArchiveSignals(QObject):
    progress = Signal(object)
    succeeded = Signal(object)
    failed = Signal(str)


class _ArchiveWork(QRunnable):
    def __init__(
        self,
        engine_factory: Callable[[], ArchiveEngine],
        criteria: SelectionCriteria | None = None,
        destination: Path | None = None,
        operation_id: int | None = None,
    ) -> None:
        super().__init__()
        self.engine_factory = engine_factory
        self.criteria = criteria
        self.destination = destination
        self.operation_id = operation_id
        self.signals = _ArchiveSignals()

    def run(self) -> None:
        try:
            engine = self.engine_factory()
            if self.operation_id is None:
                if self.criteria is None or self.destination is None:
                    raise ValueError("New archive work is incomplete.")
                operation_id = engine.prepare(self.criteria, self.destination)
            else:
                operation_id = self.operation_id
            engine.run(operation_id, self.signals.progress.emit)
            operation = engine.repository.operation(operation_id)
            if operation is None:
                raise RuntimeError("Archive result is unavailable.")
            archive_path = (
                Path(operation["destination_path"])
                / "de-Mail Archive"
                / operation["archive_folder_name"]
            )
            self.signals.succeeded.emit(
                ArchiveRunResult(
                    operation_id=operation_id,
                    status=operation["status"],
                    selected_count=operation["selected_count"],
                    exported_count=operation["exported_count"],
                    verified_count=operation["verified_count"],
                    failed_count=operation["failed_count"],
                    total_bytes=operation["total_bytes"],
                    archive_path=archive_path,
                )
            )
        except Exception:
            self.signals.failed.emit(
                "The archive stopped safely. Completed files remain available for recovery."
            )


class ArchiveController(QObject):
    started = Signal()
    progress = Signal(object)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        engine_factory: Callable[[], ArchiveEngine],
        thread_pool: QThreadPool | None = None,
    ) -> None:
        super().__init__()
        self.engine_factory = engine_factory
        self.thread_pool = thread_pool or QThreadPool.globalInstance()
        self._tasks: set[_ArchiveWork] = set()

    def start(self, criteria: SelectionCriteria, destination: str) -> None:
        task = _ArchiveWork(self.engine_factory, criteria, Path(destination))
        self._submit(task)

    def resume(self, operation_id: int) -> None:
        if operation_id <= 0:
            raise ValueError("Archive operation ID must be positive.")
        self._submit(_ArchiveWork(self.engine_factory, operation_id=operation_id))

    def _submit(self, task: _ArchiveWork) -> None:
        self._tasks.add(task)

        def completed(result: ArchiveRunResult) -> None:
            self._tasks.discard(task)
            self.completed.emit(result)

        def failed(message: str) -> None:
            self._tasks.discard(task)
            self.failed.emit(message)

        task.signals.progress.connect(self.progress.emit)
        task.signals.succeeded.connect(completed)
        task.signals.failed.connect(failed)
        self.started.emit()
        self.thread_pool.start(task)
