"""About, version history, and safe manual update-check UI."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from demail import __version__
from demail.updates import UpdateResult, UpdateState, check_for_update

from .components import Card, page_heading

MAX_CHANGELOG_CHARACTERS = 20_000


def load_version_history(path: Path | None = None) -> str:
    """Load a bounded packaged changelog with a safe fallback."""
    candidates = [path] if path is not None else [
        Path(sys.argv[0]).resolve().parent / "CHANGELOG.md",
        Path(__file__).resolve().parents[3] / "CHANGELOG.md",
    ]
    for candidate in candidates:
        if candidate is None or not candidate.is_file():
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        text = text.strip()
        if text:
            return text[:MAX_CHANGELOG_CHARACTERS]
    return "Version history is unavailable in this build."


class AboutPage(QWidget):
    check_requested = Signal()
    release_requested = Signal(str)

    def __init__(self, history: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._release_url: str | None = None
        self._build(history if history is not None else load_version_history())

    def _build(self, history: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(38, 30, 38, 30)
        layout.setSpacing(18)
        heading, _ = page_heading(
            "About",
            "de-Mail Desktop",
            "Version details, release history, and a read-only check for signed updates.",
        )
        layout.addWidget(heading)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(18)

        version_card = Card()
        version_title = QLabel(f"Version {__version__}")
        version_title.setStyleSheet("font-size: 18px; font-weight: 650;")
        privacy = QLabel(
            "The update check reads public GitHub release metadata only. It never sends Gmail "
            "content, downloads an installer, or installs software by itself."
        )
        privacy.setObjectName("muted")
        privacy.setWordWrap(True)
        version_card.layout.addWidget(version_title)
        version_card.layout.addWidget(privacy)
        actions = QHBoxLayout()
        self.check_button = QPushButton("Check for update")
        self.check_button.setProperty("primary", True)
        self.check_button.clicked.connect(self.check_requested.emit)
        self.release_button = QPushButton("View download page")
        self.release_button.setVisible(False)
        self.release_button.clicked.connect(self._request_release)
        actions.addWidget(self.check_button)
        actions.addWidget(self.release_button)
        actions.addStretch()
        version_card.layout.addLayout(actions)
        self.status_label = QLabel("No update check has been made.")
        self.status_label.setObjectName("muted")
        self.status_label.setWordWrap(True)
        version_card.layout.addWidget(self.status_label)
        body_layout.addWidget(version_card)

        history_card = Card()
        history_title = QLabel("Version history")
        history_title.setStyleSheet("font-size: 17px; font-weight: 650;")
        self.history = QPlainTextEdit()
        self.history.setReadOnly(True)
        self.history.setPlainText(history)
        self.history.setMinimumHeight(260)
        history_card.layout.addWidget(history_title)
        history_card.layout.addWidget(self.history)
        body_layout.addWidget(history_card)
        body_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)

    def set_checking(self) -> None:
        self._release_url = None
        self.check_button.setEnabled(False)
        self.check_button.setText("Checking...")
        self.release_button.setVisible(False)
        self.status_label.setText("Checking the public release feed...")

    def show_result(self, result: UpdateResult) -> None:
        self.check_button.setEnabled(True)
        self.check_button.setText("Check for update")
        self._release_url = result.release_url
        if result.state is UpdateState.AVAILABLE:
            self.status_label.setText(
                f"Version {result.latest_version} is available. You choose whether to download it."
            )
            self.release_button.setVisible(True)
        elif result.state is UpdateState.CURRENT:
            self.status_label.setText(f"Version {result.current_version} is up to date.")
            self.release_button.setVisible(False)
        else:
            self.status_label.setText(
                "The update service could not be reached or returned invalid information. "
                "Try again later."
            )
            self.release_button.setVisible(False)

    def set_open_error(self) -> None:
        self.status_label.setText("The trusted GitHub download page could not be opened.")

    def _request_release(self) -> None:
        if self._release_url:
            self.release_requested.emit(self._release_url)


class _UpdateSignals(QObject):
    succeeded = Signal(object)


class _UpdateWork(QRunnable):
    def __init__(self, checker: Callable[[], UpdateResult]) -> None:
        super().__init__()
        self.checker = checker
        self.signals = _UpdateSignals()

    def run(self) -> None:
        try:
            result = self.checker()
        except Exception:
            result = UpdateResult(UpdateState.UNAVAILABLE, __version__)
        self.signals.succeeded.emit(result)


class UpdateController(QObject):
    started = Signal()
    completed = Signal(object)

    def __init__(
        self,
        checker: Callable[[], UpdateResult] = check_for_update,
        thread_pool: QThreadPool | None = None,
    ) -> None:
        super().__init__()
        self.checker = checker
        self.thread_pool = thread_pool or QThreadPool.globalInstance()
        self._tasks: set[_UpdateWork] = set()

    def check(self) -> None:
        task = _UpdateWork(self.checker)
        self._tasks.add(task)

        def completed(result: UpdateResult) -> None:
            self._tasks.discard(task)
            self.completed.emit(result)

        task.signals.succeeded.connect(completed)
        self.started.emit()
        self.thread_pool.start(task)
