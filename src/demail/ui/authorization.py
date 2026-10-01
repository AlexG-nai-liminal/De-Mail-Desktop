"""Local Google authorization controls and privacy disclosure."""

from typing import Protocol

from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QWidget

DISCLOSURE_VERSION = 1
DISCLOSURE_KEY = "privacy/disclosure_version"


class ClearableCredentialStore(Protocol):
    def clear(self) -> None: ...


class PrivacyDisclosureDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Before connecting Google")
        self.setModal(True)
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        heading = QLabel("Your Gmail stays on this computer")
        heading.setStyleSheet("font-size: 22px; font-weight: 650;")
        explanation = QLabel(
            "de-Mail requests read-only Gmail access. Messages are processed locally and saved "
            "only in the folder you choose. Gmail data is not sent to de-Mail or Liminal "
            "servers. Windows protects the local authorization token."
        )
        explanation.setWordWrap(True)
        detail = QLabel(
            "You can disconnect at any time in Settings. Disconnecting does not delete your "
            "archives or messages."
        )
        detail.setObjectName("muted")
        detail.setWordWrap(True)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        accept = QPushButton("Continue to Google")
        accept.setDefault(True)
        accept.clicked.connect(self.accept)
        layout.addWidget(heading)
        layout.addWidget(explanation)
        layout.addWidget(detail)
        layout.addWidget(cancel)
        layout.addWidget(accept)


class AuthorizationController(QObject):
    disconnected = Signal()
    reset_completed = Signal()
    failed = Signal(str)

    def __init__(
        self,
        credential_store: ClearableCredentialStore,
        settings: QSettings,
    ) -> None:
        super().__init__()
        self.credential_store = credential_store
        self.settings = settings

    def disconnect(self) -> None:
        try:
            self.credential_store.clear()
        except OSError:
            self.failed.emit("The protected Google authorization could not be removed.")
            return
        self.disconnected.emit()

    def reset(self) -> None:
        try:
            self.credential_store.clear()
            self.settings.remove("google/client_path")
            self.settings.remove(DISCLOSURE_KEY)
            self.settings.sync()
        except OSError:
            self.failed.emit("Google authorization could not be reset.")
            return
        self.reset_completed.emit()


def disclosure_is_current(settings: QSettings) -> bool:
    return settings.value(DISCLOSURE_KEY, 0, int) == DISCLOSURE_VERSION


def accept_disclosure(settings: QSettings) -> None:
    settings.setValue(DISCLOSURE_KEY, DISCLOSURE_VERSION)
