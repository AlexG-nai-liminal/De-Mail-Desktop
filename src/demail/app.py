"""Application entry point."""

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QImageReader
from PySide6.QtWidgets import QApplication

from demail import __version__
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
from demail.ui.about import UpdateController
from demail.ui.archive import ArchiveController
from demail.ui.connection import ConnectionController, GoogleConnectionService
from demail.ui.diagnostics import DiagnosticController
from demail.ui.history import HistoryController
from demail.ui.main_window import MainWindow
from demail.ui.selection import SelectionController
from demail.ui.theme import apply_theme
from demail.windows.paths import application_paths


def run_selftest(asset_root: Path | None = None) -> None:
    """Validate resources required by the frozen application before packaging."""
    from demail.ui.help import TUTORIAL_SLIDES

    root = asset_root or Path(__file__).resolve().parent / "assets"
    required = [root / "de-mail.ico"]
    required.extend(root / "tutorial" / slide.image_name for slide in TUTORIAL_SLIDES)
    failures: list[str] = []
    for path in required:
        if not path.is_file() or path.stat().st_size == 0:
            failures.append(f"missing resource: {path.name}")
        elif not QImageReader(str(path)).canRead():
            failures.append(f"unreadable image: {path.name}")
    if failures:
        raise RuntimeError("Frozen-build self-test failed: " + "; ".join(failures))


def _create_application(arguments: list[str]) -> QApplication:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    application = QApplication([sys.argv[0], *arguments])
    application.setApplicationName("de-Mail Desktop")
    application.setOrganizationName("de-Mail")
    application.setWindowIcon(
        QIcon(str(Path(__file__).resolve().parent / "assets" / "de-mail.ico"))
    )
    apply_theme(application)
    return application


def _run_launch_test(arguments: list[str]) -> int:
    application = _create_application(arguments)
    window = MainWindow()
    window.attach_update_controller(UpdateController())
    window.show()
    QTimer.singleShot(250, application.quit)
    return application.exec()


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    modes = {argument for argument in arguments if argument in {"--selftest", "--launchtest"}}
    if len(modes) > 1:
        print("Choose only one release-test mode.", file=sys.stderr)
        return 2
    if "--selftest" in modes:
        run_selftest()
        return 0
    if "--launchtest" in modes:
        arguments.remove("--launchtest")
        return _run_launch_test(arguments)
    if "--version" in arguments:
        print(__version__)
        return 0

    application = _create_application(arguments)
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
    window.attach_update_controller(UpdateController())
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
