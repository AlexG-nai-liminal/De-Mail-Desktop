"""Background connection service and Qt controller."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from demail.auth.oauth import OAuthAuthorization
from demail.auth.token_provider import GoogleTokenProvider
from demail.gmail.client import GmailApiError, GmailClient


@dataclass(frozen=True, slots=True)
class ConnectedMailbox:
    email_address: str
    messages_total: int
    threads_total: int


class ConnectionService(Protocol):
    def connect(self) -> ConnectedMailbox: ...


class GoogleConnectionService:
    def __init__(
        self,
        client_path: Path,
        authorization: OAuthAuthorization,
        tokens: GoogleTokenProvider,
        gmail_factory: Callable[[GoogleTokenProvider], GmailClient] = GmailClient,
    ) -> None:
        self.client_path = client_path
        self.authorization = authorization
        self.tokens = tokens
        self.gmail_factory = gmail_factory

    def connect(self) -> ConnectedMailbox:
        # Reuse protected authorization when possible. A revoked or unusable
        # grant returns to the explicit system-browser flow.
        try:
            profile = self.gmail_factory(self.tokens).profile()
        except PermissionError:
            self.authorization.authorize_with_system_browser()
            profile = self.gmail_factory(self.tokens).profile()
        except GmailApiError as error:
            if error.status_code not in {401, 403}:
                raise
            self.authorization.authorize_with_system_browser()
            profile = self.gmail_factory(self.tokens).profile()
        return ConnectedMailbox(
            email_address=profile.email_address,
            messages_total=profile.messages_total,
            threads_total=profile.threads_total,
        )


class _TaskSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str)


class _ConnectionTask(QRunnable):
    def __init__(self, service: ConnectionService) -> None:
        super().__init__()
        self.service = service
        self.signals = _TaskSignals()

    def run(self) -> None:
        try:
            self.signals.succeeded.emit(self.service.connect())
        except Exception:
            self.signals.failed.emit(
                "Google could not be connected. Check the Desktop OAuth configuration "
                "and try again."
            )


class ConnectionController(QObject):
    started = Signal()
    connected = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        service_factory: Callable[[Path], ConnectionService],
        thread_pool: QThreadPool | None = None,
    ) -> None:
        super().__init__()
        self.service_factory = service_factory
        self.thread_pool = thread_pool or QThreadPool.globalInstance()
        self._tasks: set[_ConnectionTask] = set()

    def connect_mailbox(self, client_path: str | Path | None) -> None:
        path = Path(client_path) if client_path else None
        if path is None or not path.is_file():
            self.failed.emit("Google authorization is not configured yet.")
            return
        task = _ConnectionTask(self.service_factory(path))
        self._tasks.add(task)
        task.signals.succeeded.connect(lambda result: self._finish_success(task, result))
        task.signals.failed.connect(lambda message: self._finish_failure(task, message))
        self.started.emit()
        self.thread_pool.start(task)

    def _finish_success(self, task: _ConnectionTask, result: ConnectedMailbox) -> None:
        self._tasks.discard(task)
        self.connected.emit(result)

    def _finish_failure(self, task: _ConnectionTask, message: str) -> None:
        self._tasks.discard(task)
        self.failed.emit(message)
