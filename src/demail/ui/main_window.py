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

from .archive_flow import ArchiveWorkflow
from .components import Card, page_heading
from .connection import ConnectedMailbox, ConnectionController

NAVIGATION = (
    ("Archive Gmail", "archive"),
    ("History", "history"),
    ("Reclaim storage", "reclaim"),
    ("Report a problem", "report"),
    ("Settings", "settings"),
)


class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings | None = None) -> None:
        super().__init__()
        self.settings = settings or QSettings("de-Mail", "de-Mail Desktop")
        self.connection_controller: ConnectionController | None = None
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
        self.content.addWidget(
            self._simple_page("History", "Your archive operations", "No archives yet.")
        )
        self.content.addWidget(
            self._simple_page(
                "Reclaim storage",
                "Unavailable until archive verification is complete",
                "Reclaim uses separate authorization and will never permanently delete mail.",
            )
        )
        self.content.addWidget(
            self._simple_page(
                "Report a problem",
                "Review diagnostics before sharing",
                "Nothing is sent automatically. Sensitive mail details and credentials "
                "are excluded.",
            )
        )
        self.content.addWidget(self._settings_page())
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
            "Use a Desktop app OAuth client from the same Google Cloud project as the Android app.",
        )
        layout.addWidget(heading)
        card = Card()
        title = QLabel("Desktop OAuth client file")
        title.setStyleSheet("font-size: 16px; font-weight: 650;")
        detail = QLabel(
            "This file identifies the application. User access and refresh credentials are stored "
            "separately with Windows protection."
        )
        detail.setObjectName("muted")
        detail.setWordWrap(True)
        self.client_path_input = QLineEdit()
        self.client_path_input.setReadOnly(True)
        self.client_path_input.setPlaceholderText("No Desktop OAuth client selected")
        stored_path = self.settings.value("google/client_path", "", str)
        self.client_path_input.setText(stored_path)
        self.choose_client_button = QPushButton("Choose client file")
        self.choose_client_button.clicked.connect(self._choose_client_file)
        card.layout.addWidget(title)
        card.layout.addWidget(detail)
        card.layout.addWidget(self.client_path_input)
        card.layout.addWidget(self.choose_client_button)
        layout.addWidget(card)
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

    def attach_connection_controller(self, controller: ConnectionController) -> None:
        self.connection_controller = controller
        self.archive_workflow.connect_requested.connect(
            lambda: controller.connect_mailbox(self.client_path_input.text())
        )
        controller.started.connect(self.archive_workflow.set_connecting)
        controller.failed.connect(self.archive_workflow.set_connection_error)
        controller.connected.connect(self._connected)

    def _connected(self, mailbox: ConnectedMailbox) -> None:
        message_word = "message" if mailbox.messages_total == 1 else "messages"
        thread_word = "conversation" if mailbox.threads_total == 1 else "conversations"
        totals = (
            f"{mailbox.messages_total:,} {message_word}, "
            f"{mailbox.threads_total:,} {thread_word}"
        )
        self.archive_workflow.set_connected(mailbox.email_address, totals)

    def show_page(self, index: int) -> None:
        if not 0 <= index < self.content.count():
            raise ValueError("Navigation page is out of range")
        self.content.setCurrentIndex(index)
        self.nav_buttons[index].setChecked(True)
