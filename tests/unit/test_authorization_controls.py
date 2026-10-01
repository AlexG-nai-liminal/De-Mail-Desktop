from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtTest import QSignalSpy

from demail.ui.authorization import (
    DISCLOSURE_KEY,
    DISCLOSURE_VERSION,
    AuthorizationController,
    accept_disclosure,
    disclosure_is_current,
)


class RecordingStore:
    def __init__(self, error: OSError | None = None) -> None:
        self.clear_count = 0
        self.error = error

    def clear(self) -> None:
        self.clear_count += 1
        if self.error:
            raise self.error


def settings_at(path: Path) -> QSettings:
    return QSettings(str(path), QSettings.Format.IniFormat)


def test_disconnect_removes_only_credentials(tmp_path: Path) -> None:
    settings = settings_at(tmp_path / "settings.ini")
    settings.setValue("google/client_path", "development.json")
    accept_disclosure(settings)
    store = RecordingStore()
    controller = AuthorizationController(store, settings)
    disconnected = QSignalSpy(controller.disconnected)

    controller.disconnect()

    assert store.clear_count == 1
    assert disconnected.count() == 1
    assert settings.value("google/client_path") == "development.json"
    assert disclosure_is_current(settings)


def test_reset_clears_credentials_client_choice_and_disclosure(tmp_path: Path) -> None:
    settings = settings_at(tmp_path / "settings.ini")
    settings.setValue("google/client_path", "development.json")
    accept_disclosure(settings)
    store = RecordingStore()
    controller = AuthorizationController(store, settings)
    reset = QSignalSpy(controller.reset_completed)

    controller.reset()

    assert store.clear_count == 1
    assert reset.count() == 1
    assert settings.value("google/client_path") is None
    assert not disclosure_is_current(settings)


def test_clear_failure_is_reported_without_success(tmp_path: Path) -> None:
    controller = AuthorizationController(
        RecordingStore(PermissionError("private path")), settings_at(tmp_path / "settings.ini")
    )
    failed = QSignalSpy(controller.failed)
    disconnected = QSignalSpy(controller.disconnected)
    controller.disconnect()
    assert failed.count() == 1
    assert disconnected.count() == 0
    assert "private path" not in failed.at(0)[0]


def test_old_or_malformed_disclosure_values_are_not_accepted(tmp_path: Path) -> None:
    settings = settings_at(tmp_path / "settings.ini")
    for value in (DISCLOSURE_VERSION - 1, "invalid", -1):
        settings.setValue(DISCLOSURE_KEY, value)
        assert not disclosure_is_current(settings)
