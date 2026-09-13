"""Durable archive history presentation and background loading."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from demail.domain.models import ArchiveHistoryItem, OperationStatus

from .components import Card, page_heading


class HistoryRepository(Protocol):
    def operations(self, limit: int = 100): ...


class HistoryPage(QWidget):
    refresh_requested = Signal()
    resume_requested = Signal(int)
    open_folder_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(38, 30, 38, 30)
        layout.setSpacing(22)
        heading, _ = page_heading(
            "History",
            "Your archive operations",
            "Review durable results and resume work without downloading completed messages again.",
        )
        layout.addWidget(heading)
        card = Card()
        controls = QHBoxLayout()
        self.status_label = QLabel("Loading archive history...")
        self.status_label.setObjectName("muted")
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        controls.addWidget(self.status_label)
        controls.addStretch()
        controls.addWidget(self.refresh_button)
        card.layout.addLayout(controls)
        self.operations = QListWidget()
        self.operations.currentItemChanged.connect(self._selection_changed)
        card.layout.addWidget(self.operations)
        self.detail = QLabel("Select an archive operation to see its details.")
        self.detail.setObjectName("muted")
        self.detail.setWordWrap(True)
        card.layout.addWidget(self.detail)
        actions = QHBoxLayout()
        self.resume_button = QPushButton("Resume safely")
        self.resume_button.clicked.connect(self._resume_selected)
        self.open_button = QPushButton("Open archive folder")
        self.open_button.clicked.connect(self._open_selected)
        actions.addWidget(self.resume_button)
        actions.addWidget(self.open_button)
        actions.addStretch()
        card.layout.addLayout(actions)
        layout.addWidget(card)
        layout.addStretch()
        self._selection_changed()

    def set_loading(self) -> None:
        self.status_label.setText("Loading archive history...")
        self.refresh_button.setEnabled(False)

    def set_items(self, items: tuple[ArchiveHistoryItem, ...]) -> None:
        self.operations.clear()
        for operation in items:
            created = self._display_date(operation.created_at)
            status = operation.status.value.replace("_", " ").title()
            item = QListWidgetItem(
                f"{created}  |  {status}\n{operation.selection_description}"
            )
            item.setData(Qt.ItemDataRole.UserRole, operation)
            self.operations.addItem(item)
        noun = "operation" if len(items) == 1 else "operations"
        self.status_label.setText(f"{len(items):,} {noun}")
        self.refresh_button.setEnabled(True)
        if items:
            self.operations.setCurrentRow(0)
        else:
            self.detail.setText("No archive operations yet.")
            self._selection_changed()

    def set_error(self, message: str) -> None:
        self.status_label.setText(message)
        self.refresh_button.setEnabled(True)

    def _selected(self) -> ArchiveHistoryItem | None:
        item = self.operations.currentItem()
        operation = item.data(Qt.ItemDataRole.UserRole) if item else None
        return operation if isinstance(operation, ArchiveHistoryItem) else None

    def _selection_changed(self, *_: object) -> None:
        operation = self._selected()
        if operation is None:
            self.resume_button.setEnabled(False)
            self.open_button.setEnabled(False)
            return
        self.detail.setText(
            f"Account: {operation.account_email}\n"
            f"Selected: {operation.selected_count:,}\n"
            f"Exported: {operation.exported_count:,}\n"
            f"Verified: {operation.verified_count:,}\n"
            f"Exceptions: {operation.failed_count:,}\n"
            f"Archive: {operation.archive_path}"
        )
        self.resume_button.setEnabled(operation.can_resume)
        if operation.worker_locked:
            self.resume_button.setToolTip("This operation already has an active recovery lock.")
        else:
            self.resume_button.setToolTip("")
        self.open_button.setEnabled(operation.archive_path.is_dir())

    def _resume_selected(self) -> None:
        operation = self._selected()
        if operation and operation.can_resume:
            self.resume_requested.emit(operation.operation_id)

    def _open_selected(self) -> None:
        operation = self._selected()
        if operation and operation.archive_path.is_dir():
            self.open_folder_requested.emit(str(operation.archive_path))

    @staticmethod
    def _display_date(value: str) -> str:
        try:
            return datetime.fromisoformat(value).astimezone().strftime("%b %d, %Y %I:%M %p")
        except ValueError:
            return "Unknown date"


class _HistorySignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str)


class _HistoryWork(QRunnable):
    def __init__(self, repository_factory: Callable[[], HistoryRepository]) -> None:
        super().__init__()
        self.repository_factory = repository_factory
        self.signals = _HistorySignals()

    def run(self) -> None:
        try:
            rows = self.repository_factory().operations()
            items = tuple(
                ArchiveHistoryItem(
                    operation_id=row["id"],
                    created_at=row["created_at"],
                    account_email=row["account_email"],
                    selection_description=row["selection_description"],
                    destination_path=row["destination_path"],
                    archive_folder_name=row["archive_folder_name"],
                    status=OperationStatus(row["status"]),
                    selected_count=row["selected_count"],
                    exported_count=row["exported_count"],
                    verified_count=row["verified_count"],
                    failed_count=row["failed_count"],
                    total_bytes=row["total_bytes"],
                    worker_locked=self._worker_is_active(
                        row["worker_token"], row["worker_acquired_at"]
                    ),
                )
                for row in rows
            )
            self.signals.succeeded.emit(items)
        except Exception:
            self.signals.failed.emit("Archive history could not be loaded safely.")

    @staticmethod
    def _worker_is_active(token: str | None, acquired_at: str | None) -> bool:
        if token is None:
            return False
        if acquired_at is None:
            return True
        try:
            acquired = datetime.fromisoformat(acquired_at)
            if acquired.tzinfo is None:
                return True
            return acquired > datetime.now(UTC) - timedelta(hours=1)
        except ValueError:
            return True


class HistoryController(QObject):
    started = Signal()
    loaded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        repository_factory: Callable[[], HistoryRepository],
        thread_pool: QThreadPool | None = None,
    ) -> None:
        super().__init__()
        self.repository_factory = repository_factory
        self.thread_pool = thread_pool or QThreadPool.globalInstance()
        self._tasks: set[_HistoryWork] = set()

    def load(self) -> None:
        task = _HistoryWork(self.repository_factory)
        self._tasks.add(task)

        def loaded(items: tuple[ArchiveHistoryItem, ...]) -> None:
            self._tasks.discard(task)
            self.loaded.emit(items)

        def failed(message: str) -> None:
            self._tasks.discard(task)
            self.failed.emit(message)

        task.signals.succeeded.connect(loaded)
        task.signals.failed.connect(failed)
        self.started.emit()
        self.thread_pool.start(task)
