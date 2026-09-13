"""Application entry point."""

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from demail.auth.dpapi import DpapiProtector
from demail.auth.oauth import OAuthAuthorization
from demail.auth.token_provider import GoogleTokenProvider
from demail.auth.token_store import CredentialStore
from demail.diagnostics.collector import DiagnosticCollector
from demail.gmail.client import GmailClient
from demail.gmail.selection_service import MailboxSelectionService
from demail.jobs.archive_operation import ArchiveOperationEngine
from demail.persistence.archive_repository import ArchiveRepository
from demail.persistence.database import Database
from demail.ui.archive import ArchiveController
from demail.ui.connection import ConnectionController, GoogleConnectionService
from demail.ui.diagnostics import DiagnosticController
from demail.ui.history import HistoryController
from demail.ui.main_window import MainWindow
from demail.ui.selection import SelectionController
from demail.ui.theme import apply_theme
from demail.windows.paths import application_paths


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    application = QApplication(sys.argv)
    application.setApplicationName("de-Mail Desktop")
    application.setOrganizationName("de-Mail")
    application.setWindowIcon(
        QIcon(str(Path(__file__).resolve().parent / "assets" / "de-mail.ico"))
    )
    apply_theme(application)
    paths = application_paths()
    paths.data.mkdir(parents=True, exist_ok=True)
    database = Database(paths.database)
    database.migrate()
    credential_store = CredentialStore(paths.authorization, DpapiProtector())

    def connection_service(client_path):
        authorization = OAuthAuthorization(client_path, credential_store)
        tokens = GoogleTokenProvider(credential_store)
        return GoogleConnectionService(client_path, authorization, tokens)

    window = MainWindow()
    controller = ConnectionController(connection_service)
    window.attach_connection_controller(controller)
    selection_controller = SelectionController(
        lambda: MailboxSelectionService(GmailClient(GoogleTokenProvider(credential_store)))
    )
    window.attach_selection_controller(selection_controller)
    archive_controller = ArchiveController(
        lambda: ArchiveOperationEngine(
            GmailClient(GoogleTokenProvider(credential_store)),
            ArchiveRepository(database),
        )
    )
    window.attach_archive_controller(archive_controller)
    window.attach_history_controller(HistoryController(lambda: ArchiveRepository(database)))
    window.attach_diagnostic_controller(
        DiagnosticController(
            lambda: DiagnosticCollector(ArchiveRepository(database), paths.data),
            lambda: window.connected_account,
        )
    )
    window.show()
    return application.exec()
