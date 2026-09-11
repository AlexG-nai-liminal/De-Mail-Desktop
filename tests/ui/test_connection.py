import time
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtTest import QSignalSpy

from demail.ui.connection import ConnectedMailbox, ConnectionController
from demail.ui.main_window import MainWindow


class SuccessfulService:
    def connect(self) -> ConnectedMailbox:
        return ConnectedMailbox("archive@example.com", 12_345, 9_876)


class FailingService:
    def connect(self) -> ConnectedMailbox:
        raise RuntimeError("secret server response")


def wait_for(spy: QSignalSpy, qtbot) -> None:
    deadline = time.monotonic() + 3
    while spy.count() == 0 and time.monotonic() < deadline:
        qtbot.wait(10)
    assert spy.count() == 1


def test_missing_client_file_fails_without_starting_worker(tmp_path: Path, qtbot) -> None:
    controller = ConnectionController(lambda _: SuccessfulService())
    failed = QSignalSpy(controller.failed)
    started = QSignalSpy(controller.started)
    controller.connect_mailbox(str(tmp_path / "missing.json"))
    assert failed.count() == 1
    assert started.count() == 0
    assert "Settings" in failed.at(0)[0]


def test_successful_connection_runs_off_ui_thread_and_updates_window(
    tmp_path: Path, qtbot
) -> None:
    client_path = tmp_path / "client.json"
    client_path.write_text("{}", encoding="utf-8")
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("google/client_path", str(client_path))
    controller = ConnectionController(lambda _: SuccessfulService())
    window = MainWindow(settings)
    window.attach_connection_controller(controller)
    qtbot.addWidget(window)
    connected = QSignalSpy(controller.connected)
    window.archive_workflow.connect_requested.emit()
    wait_for(connected, qtbot)
    assert "archive@example.com" in window.archive_workflow.account_status.text()
    assert "12,345 messages" in window.archive_workflow.account_status.text()
    assert window.archive_workflow.next_button.isEnabled()


def test_background_failure_is_privacy_safe(tmp_path: Path, qtbot) -> None:
    client_path = tmp_path / "client.json"
    client_path.write_text("{}", encoding="utf-8")
    controller = ConnectionController(lambda _: FailingService())
    failed = QSignalSpy(controller.failed)
    controller.connect_mailbox(str(client_path))
    wait_for(failed, qtbot)
    message = failed.at(0)[0]
    assert "secret server response" not in message
    assert "could not be connected" in message
