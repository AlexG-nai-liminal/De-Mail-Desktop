"""Application entry point."""

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from demail.auth.dpapi import DpapiProtector
from demail.auth.oauth import OAuthAuthorization
from demail.auth.token_provider import GoogleTokenProvider
from demail.auth.token_store import CredentialStore
from demail.persistence.database import Database
from demail.ui.connection import ConnectionController, GoogleConnectionService
from demail.ui.main_window import MainWindow
from demail.ui.theme import apply_theme
from demail.windows.paths import application_paths


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    application = QApplication(sys.argv)
    application.setApplicationName("de-Mail Desktop")
    application.setOrganizationName("de-Mail")
    apply_theme(application)
    paths = application_paths()
    paths.data.mkdir(parents=True, exist_ok=True)
    Database(paths.database).migrate()
    credential_store = CredentialStore(paths.authorization, DpapiProtector())

    def connection_service(client_path):
        authorization = OAuthAuthorization(client_path, credential_store)
        tokens = GoogleTokenProvider(credential_store)
        return GoogleConnectionService(client_path, authorization, tokens)

    window = MainWindow()
    controller = ConnectionController(connection_service)
    window.attach_connection_controller(controller)
    window.show()
    return application.exec()
