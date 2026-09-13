from pathlib import Path

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from demail.domain.eras import Era
from demail.domain.selection import SelectionCriteria
from demail.gmail.client import GmailLabel, GmailMessageMetadata
from demail.jobs.archive_operation import ArchiveProgress

from .archive import ArchiveRunResult
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

QUICK_ARCHIVE_LABELS = ("OLDEST THIRD", "MIDDLE THIRD", "NEWEST THIRD")
SELECTION_FIELD_HEIGHT = 42


class ArchiveWorkflow(QWidget):
    step_changed = Signal(int)
    connect_requested = Signal()
    selection_options_requested = Signal()
    eras_requested = Signal(bool)
    manual_candidates_requested = Signal(object)
    exact_count_requested = Signal(object)
    destination_requested = Signal()
    archive_requested = Signal(object, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._connected = False
        self._exact_count: int | None = None
        self._counting = False
        self._archive_running = False
        self._era_scan_complete = False
        self._era_scan_running = False
        self._pending_quick_archive_index: int | None = None
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
        self._connect_selection_change_signals()

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
        card.setMaximumWidth(840)
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
            "Choose a quick mailbox third, or use dates, labels, sender, search, or "
            "manual selection.",
        )
        quick_title = QLabel("Quick archive")
        quick_title.setStyleSheet("font-size: 15px; font-weight: 650;")
        quick_detail = QLabel(
            "Choose one balanced third of your mailbox, then continue to review and archive it."
        )
        quick_detail.setObjectName("muted")
        quick_detail.setWordWrap(True)
        self.quick_archive_container = QWidget()
        self.quick_archive_container.setObjectName("quickArchiveSegments")
        quick_layout = QHBoxLayout(self.quick_archive_container)
        quick_layout.setContentsMargins(0, 0, 0, 0)
        quick_layout.setSpacing(0)
        self.quick_archive_group = QButtonGroup(self)
        self.quick_archive_group.setExclusive(True)
        self.quick_archive_buttons: list[QPushButton] = []
        for index, label in enumerate(QUICK_ARCHIVE_LABELS):
            button = QPushButton(f"{label}\n33.33%")
            button.setCheckable(True)
            button.setProperty("quickArchive", True)
            position = "first" if index == 0 else "last" if index == 2 else "middle"
            button.setProperty("segmentPosition", position)
            button.setAccessibleName(f"{label.title()}, 33.33 percent of mailbox")
            button.setToolTip("Calculate and select this mailbox third")
            button.clicked.connect(
                lambda _checked=False, selected=index: self._request_quick_archive(selected)
            )
            self.quick_archive_group.addButton(button, index)
            self.quick_archive_buttons.append(button)
            quick_layout.addWidget(button, 1)
        card.layout.addWidget(quick_title)
        card.layout.addWidget(quick_detail)
        card.layout.addWidget(self.quick_archive_container)

        custom_title = QLabel("Detailed selection")
        custom_title.setStyleSheet("font-size: 15px; font-weight: 650; margin-top: 8px;")
        card.layout.addWidget(custom_title)
        form = QFormLayout()
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(14)
        self.selection_form = form
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
        self.selection_mode.setMinimumHeight(SELECTION_FIELD_HEIGHT)
        self.selection_mode.currentIndexChanged.connect(self._update_selection_mode)
        self.era_combo = QComboBox()
        self.era_combo.setMinimumHeight(SELECTION_FIELD_HEIGHT)
        self.era_combo.setPlaceholderText("Calculate mailbox eras first")
        self.scan_eras_button = QPushButton("Calculate mailbox eras")
        self.scan_eras_button.clicked.connect(self._request_era_scan)
        self.start_date = QDateEdit(QDate.currentDate().addYears(-1))
        self.start_date.setMinimumHeight(SELECTION_FIELD_HEIGHT)
        self.start_date.setCalendarPopup(True)
        self.end_date = QDateEdit(QDate.currentDate())
        self.end_date.setMinimumHeight(SELECTION_FIELD_HEIGHT)
        self.end_date.setCalendarPopup(True)
        self.sender_input = QLineEdit()
        self.sender_input.setMinimumHeight(SELECTION_FIELD_HEIGHT)
        self.sender_input.setPlaceholderText("sender@example.com")
        self.search_input = QLineEdit()
        self.search_input.setMinimumHeight(SELECTION_FIELD_HEIGHT)
        self.search_input.setPlaceholderText("has:attachment")
        self.label_combo = QComboBox()
        self.label_combo.setMinimumHeight(SELECTION_FIELD_HEIGHT)
        self.label_combo.setPlaceholderText("Choose a Gmail label")
        self.include_spam = QCheckBox("Include Spam and Trash")
        self.manual_candidates = QListWidget()
        self.manual_candidates.setMinimumHeight(180)
        self.load_candidates_button = QPushButton("Load recent matching messages")
        self.load_candidates_button.clicked.connect(self._request_manual_candidates)
        form.addRow("Selection", self.selection_mode)
        form.addRow("Mailbox era", self.era_combo)
        form.addRow("", self.scan_eras_button)
        form.addRow("From", self.start_date)
        form.addRow("To", self.end_date)
        form.addRow("Gmail label", self.label_combo)
        form.addRow("Sender", self.sender_input)
        form.addRow("Gmail search", self.search_input)
        form.addRow("", self.include_spam)
        form.addRow("", self.load_candidates_button)
        form.addRow("Messages", self.manual_candidates)
        self.selection_error = QLabel("")
        self.selection_error.setObjectName("muted")
        card.layout.addLayout(form)
        card.layout.addWidget(self.selection_error)
        self._update_selection_mode()
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
        self.count_button.clicked.connect(self._request_exact_count)
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
        self.destination_button.clicked.connect(self.destination_requested.emit)
        self.destination_error = QLabel("")
        self.destination_error.setObjectName("muted")
        card.layout.addWidget(self.destination_input)
        card.layout.addWidget(self.destination_button)
        card.layout.addWidget(self.destination_error)
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
        self._counting = False
        self._exact_count = count
        noun = "message" if count == 1 else "messages"
        self.count_label.setText(f"{count:,} {noun} selected")
        self.count_button.setEnabled(True)
        self._update_actions()

    def set_counting(self) -> None:
        self._counting = True
        self._exact_count = None
        self.count_label.setText("Counting every matching message...")
        self.count_button.setEnabled(False)
        self._update_actions()

    def set_selection_error(self, message: str) -> None:
        self._counting = False
        self.selection_error.setText(message)
        self.count_label.setText(message)
        self.count_button.setEnabled(True)
        self._update_actions()

    def set_destination(self, destination: str) -> None:
        path = Path(destination)
        if not path.is_absolute() or not path.is_dir():
            raise ValueError("Choose an existing destination folder.")
        self.destination_input.setText(str(path))
        self.destination_error.clear()
        self._update_actions()

    def set_archive_started(self) -> None:
        self._archive_running = True
        self.archive_progress.setRange(0, 1)
        self.archive_progress.setValue(0)
        self.progress_label.setText("Preparing a fixed message list...")
        self.verify_progress.setRange(0, 1)
        self.verify_progress.setValue(0)
        self.verify_label.setText("Waiting for archive export")
        self.set_step(4)

    def set_archive_progress(self, progress: ArchiveProgress) -> None:
        if progress.phase == "export":
            self.set_step(4)
            self.archive_progress.setRange(0, max(progress.total, 1))
            self.archive_progress.setValue(progress.completed)
            self.progress_label.setText(
                f"{progress.completed:,} of {progress.total:,} messages copied"
            )
            return
        self.set_step(5)
        self.verify_progress.setRange(0, max(progress.total, 1))
        self.verify_progress.setValue(progress.completed)
        self.verify_label.setText(
            f"{progress.completed:,} of {progress.total:,} messages checked"
        )

    def set_archive_complete(self, result: ArchiveRunResult) -> None:
        self._archive_running = False
        if result.status == "VERIFIED":
            self.report_title.setText("Archive verified")
        elif result.status == "PARTIAL":
            self.report_title.setText("Archive completed with exceptions")
        else:
            self.report_title.setText("Archive could not be completed")
        self.report_detail.setText(
            f"Selected: {result.selected_count:,}\n"
            f"Exported: {result.exported_count:,}\n"
            f"Verified: {result.verified_count:,}\n"
            f"Exceptions: {result.failed_count:,}\n"
            f"Size: {self._format_bytes(result.total_bytes)}\n"
            f"Saved to: {result.archive_path}"
        )
        self.set_step(6)

    def set_archive_error(self, message: str) -> None:
        self._archive_running = False
        self.report_title.setText("Archive stopped safely")
        self.report_detail.setText(message)
        self.set_step(6)

    @staticmethod
    def _format_bytes(byte_count: int) -> str:
        if byte_count < 0:
            raise ValueError("Archive size cannot be negative.")
        size = float(byte_count)
        for unit in ("bytes", "KB", "MB", "GB", "TB"):
            if size < 1024 or unit == "TB":
                return f"{int(size):,} {unit}" if unit == "bytes" else f"{size:.1f} {unit}"
            size /= 1024
        raise AssertionError("Unreachable size unit")

    def set_labels(self, labels: tuple[GmailLabel, ...]) -> None:
        self.label_combo.clear()
        for label in sorted(labels, key=lambda item: item.name.casefold()):
            self.label_combo.addItem(label.name, label.id)
        if labels:
            self.label_combo.setCurrentIndex(0)

    def set_eras(self, eras: tuple[Era, ...]) -> None:
        self._era_scan_complete = True
        self._era_scan_running = False
        self.era_combo.clear()
        for era in eras:
            count = f"{era.approximate_count:,} messages"
            self.era_combo.addItem(f"{era.kind.value}: {count}", era)
        if eras:
            self.era_combo.setCurrentIndex(0)
        self.scan_eras_button.setText("Recalculate mailbox eras")
        self.scan_eras_button.setEnabled(True)
        has_thirds = len(eras) == len(self.quick_archive_buttons)
        for index, button in enumerate(self.quick_archive_buttons):
            button.setEnabled(has_thirds)
            if has_thirds:
                count = f"{eras[index].approximate_count:,}"
                button.setText(f"{QUICK_ARCHIVE_LABELS[index]}\n33.33% · {count}")
                button.setToolTip(
                    f"Select approximately {count} messages from the "
                    f"{QUICK_ARCHIVE_LABELS[index].lower()}"
                )
            else:
                button.setText(f"{QUICK_ARCHIVE_LABELS[index]}\nUnavailable")
                button.setToolTip("This mailbox could not be divided into three useful eras")
        pending = self._pending_quick_archive_index
        self._pending_quick_archive_index = None
        if has_thirds and pending is not None:
            self._activate_quick_archive(pending)
        else:
            self._sync_quick_archive_selection()

    def set_era_scan_running(self) -> None:
        self._era_scan_running = True
        self.scan_eras_button.setText("Calculating mailbox eras...")
        self.scan_eras_button.setEnabled(False)
        for index, button in enumerate(self.quick_archive_buttons):
            button.setEnabled(False)
            button.setText(f"{QUICK_ARCHIVE_LABELS[index]}\nCalculating")

    def set_era_scan_error(self, message: str) -> None:
        self._era_scan_complete = False
        self._era_scan_running = False
        self._pending_quick_archive_index = None
        self.scan_eras_button.setText("Try mailbox eras again")
        self.scan_eras_button.setEnabled(True)
        for index, button in enumerate(self.quick_archive_buttons):
            button.setEnabled(True)
            button.setText(f"{QUICK_ARCHIVE_LABELS[index]}\n33.33%")
        self.set_selection_error(message)

    def set_manual_candidates(self, candidates: tuple[GmailMessageMetadata, ...]) -> None:
        self.manual_candidates.clear()
        for candidate in candidates:
            subject = candidate.subject or "No subject"
            sender = candidate.sender or "Unknown sender"
            item = QListWidgetItem(f"{subject}\n{sender}")
            item.setData(Qt.ItemDataRole.UserRole, candidate.id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.manual_candidates.addItem(item)
        self.load_candidates_button.setText("Reload recent matching messages")
        self.load_candidates_button.setEnabled(True)

    def selection_criteria(self, *, include_manual_ids: bool = True) -> SelectionCriteria:
        mode = self.selection_mode.currentText()
        common = {
            "include_spam_and_trash": self.include_spam.isChecked(),
        }
        if mode == "Mailbox era":
            era = self.era_combo.currentData()
            if not isinstance(era, Era):
                raise ValueError("Calculate and choose a mailbox era first.")
            return self._validated(era.criteria(self.include_spam.isChecked()))
        if mode == "Date range":
            return self._validated(
                SelectionCriteria(
                    start_date=self.start_date.date().toPython().isoformat(),
                    end_date=self.end_date.date().toPython().isoformat(),
                    **common,
                )
            )
        if mode == "Gmail label":
            label_id = self.label_combo.currentData()
            if not isinstance(label_id, str):
                raise ValueError("Choose a Gmail label first.")
            return self._validated(
                SelectionCriteria(
                    label_id=label_id,
                    label_name=self.label_combo.currentText(),
                    **common,
                )
            )
        if mode == "Sender":
            sender = self.sender_input.text().strip()
            if not sender:
                raise ValueError("Sender is required.")
            return self._validated(SelectionCriteria(sender=sender, **common))
        if mode == "Gmail search":
            search = self.search_input.text().strip()
            if not search:
                raise ValueError("Enter a Gmail search first.")
            return self._validated(SelectionCriteria(search_query=search, **common))
        selected = tuple(
            self.manual_candidates.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(self.manual_candidates.count())
            if self.manual_candidates.item(index).checkState() == Qt.CheckState.Checked
        )
        if include_manual_ids and not selected:
            raise ValueError("Select at least one message first.")
        return self._validated(
            SelectionCriteria(
                sender=self.sender_input.text().strip() or None,
                search_query=self.search_input.text().strip() or None,
                include_spam_and_trash=self.include_spam.isChecked(),
                explicit_message_ids=selected if include_manual_ids else (),
            )
        )

    @staticmethod
    def _validated(criteria: SelectionCriteria) -> SelectionCriteria:
        problems = criteria.validate()
        if problems:
            raise ValueError(problems[0])
        return criteria

    def _update_selection_mode(self) -> None:
        mode = self.selection_mode.currentText()
        widgets = {
            self.era_combo: mode == "Mailbox era",
            self.scan_eras_button: mode == "Mailbox era",
            self.start_date: mode == "Date range",
            self.end_date: mode == "Date range",
            self.label_combo: mode == "Gmail label",
            self.sender_input: mode in {"Sender", "Manual selection"},
            self.search_input: mode in {"Gmail search", "Manual selection"},
            self.load_candidates_button: mode == "Manual selection",
            self.manual_candidates: mode == "Manual selection",
        }
        for widget, visible in widgets.items():
            widget.setVisible(visible)
            label = self.selection_form.labelForField(widget)
            if label is not None:
                label.setVisible(visible)
        self.selection_error.clear()

    def _connect_selection_change_signals(self) -> None:
        self.selection_mode.currentIndexChanged.connect(self._invalidate_exact_count)
        self.selection_mode.currentIndexChanged.connect(self._sync_quick_archive_selection)
        self.era_combo.currentIndexChanged.connect(self._invalidate_exact_count)
        self.era_combo.currentIndexChanged.connect(self._sync_quick_archive_selection)
        self.start_date.dateChanged.connect(self._invalidate_exact_count)
        self.end_date.dateChanged.connect(self._invalidate_exact_count)
        self.label_combo.currentIndexChanged.connect(self._invalidate_exact_count)
        self.sender_input.textChanged.connect(self._invalidate_exact_count)
        self.search_input.textChanged.connect(self._invalidate_exact_count)
        self.include_spam.toggled.connect(self._invalidate_exact_count)
        self.manual_candidates.itemChanged.connect(self._invalidate_exact_count)

    def _request_era_scan(self) -> None:
        if self._era_scan_running:
            return
        self._era_scan_complete = False
        self._pending_quick_archive_index = None
        self.set_era_scan_running()
        self.eras_requested.emit(self.include_spam.isChecked())

    def _request_quick_archive(self, index: int) -> None:
        if not 0 <= index < len(self.quick_archive_buttons):
            raise ValueError("Quick archive third is out of range")
        if self._era_scan_running:
            return
        if not self._era_scan_complete:
            self._pending_quick_archive_index = index
            self.set_era_scan_running()
            self.eras_requested.emit(self.include_spam.isChecked())
            return
        self._activate_quick_archive(index)

    def _activate_quick_archive(self, index: int) -> None:
        era = self.era_combo.itemData(index)
        if not isinstance(era, Era):
            self.selection_error.setText(
                "This mailbox could not be divided into three useful eras."
            )
            self._sync_quick_archive_selection()
            return
        self.selection_mode.setCurrentText("Mailbox era")
        self.era_combo.setCurrentIndex(index)
        self.selection_error.clear()
        self._sync_quick_archive_selection()

    def _sync_quick_archive_selection(self) -> None:
        selected = (
            self.era_combo.currentIndex()
            if self.selection_mode.currentText() == "Mailbox era"
            else -1
        )
        self.quick_archive_group.setExclusive(False)
        for index, button in enumerate(self.quick_archive_buttons):
            button.setChecked(index == selected and self._era_scan_complete)
        self.quick_archive_group.setExclusive(True)

    def _invalidate_exact_count(self) -> None:
        if self._exact_count is None and not self._counting:
            return
        self._counting = False
        self._exact_count = None
        self.count_label.setText("Count not calculated")
        self.count_button.setEnabled(True)
        self._update_actions()

    def _request_manual_candidates(self) -> None:
        try:
            criteria = self.selection_criteria(include_manual_ids=False)
        except ValueError as error:
            self.selection_error.setText(str(error))
            return
        self.load_candidates_button.setText("Loading messages...")
        self.load_candidates_button.setEnabled(False)
        self.manual_candidates_requested.emit(criteria)

    def _request_exact_count(self) -> None:
        try:
            criteria = self.selection_criteria()
        except ValueError as error:
            self.set_selection_error(str(error))
            return
        self.set_counting()
        self.exact_count_requested.emit(criteria)

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
            if self.current_step == 1:
                try:
                    self.selection_criteria()
                except ValueError as error:
                    self.selection_error.setText(str(error))
                    return
            if self.current_step == 3:
                destination = self.destination_input.text()
                if not destination:
                    self.destination_error.setText("Choose a destination folder first.")
                    return
                self.archive_requested.emit(self.selection_criteria(), destination)
                return
            self.set_step(self.current_step + 1)

    def go_back(self) -> None:
        if self.current_step > 0:
            self.set_step(self.current_step - 1)

    def _update_actions(self) -> None:
        index = self.current_step
        self.back_button.setEnabled(index > 0 and not self._archive_running)
        can_continue = not (index == 0 and not self._connected)
        if index == 2 and self._exact_count is None:
            can_continue = False
        if index == 3 and not self.destination_input.text():
            can_continue = False
        if self._archive_running:
            can_continue = False
        self.next_button.setEnabled(can_continue and index < self.pages.count() - 1)
