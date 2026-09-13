"""Background controller for mailbox selection work."""

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from demail.domain.selection import SelectionCriteria
from demail.gmail.selection_service import MailboxEraScanner


class SelectionService(Protocol):
    def labels(self): ...

    def exact_selection(self, criteria: SelectionCriteria): ...

    def recent_messages(self, criteria: SelectionCriteria, limit: int = 100): ...


class _WorkSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str)


class _Work(QRunnable):
    def __init__(self, work: Callable[[], object]) -> None:
        super().__init__()
        self.work = work
        self.signals = _WorkSignals()

    def run(self) -> None:
        try:
            self.signals.succeeded.emit(self.work())
        except Exception:
            self.signals.failed.emit(
                "Gmail selection could not be loaded. Check the connection and try again."
            )


class SelectionController(QObject):
    labels_loaded = Signal(object)
    eras_loaded = Signal(object)
    candidates_loaded = Signal(object)
    exact_count_loaded = Signal(object)
    failed = Signal(str, str)
    started = Signal(str)

    def __init__(
        self,
        service_factory: Callable[[], SelectionService],
        thread_pool: QThreadPool | None = None,
    ) -> None:
        super().__init__()
        self.service_factory = service_factory
        self.thread_pool = thread_pool or QThreadPool.globalInstance()
        self._tasks: set[_Work] = set()

    def load_labels(self) -> None:
        self._submit("labels", lambda: self.service_factory().labels(), self.labels_loaded.emit)

    def scan_eras(self, include_spam_and_trash: bool) -> None:
        def scan():
            service = self.service_factory()
            return MailboxEraScanner(service).scan(include_spam_and_trash).eras

        self._submit("eras", scan, self.eras_loaded.emit)

    def load_candidates(self, criteria: SelectionCriteria) -> None:
        self._submit(
            "candidates",
            lambda: self.service_factory().recent_messages(criteria, 100),
            self.candidates_loaded.emit,
        )

    def calculate_exact_count(self, criteria: SelectionCriteria) -> None:
        self._submit(
            "count",
            lambda: (criteria, self.service_factory().exact_selection(criteria).exact_count),
            self.exact_count_loaded.emit,
        )

    def _submit(
        self, context: str, work: Callable[[], object], success: Callable[[object], None]
    ) -> None:
        task = _Work(work)
        self._tasks.add(task)

        def succeeded(result: object) -> None:
            self._tasks.discard(task)
            success(result)

        def failed(message: str) -> None:
            self._tasks.discard(task)
            self.failed.emit(context, message)

        task.signals.succeeded.connect(succeeded)
        task.signals.failed.connect(failed)
        self.started.emit(context)
        self.thread_pool.start(task)
