"""Inspectable, local-only problem report UI and controller."""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from demail.archive.atomic_file import AtomicArchiveFile
from demail.diagnostics.collector import DiagnosticCollector
from demail.diagnostics.report import render_report

from .components import Card, page_heading


class ProblemReportPage(QWidget):
    build_requested = Signal(str, str)
    save_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(38, 30, 38, 30)
        layout.setSpacing(18)
        heading, _ = page_heading(
            "Report a problem",
            "Inspect everything before it leaves",
            "de-Mail has no diagnostics server. Nothing is sent automatically.",
        )
        layout.addWidget(heading)
        card = Card()
        privacy = QLabel(
            "Describe the problem, build the report, and read every character. "
            "You decide whether to copy or save it."
        )
        privacy.setObjectName("muted")
        privacy.setWordWrap(True)
        card.layout.addWidget(privacy)
        card.layout.addWidget(QLabel("What happened?"))
        self.what_happened = QPlainTextEdit()
        self.what_happened.setPlaceholderText(
            "It stopped during verification and the operation would not resume."
        )
        self.what_happened.setMaximumHeight(90)
        card.layout.addWidget(self.what_happened)
        card.layout.addWidget(QLabel("What were you trying to do?"))
        self.what_doing = QPlainTextEdit()
        self.what_doing.setPlaceholderText("Archiving a date range to an external drive.")
        self.what_doing.setMaximumHeight(75)
        card.layout.addWidget(self.what_doing)
        self.build_button = QPushButton("Build privacy-safe report")
        self.build_button.setProperty("primary", True)
        self.build_button.clicked.connect(self._request_build)
        card.layout.addWidget(self.build_button)
        preview_title = QLabel("Complete report preview")
        preview_title.setStyleSheet("font-size: 16px; font-weight: 650;")
        card.layout.addWidget(preview_title)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("Build the report to inspect it here.")
        self.preview.setMinimumHeight(220)
        card.layout.addWidget(self.preview)
        actions = QHBoxLayout()
        self.copy_button = QPushButton("Copy report")
        self.copy_button.clicked.connect(self.copy_report)
        self.save_button = QPushButton("Save report as file")
        self.save_button.clicked.connect(
            lambda: self.save_requested.emit(self.preview.toPlainText())
        )
        actions.addWidget(self.copy_button)
        actions.addWidget(self.save_button)
        actions.addStretch()
        card.layout.addLayout(actions)
        self.delivery_status = QLabel("")
        self.delivery_status.setObjectName("muted")
        card.layout.addWidget(self.delivery_status)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.addWidget(card)
        body_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)
        self._set_delivery_enabled(False)

    def _request_build(self) -> None:
        self.build_requested.emit(
            self.what_happened.toPlainText(),
            self.what_doing.toPlainText(),
        )

    def set_building(self) -> None:
        self.build_button.setEnabled(False)
        self.build_button.setText("Building report...")
        self.delivery_status.setText("Collecting non-personal application facts...")
        self._set_delivery_enabled(False)

    def set_report(self, text: str) -> None:
        self.preview.setPlainText(text)
        self.build_button.setEnabled(True)
        self.build_button.setText("Rebuild privacy-safe report")
        self.delivery_status.setText("Review the report before copying or saving it.")
        self._set_delivery_enabled(bool(text))

    def set_error(self, message: str) -> None:
        self.build_button.setEnabled(True)
        self.build_button.setText("Try building report again")
        self.delivery_status.setText(message)
        self._set_delivery_enabled(False)

    def copy_report(self) -> None:
        text = self.preview.toPlainText()
        if not text:
            return
        QApplication.clipboard().setText(text)
        self.delivery_status.setText("Report copied to the clipboard.")

    def set_saved(self, path: str) -> None:
        del path
        self.delivery_status.setText("Report saved to the folder you selected.")

    def _set_delivery_enabled(self, enabled: bool) -> None:
        self.copy_button.setEnabled(enabled)
        self.save_button.setEnabled(enabled)


class _DiagnosticSignals(QObject):
    succeeded = Signal(str)
    failed = Signal(str)


class _DiagnosticWork(QRunnable):
    def __init__(
        self,
        collector_factory: Callable[[], DiagnosticCollector],
        account_provider: Callable[[], str | None],
        what_happened: str,
        what_doing: str,
    ) -> None:
        super().__init__()
        self.collector_factory = collector_factory
        self.account_provider = account_provider
        self.what_happened = what_happened
        self.what_doing = what_doing
        self.signals = _DiagnosticSignals()

    def run(self) -> None:
        try:
            report = self.collector_factory().collect(
                stage="Report a problem",
                account_email=self.account_provider(),
                what_happened=self.what_happened,
                what_were_you_doing=self.what_doing,
            )
            self.signals.succeeded.emit(render_report(report))
        except Exception:
            self.signals.failed.emit("The diagnostic report could not be built safely.")


class DiagnosticController(QObject):
    started = Signal()
    built = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        collector_factory: Callable[[], DiagnosticCollector],
        account_provider: Callable[[], str | None] = lambda: None,
        thread_pool: QThreadPool | None = None,
    ) -> None:
        super().__init__()
        self.collector_factory = collector_factory
        self.account_provider = account_provider
        self.thread_pool = thread_pool or QThreadPool.globalInstance()
        self._tasks: set[_DiagnosticWork] = set()

    def build(self, what_happened: str, what_doing: str) -> None:
        task = _DiagnosticWork(
            self.collector_factory,
            self.account_provider,
            what_happened,
            what_doing,
        )
        self._tasks.add(task)

        def built(text: str) -> None:
            self._tasks.discard(task)
            self.built.emit(text)

        def failed(message: str) -> None:
            self._tasks.discard(task)
            self.failed.emit(message)

        task.signals.succeeded.connect(built)
        task.signals.failed.connect(failed)
        self.started.emit()
        self.thread_pool.start(task)


def save_diagnostic_report(path: Path, text: str) -> None:
    if not path.is_absolute() or not path.parent.is_dir():
        raise OSError("The report destination is unavailable.")
    if not text:
        raise ValueError("A blank diagnostic report cannot be saved.")
    with AtomicArchiveFile(path) as target:
        target.write(text.encode("utf-8"))
