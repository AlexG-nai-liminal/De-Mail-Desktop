from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from demail.auth.client_config import OAuthClientConfigError
from demail.auth.client_source import describe_oauth_source, resolve_oauth_client
from demail.windows.shell import open_email_draft, open_folder, open_release_page

from .about import AboutPage, UpdateController
from .archive import ArchiveController
from .archive_flow import ArchiveWorkflow
from .authorization import (
    AuthorizationController,
    PrivacyDisclosureDialog,
    accept_disclosure,
    disclosure_is_current,
)
from .components import Card, page_heading
from .connection import ConnectedMailbox, ConnectionController
from .diagnostics import DiagnosticController, ProblemReportPage, save_diagnostic_report
from .help import HelpTutorialPage
from .history import HistoryController, HistoryPage
from .selection import SelectionController

NAVIGATION = (
    ("Archive Gmail", "archive"),
    ("History", "history"),
    ("Reclaim storage", "reclaim"),
    ("Report a problem", "report"),
    ("Settings", "settings"),
    ("Help", "help"),
    ("About", "about"),
)

REPORT_EMAIL = "alex@liminalmemory.com"
REPORT_SUBJECT = "de-Mail Desktop problem report"


class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings | None = None) -> None:
        super().__init__()
        self.settings = settings or QSettings("de-Mail", "de-Mail Desktop")
        self.connection_controller: ConnectionController | None = None
        self.selection_controller: SelectionController | None = None
        self.archive_controller: ArchiveController | None = None
        self.history_controller: HistoryController | None = None
        self.diagnostic_controller: DiagnosticController | None = None
        self.update_controller: UpdateController | None = None
        self.authorization_controller: AuthorizationController | None = None
        self.connected_account: str | None = None
        self.setWindowTitle("de-Mail Desktop")
        self.setMinimumSize(960, 640)
        self.resize(1180, 760)
        self._build()

    def _build(self) -> None:
        root = QWidget()
        root.setObjectName("appRoot")
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._navigation())
        self.content = QStackedWidget()
        self.archive_workflow = ArchiveWorkflow()
        self.content.addWidget(self.archive_workflow)
        self.history_page = HistoryPage()
        self.history_page.open_folder_requested.connect(self._open_history_folder)
        self.content.addWidget(self.history_page)
        self.content.addWidget(
            self._simple_page(
                "Reclaim storage",
                "Unavailable until archive verification is complete",
                "Reclaim uses separate authorization and will never permanently delete mail.",
            )
        )
        self.problem_report_page = ProblemReportPage()
        self.problem_report_page.save_requested.connect(self._save_diagnostic_report)
        self.problem_report_page.send_requested.connect(self._send_diagnostic_report)
        self.content.addWidget(self.problem_report_page)
        self.content.addWidget(self._settings_page())
        self.help_page = HelpTutorialPage()
        self.content.addWidget(self.help_page)
        self.about_page = AboutPage()
        self.about_page.release_requested.connect(self._open_release_page)
        self.content.addWidget(self.about_page)
        layout.addWidget(self.content, 1)
        self.setCentralWidget(root)

    def _navigation(self) -> QWidget:
        rail = QWidget()
        rail.setObjectName("navigationRail")
        rail.setFixedWidth(218)
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(18, 24, 18, 20)
        layout.setSpacing(5)
        brand = QLabel("de-Mail")
        brand.setObjectName("brand")
        product = QLabel("DESKTOP ARCHIVE")
        product.setObjectName("eyebrow")
        layout.addWidget(brand)
        layout.addWidget(product)
        layout.addSpacing(28)
        self.nav_buttons: list[QPushButton] = []
        for index, (label, _) in enumerate(NAVIGATION):
            button = QPushButton(label)
            button.setProperty("nav", True)
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.clicked.connect(lambda checked=False, page=index: self.show_page(page))
            self.nav_buttons.append(button)
            layout.addWidget(button)
        self.nav_buttons[0].setChecked(True)
        layout.addStretch()
        privacy = QLabel("READ-ONLY GMAIL ACCESS")
        privacy.setObjectName("eyebrow")
        privacy.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(privacy)
        return rail

    def _simple_page(self, eyebrow: str, title: str, description: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(38, 30, 38, 30)
        layout.setSpacing(22)
        heading, _ = page_heading(eyebrow, title, description)
        layout.addWidget(heading)
        card = Card()
        empty = QLabel("This area is ready for the next implementation stage.")
        empty.setObjectName("muted")
        card.layout.addWidget(empty)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(38, 30, 38, 30)
        layout.setSpacing(22)
        heading, _ = page_heading(
            "Settings",
            "Google authorization",
            "Production releases connect with de-Mail's built-in Google identity.",
        )
        layout.addWidget(heading)
        card = Card()
        title = QLabel("Authorization source")
        title.setStyleSheet("font-size: 16px; font-weight: 650;")
        detail = QLabel(
            "Gmail access is read-only. Authorization is protected by Windows and Gmail data is "
            "processed locally, never sent to Liminal servers."
        )
        detail.setObjectName("muted")
        detail.setWordWrap(True)
        self.client_path_input = QLineEdit()
        self.client_path_input.setReadOnly(True)
        self.client_path_input.setPlaceholderText("No Desktop OAuth client selected")
        stored_path = self.settings.value("google/client_path", "", str)
        self.client_path_input.setText(stored_path)
        self.authorization_source_label = QLabel(describe_oauth_source(stored_path))
        self.authorization_source_label.setObjectName("muted")
        self.choose_client_button = QPushButton("Choose client file")
        self.choose_client_button.clicked.connect(self._choose_client_file)
        card.layout.addWidget(title)
        card.layout.addWidget(detail)
        card.layout.addWidget(self.authorization_source_label)
        card.layout.addWidget(self.client_path_input)
        card.layout.addWidget(self.choose_client_button)
        production_client = resolve_oauth_client() if not stored_path else None
        if production_client and production_client.is_production:
            self.client_path_input.hide()
            self.choose_client_button.hide()
        layout.addWidget(card)
        account_card = Card()
        account_title = QLabel("Connected Google account")
        account_title.setStyleSheet("font-size: 16px; font-weight: 650;")
        self.connected_account_label = QLabel("Not connected")
        self.connected_account_label.setObjectName("muted")
        self.disconnect_button = QPushButton("Disconnect Google account")
        self.disconnect_button.setEnabled(False)
        self.reset_authorization_button = QPushButton("Reset authorization")
        self.disconnect_button.clicked.connect(self._disconnect_authorization)
        self.reset_authorization_button.clicked.connect(self._reset_authorization)
        account_card.layout.addWidget(account_title)
        account_card.layout.addWidget(self.connected_account_label)
        account_card.layout.addWidget(self.disconnect_button)
        account_card.layout.addWidget(self.reset_authorization_button)
        layout.addWidget(account_card)
        layout.addStretch()
        return page

    def _choose_client_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Google Desktop OAuth client",
            "",
            "JSON files (*.json)",
        )
        if path:
            self.client_path_input.setText(path)
            self.settings.setValue("google/client_path", path)
            self.authorization_source_label.setText(describe_oauth_source(path))

    def _oauth_client_path(self) -> Path | None:
        try:
            source = resolve_oauth_client(self.client_path_input.text())
        except OAuthClientConfigError:
            return None
        return source.path if source else None

    def attach_connection_controller(self, controller: ConnectionController) -> None:
        self.connection_controller = controller
        self.archive_workflow.connect_requested.connect(self._request_connection)
        controller.started.connect(self.archive_workflow.set_connecting)
        controller.failed.connect(self.archive_workflow.set_connection_error)
        controller.connected.connect(self._connected)

    def attach_authorization_controller(self, controller: AuthorizationController) -> None:
        self.authorization_controller = controller
        controller.disconnected.connect(self._authorization_cleared)
        controller.reset_completed.connect(self._authorization_reset)
        controller.failed.connect(self._authorization_error)

    def _request_connection(self) -> None:
        if self.connection_controller is None:
            return
        if not disclosure_is_current(self.settings):
            dialog = PrivacyDisclosureDialog(self)
            if dialog.exec() != PrivacyDisclosureDialog.DialogCode.Accepted:
                return
            accept_disclosure(self.settings)
        self.connection_controller.connect_mailbox(self._oauth_client_path())

    def _disconnect_authorization(self) -> None:
        if self.authorization_controller:
            self.authorization_controller.disconnect()

    def _reset_authorization(self) -> None:
        if self.authorization_controller:
            self.authorization_controller.reset()

    def _authorization_cleared(self) -> None:
        self.connected_account = None
        self.connected_account_label.setText("Not connected")
        self.disconnect_button.setEnabled(False)
        self.archive_workflow.set_disconnected()

    def _authorization_reset(self) -> None:
        self._authorization_cleared()
        self.client_path_input.clear()
        self.authorization_source_label.setText(describe_oauth_source())

    def _authorization_error(self, message: str) -> None:
        self.connected_account_label.setText(message)

    def attach_update_controller(self, controller: UpdateController) -> None:
        self.update_controller = controller
        self.about_page.check_requested.connect(controller.check)
        controller.started.connect(self.about_page.set_checking)
        controller.completed.connect(self.about_page.show_result)

    def _open_release_page(self, url: str) -> None:
        try:
            open_release_page(url)
        except (OSError, ValueError):
            self.about_page.set_open_error()

    def attach_selection_controller(self, controller: SelectionController) -> None:
        self.selection_controller = controller
        self.archive_workflow.selection_options_requested.connect(controller.load_labels)
        self.archive_workflow.eras_requested.connect(controller.scan_eras)
        self.archive_workflow.manual_candidates_requested.connect(controller.load_candidates)
        self.archive_workflow.exact_count_requested.connect(controller.calculate_exact_count)
        controller.eras_loaded.connect(self.archive_workflow.set_eras)
        controller.labels_loaded.connect(self.archive_workflow.set_labels)
        controller.candidates_loaded.connect(self.archive_workflow.set_manual_candidates)
        controller.exact_count_loaded.connect(self._selection_counted)
        controller.started.connect(self._selection_started)
        controller.failed.connect(self._selection_failed)

    def attach_archive_controller(self, controller: ArchiveController) -> None:
        self.archive_controller = controller
        flow = self.archive_workflow
        flow.destination_requested.connect(self._choose_destination)
        flow.archive_requested.connect(controller.start)
        controller.started.connect(flow.set_archive_started)
        controller.progress.connect(flow.set_archive_progress)
        controller.completed.connect(flow.set_archive_complete)
        controller.failed.connect(flow.set_archive_error)
        self.history_page.resume_requested.connect(self._resume_operation)

    def attach_history_controller(self, controller: HistoryController) -> None:
        self.history_controller = controller
        self.history_page.refresh_requested.connect(controller.load)
        controller.started.connect(self.history_page.set_loading)
        controller.loaded.connect(self.history_page.set_items)
        controller.failed.connect(self.history_page.set_error)
        if self.archive_controller:
            self.archive_controller.completed.connect(lambda _: controller.load())

    def attach_diagnostic_controller(self, controller: DiagnosticController) -> None:
        self.diagnostic_controller = controller
        self.problem_report_page.build_requested.connect(controller.build)
        controller.started.connect(self.problem_report_page.set_building)
        controller.built.connect(self.problem_report_page.set_report)
        controller.failed.connect(self.problem_report_page.set_error)

    def _save_diagnostic_report(self, text: str) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save diagnostic report",
            "de-Mail-report.txt",
            "Text files (*.txt)",
        )
        if not path:
            return
        try:
            save_diagnostic_report(Path(path), text)
        except (OSError, ValueError):
            self.problem_report_page.set_error("The diagnostic report could not be saved.")
            return
        self.problem_report_page.set_saved(path)

    def _send_diagnostic_report(self, text: str) -> None:
        try:
            open_email_draft(REPORT_EMAIL, REPORT_SUBJECT, text)
        except (OSError, ValueError):
            self.problem_report_page.set_delivery_error(
                "The email draft could not be opened. Copy or save the report instead."
            )
            return
        self.problem_report_page.set_email_opened(REPORT_EMAIL)

    def _resume_operation(self, operation_id: int) -> None:
        if self.archive_controller is None:
            self.history_page.set_error("Archive recovery is unavailable.")
            return
        self.show_page(0)
        self.archive_controller.resume(operation_id)

    def _open_history_folder(self, path: str) -> None:
        try:
            open_folder(Path(path))
        except OSError:
            self.history_page.set_error("The archive folder is unavailable.")

    def _choose_destination(self) -> None:
        destination = QFileDialog.getExistingDirectory(
            self,
            "Choose archive destination",
            self.archive_workflow.destination_input.text(),
        )
        if destination:
            self.archive_workflow.set_destination(destination)

    def _connected(self, mailbox: ConnectedMailbox) -> None:
        self.connected_account = mailbox.email_address
        self.connected_account_label.setText(mailbox.email_address)
        self.disconnect_button.setEnabled(True)
        message_word = "message" if mailbox.messages_total == 1 else "messages"
        thread_word = "conversation" if mailbox.threads_total == 1 else "conversations"
        totals = (
            f"{mailbox.messages_total:,} {message_word}, "
            f"{mailbox.threads_total:,} {thread_word}"
        )
        self.archive_workflow.set_connected(mailbox.email_address, totals)
        self.archive_workflow.selection_options_requested.emit()

    def _selection_started(self, context: str) -> None:
        if context == "eras":
            self.archive_workflow.set_era_scan_running()
        elif context == "count":
            self.archive_workflow.set_counting()

    def _selection_failed(self, context: str, message: str) -> None:
        if context == "eras":
            self.archive_workflow.set_era_scan_error(message)
            return
        elif context == "candidates":
            self.archive_workflow.load_candidates_button.setText("Try loading messages again")
            self.archive_workflow.load_candidates_button.setEnabled(True)
        self.archive_workflow.set_selection_error(message)

    def _selection_counted(self, result: tuple[object, int]) -> None:
        criteria, count = result
        try:
            current = self.archive_workflow.selection_criteria()
        except ValueError:
            return
        if criteria == current:
            self.archive_workflow.set_exact_count(count)

    def show_page(self, index: int) -> None:
        if not 0 <= index < self.content.count():
            raise ValueError("Navigation page is out of range")
        self.content.setCurrentIndex(index)
        self.nav_buttons[index].setChecked(True)
        if index == 1 and self.history_controller:
            self.history_controller.load()
        if index == 3 and self.diagnostic_controller:
            self.diagnostic_controller.build(
                self.problem_report_page.what_happened.toPlainText(),
                self.problem_report_page.what_doing.toPlainText(),
            )
