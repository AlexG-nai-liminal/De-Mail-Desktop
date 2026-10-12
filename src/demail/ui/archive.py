"""Background controller for archive preparation, export, and verification."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Protocol

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from demail.domain.selection import SelectionCriteria
from demail.jobs.archive_operation import ArchiveProgress
from demail.jobs.failures import explain_failure


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
    detail: str = ""
    unresolved: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.operation_id <= 0 or any(value < 0 for value in (
            self.selected_count, self.exported_count, self.verified_count,
            self.failed_count, self.total_bytes,
        )):
            raise ValueError("Archive result identity and counts are invalid.")
        if self.verified_count > self.exported_count or self.exported_count > self.selected_count:
            raise ValueError("Archive result counts are inconsistent.")
        if self.status == "VERIFIED" and (
            self.selected_count != self.verified_count or self.failed_count
        ):
            raise ValueError("Verified result must account for every selected message.")


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
        verification_only: bool = False,
    ) -> None:
        super().__init__()
        self.engine_factory = engine_factory
        self.criteria = criteria
        self.destination = destination
        self.operation_id = operation_id
        self.verification_only = verification_only
        self.pause_event = Event()
        self.signals = _ArchiveSignals()

    def run(self) -> None:
        try:
            engine = self.engine_factory()
            if hasattr(engine, "set_pause_event"):
                engine.set_pause_event(self.pause_event)
            if self.operation_id is None:
                if self.criteria is None or self.destination is None:
                    raise ValueError("New archive work is incomplete.")
                operation_id = engine.prepare(self.criteria, self.destination)
            else:
                operation_id = self.operation_id
            if self.verification_only:
                engine.verify_existing(operation_id, self.signals.progress.emit)
            else:
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
                    detail=operation.get("status_detail", "") or ""
                    if isinstance(operation, dict)
                    else operation["status_detail"] or "",
                    unresolved=tuple(
                        f"{row['gmail_message_id']}: {row['verification']} "
                        f"{row['failure_message'] or ''}"
                        for row in engine.repository.messages(operation_id)
                        if row["verification"] != "VERIFIED"
                    ) if hasattr(engine.repository, "messages") else (),
                )
            )
        except Exception as error:
            self.signals.failed.emit(explain_failure(error))


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
        self._require_idle()
        task = _ArchiveWork(self.engine_factory, criteria, Path(destination))
        self._submit(task)

    def resume(self, operation_id: int) -> None:
        self._require_idle()
        if operation_id <= 0:
            raise ValueError("Archive operation ID must be positive.")
        self._submit(_ArchiveWork(self.engine_factory, operation_id=operation_id))

    def verify_existing(self, operation_id: int) -> None:
        self._require_idle()
        if operation_id <= 0:
            raise ValueError("Archive operation ID must be positive.")
        self._submit(_ArchiveWork(
            self.engine_factory, operation_id=operation_id, verification_only=True
        ))

    def pause(self) -> None:
        for task in self._tasks:
            task.pause_event.set()

    def _require_idle(self) -> None:
        if self._tasks:
            raise RuntimeError("An archive operation is already running.")

    @property
    def busy(self) -> bool:
        return bool(self._tasks)

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
