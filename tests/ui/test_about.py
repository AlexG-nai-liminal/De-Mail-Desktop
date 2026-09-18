from pathlib import Path

from demail.ui.about import (
    MAX_CHANGELOG_CHARACTERS,
    AboutPage,
    UpdateController,
    load_version_history,
)
from demail.ui.main_window import NAVIGATION, MainWindow
from demail.updates import UpdateResult, UpdateState


class DirectThreadPool:
    def start(self, task) -> None:
        task.run()


def test_about_is_main_navigation_item_below_help(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert NAVIGATION[-3:] == (
        ("Settings", "settings"),
        ("Help", "help"),
        ("About", "about"),
    )
    window.nav_buttons[-1].click()

    assert window.content.currentWidget() is window.about_page
    assert window.about_page.check_button.text() == "Check for update"
    assert "Version 0.2.0" in [
        label.text()
        for label in window.about_page.findChildren(type(window.about_page.status_label))
    ]


def test_about_page_shows_available_update_without_downloading_it(qtbot) -> None:
    page = AboutPage("# Version history")
    qtbot.addWidget(page)
    opened: list[str] = []
    page.release_requested.connect(opened.append)

    page.set_checking()
    assert not page.check_button.isEnabled()
    assert page.check_button.text() == "Checking..."
    page.show_result(
        UpdateResult(
            UpdateState.AVAILABLE,
            "0.2.0",
            "0.3.0",
            "https://github.com/AlexG-nai-liminal/de-mail-desktop-releases/releases/tag/v0.3.0",
        )
    )

    assert page.check_button.text() == "Check for update"
    assert page.release_button.isVisibleTo(page)
    assert "0.3.0 is available" in page.status_label.text()
    page.release_button.click()
    assert opened == [
        "https://github.com/AlexG-nai-liminal/de-mail-desktop-releases/releases/tag/v0.3.0"
    ]


def test_about_page_handles_current_and_unavailable_results(qtbot) -> None:
    page = AboutPage("history")
    qtbot.addWidget(page)
    page.show_result(UpdateResult(UpdateState.CURRENT, "0.2.0", "0.2.0"))
    assert "up to date" in page.status_label.text()
    assert not page.release_button.isVisible()

    page.show_result(UpdateResult(UpdateState.UNAVAILABLE, "0.2.0"))
    assert "could not be reached" in page.status_label.text()
    assert page.check_button.isEnabled()


def test_update_controller_recovers_from_unexpected_checker_failure(qtbot) -> None:
    del qtbot

    def fail():
        raise RuntimeError("secret server detail")

    controller = UpdateController(fail, DirectThreadPool())
    results = []
    controller.completed.connect(results.append)
    controller.check()

    assert results == [UpdateResult(UpdateState.UNAVAILABLE, "0.2.0")]
    assert not controller._tasks


def test_version_history_loads_utf8_and_is_bounded(tmp_path: Path) -> None:
    history = tmp_path / "CHANGELOG.md"
    history.write_text("Version history\n" + "x" * MAX_CHANGELOG_CHARACTERS, encoding="utf-8")

    loaded = load_version_history(history)

    assert loaded.startswith("Version history")
    assert len(loaded) == MAX_CHANGELOG_CHARACTERS


def test_missing_or_malformed_version_history_has_safe_fallback(tmp_path: Path) -> None:
    assert "unavailable" in load_version_history(tmp_path / "missing.md")
    malformed = tmp_path / "CHANGELOG.md"
    malformed.write_bytes(b"\xff\xfe")
    assert "unavailable" in load_version_history(malformed)
