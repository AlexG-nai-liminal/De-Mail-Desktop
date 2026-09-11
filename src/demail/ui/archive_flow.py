from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .components import Card, page_heading

STEP_NAMES = (
    "Connect",
    "Select",
    "Review",
    "Destination",
    "Archive",
    "Verify",
    "Complete",
)


class ArchiveWorkflow(QWidget):
    step_changed = Signal(int)
    connect_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._connected = False
        self._exact_count: int | None = None
        self._build()
        self.set_step(0)

    @property
    def current_step(self) -> int:
        return self.pages.currentIndex()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(38, 30, 38, 30)
        root.setSpacing(22)
        heading, _ = page_heading(
            "Archive Gmail",
            "A verified copy you control",
            "Choose what to preserve. Every message is copied in its original format, "
            "then read back and checked.",
        )
        root.addWidget(heading)

        self.step_labels: list[QLabel] = []
        steps = QHBoxLayout()
        steps.setSpacing(14)
        for index, name in enumerate(STEP_NAMES):
            label = QLabel(f"{index + 1:02d}")
            label.setToolTip(name)
            label.setAccessibleName(f"Step {index + 1}: {name}")
            label.setObjectName("muted")
            self.step_labels.append(label)
            steps.addWidget(label)
        steps.addStretch()
        root.addLayout(steps)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._connect_page())
        self.pages.addWidget(self._selection_page())
        self.pages.addWidget(self._review_page())
        self.pages.addWidget(self._destination_page())
        self.pages.addWidget(self._progress_page())
        self.pages.addWidget(self._verification_page())
        self.pages.addWidget(self._complete_page())
        root.addWidget(self.pages, 1)

        actions = QHBoxLayout()
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self.go_back)
        self.next_button = QPushButton("Continue")
        self.next_button.setProperty("primary", True)
        self.next_button.clicked.connect(self.go_forward)
        actions.addWidget(self.back_button)
        actions.addStretch()
        actions.addWidget(self.next_button)
        root.addLayout(actions)

    def _page(self, title: str, description: str) -> tuple[QWidget, Card]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        card = Card()
        card.setMaximumWidth(760)
        heading = QLabel(title)
        heading.setStyleSheet("font-size: 19px; font-weight: 650;")
        detail = QLabel(description)
        detail.setObjectName("muted")
        detail.setWordWrap(True)
        card.layout.addWidget(heading)
        card.layout.addWidget(detail)
        layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addStretch()
        return page, card

    def _connect_page(self) -> QWidget:
        page, card = self._page(
            "Connect your Google account",
            "Authorization opens in your usual browser and requests Gmail read-only access.",
        )
        self.account_status = QLabel("Not connected")
        self.account_status.setObjectName("muted")
        self.connect_button = QPushButton("Connect with Google")
        self.connect_button.clicked.connect(self.connect_requested.emit)
        card.layout.addWidget(self.account_status)
        card.layout.addWidget(self.connect_button)
        return page

    def _selection_page(self) -> QWidget:
        page, card = self._page(
            "Choose the mail to archive",
            "Start broad with a mailbox era, or use dates, labels, sender, search, "
            "or manual selection.",
        )
        form = QFormLayout()
        self.selection_mode = QComboBox()
        self.selection_mode.addItems(
            [
                "Mailbox era",
                "Date range",
                "Gmail label",
                "Sender",
                "Gmail search",
                "Manual selection",
            ]
        )
        self.start_date = QDateEdit(QDate.currentDate().addYears(-1))
        self.start_date.setCalendarPopup(True)
        self.end_date = QDateEdit(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        self.sender_input = QLineEdit()
        self.sender_input.setPlaceholderText("sender@example.com")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("has:attachment")
        form.addRow("Selection", self.selection_mode)
        form.addRow("From", self.start_date)
        form.addRow("To", self.end_date)
        form.addRow("Sender", self.sender_input)
        form.addRow("Gmail search", self.search_input)
        card.layout.addLayout(form)
        return page

    def _review_page(self) -> QWidget:
        page, card = self._page(
            "Review the exact count",
            "de-Mail walks every Gmail results page before archiving. Estimates are never "
            "used as the final count.",
        )
        self.count_label = QLabel("Count not calculated")
        self.count_label.setStyleSheet("font-size: 24px; font-weight: 650;")
        self.count_button = QPushButton("Calculate exact count")
        card.layout.addWidget(self.count_label)
        card.layout.addWidget(self.count_button)
        return page

    def _destination_page(self) -> QWidget:
        page, card = self._page(
            "Choose a destination",
            "Select a Windows folder you control. Each archive receives a new operation folder.",
        )
        self.destination_input = QLineEdit()
        self.destination_input.setPlaceholderText("No folder selected")
        self.destination_input.setReadOnly(True)
        self.destination_button = QPushButton("Choose folder")
        card.layout.addWidget(self.destination_input)
        card.layout.addWidget(self.destination_button)
        return page

    def _progress_page(self) -> QWidget:
        page, card = self._page(
            "Archiving messages",
            "Completed messages are durable. If this stops, resume without downloading them again.",
        )
        self.archive_progress = QProgressBar()
        self.archive_progress.setRange(0, 100)
        self.archive_progress.setValue(0)
        self.archive_progress.setTextVisible(False)
        self.progress_label = QLabel("0 of 0 messages copied")
        self.progress_label.setObjectName("muted")
        card.layout.addWidget(self.archive_progress)
        card.layout.addWidget(self.progress_label)
        return page

    def _verification_page(self) -> QWidget:
        page, card = self._page(
            "Verifying the archive",
            "Every file is reopened from the destination and checked for exact size and SHA-256.",
        )
        self.verify_progress = QProgressBar()
        self.verify_progress.setTextVisible(False)
        self.verify_label = QLabel("Waiting for archive export")
        self.verify_label.setObjectName("muted")
        card.layout.addWidget(self.verify_progress)
        card.layout.addWidget(self.verify_label)
        return page

    def _complete_page(self) -> QWidget:
        page, card = self._page(
            "Archive report",
            "Verified is shown only when every selected message exists and matches its "
            "recorded hash.",
        )
        self.report_title = QLabel("Archive not started")
        self.report_title.setStyleSheet("font-size: 24px; font-weight: 650;")
        self.report_detail = QLabel("No result is available yet.")
        self.report_detail.setObjectName("muted")
        card.layout.addWidget(self.report_title)
        card.layout.addWidget(self.report_detail)
        return page

    def set_connected(self, account: str, totals: str) -> None:
        self._connected = True
        self.account_status.setText(f"{account}\n{totals}")
        self.connect_button.setText("Connected")
        self.connect_button.setEnabled(False)
        self._update_actions()

    def set_connecting(self) -> None:
        self.connect_button.setEnabled(False)
        self.connect_button.setText("Connecting...")
        self.account_status.setText("Complete authorization in your browser")

    def set_connection_error(self, message: str) -> None:
        self._connected = False
        self.connect_button.setEnabled(True)
        self.connect_button.setText("Try again")
        self.account_status.setText(message)
        self._update_actions()

    def set_exact_count(self, count: int) -> None:
        if count < 0:
            raise ValueError("Exact count cannot be negative")
        self._exact_count = count
        noun = "message" if count == 1 else "messages"
        self.count_label.setText(f"{count:,} {noun} selected")
        self._update_actions()

    def set_step(self, index: int) -> None:
        if not 0 <= index < self.pages.count():
            raise ValueError("Archive workflow step is out of range")
        self.pages.setCurrentIndex(index)
        for step_index, label in enumerate(self.step_labels):
            label.setStyleSheet(
                "color: #FFFFFF; font-weight: 650;" if step_index == index else "color: #666666;"
            )
        self._update_actions()
        self.step_changed.emit(index)

    def go_forward(self) -> None:
        if self.next_button.isEnabled() and self.current_step < self.pages.count() - 1:
            self.set_step(self.current_step + 1)

    def go_back(self) -> None:
        if self.current_step > 0:
            self.set_step(self.current_step - 1)

    def _update_actions(self) -> None:
        index = self.current_step
        self.back_button.setEnabled(index > 0)
        can_continue = not (index == 0 and not self._connected)
        if index == 2 and self._exact_count is None:
            can_continue = False
        self.next_button.setEnabled(can_continue and index < self.pages.count() - 1)
