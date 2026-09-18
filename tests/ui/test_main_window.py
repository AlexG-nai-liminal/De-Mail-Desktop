from collections.abc import Iterator

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

from demail.ui.archive_flow import STEP_NAMES, ArchiveWorkflow
from demail.ui.main_window import NAVIGATION, MainWindow
from demail.ui.theme import BLACK, CARD, PANEL, STYLE_SHEET, WHITE, apply_theme


def descendants(widget: QWidget) -> Iterator[QWidget]:
    yield widget
    yield from widget.findChildren(QWidget)


def visible_text(widget: QWidget) -> str:
    values: list[str] = []
    for child in descendants(widget):
        if isinstance(child, QLabel | QPushButton):
            values.append(child.text())
    return "\n".join(values)


def test_main_window_has_requested_navigation_and_minimum_desktop_size(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.minimumWidth() >= 960
    assert window.minimumHeight() >= 640
    assert [button.text() for button in window.nav_buttons] == [item[0] for item in NAVIGATION]
    assert window.nav_buttons[0].isChecked()
    assert window.content.currentIndex() == 0
    assert [button.text() for button in window.nav_buttons[-2:]] == ["Settings", "Help"]


def test_navigation_switches_one_content_page_at_a_time(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    qtbot.mouseClick(window.nav_buttons[1], Qt.MouseButton.LeftButton)
    assert window.content.currentIndex() == 1
    assert window.nav_buttons[1].isChecked()
    assert not window.nav_buttons[0].isChecked()


def test_navigation_rejects_out_of_range_page(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    with pytest.raises(ValueError, match="out of range"):
        window.show_page(99)


def test_archive_flow_requires_connection_before_continue(qtbot) -> None:
    flow = ArchiveWorkflow()
    qtbot.addWidget(flow)
    assert flow.current_step == 0
    assert not flow.next_button.isEnabled()
    flow.set_connected("archive@example.com", "42 messages")
    assert flow.next_button.isEnabled()
    qtbot.mouseClick(flow.next_button, Qt.MouseButton.LeftButton)
    assert flow.current_step == 1


def test_exact_count_gate_and_boundary_values(qtbot) -> None:
    flow = ArchiveWorkflow()
    qtbot.addWidget(flow)
    flow.set_connected("archive@example.com", "42 messages")
    flow.set_step(2)
    assert not flow.next_button.isEnabled()
    flow.set_exact_count(0)
    assert flow.count_label.text() == "0 messages selected"
    assert flow.next_button.isEnabled()
    flow.set_exact_count(1)
    assert flow.count_label.text() == "1 message selected"
    with pytest.raises(ValueError, match="negative"):
        flow.set_exact_count(-1)


def test_workflow_has_all_required_stages_and_rejects_invalid_step(qtbot) -> None:
    flow = ArchiveWorkflow()
    qtbot.addWidget(flow)
    assert STEP_NAMES == (
        "Connect",
        "Select",
        "Review",
        "Destination",
        "Archive",
        "Verify",
        "Complete",
    )
    assert flow.pages.count() == len(STEP_NAMES)
    with pytest.raises(ValueError, match="out of range"):
        flow.set_step(-1)


def test_user_facing_widget_text_contains_no_dash_characters(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    text = visible_text(window)
    assert "—" not in text
    assert "–" not in text


def test_theme_is_nearly_black_with_white_text_and_dark_gray_cards(qapp) -> None:
    apply_theme(qapp)
    palette = QApplication.palette()
    assert palette.window().color().name().upper() == BLACK.upper()
    assert palette.windowText().color().name().upper() == WHITE.upper()
    assert PANEL in qapp.styleSheet()
    assert CARD in qapp.styleSheet()
    assert 'QPushButton[primary="true"]:disabled' in STYLE_SHEET
    assert "background: #303030" in STYLE_SHEET


def test_problem_report_email_draft_uses_fixed_recipient(
    qtbot, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        "demail.ui.main_window.open_email_draft",
        lambda recipient, subject, body: opened.append((recipient, subject, body)),
    )
    window = MainWindow()
    qtbot.addWidget(window)
    window.problem_report_page.set_report("reviewed report")

    window.problem_report_page.send_button.click()

    assert opened == [
        ("alex@liminalmemory.com", "de-Mail Desktop problem report", "reviewed report")
    ]
    assert "draft opened" in window.problem_report_page.delivery_status.text().lower()


def test_problem_report_email_failure_keeps_copy_and_save_available(
    qtbot, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*_args) -> None:
        raise OSError("no mail application")

    monkeypatch.setattr("demail.ui.main_window.open_email_draft", fail)
    window = MainWindow()
    qtbot.addWidget(window)
    window.problem_report_page.set_report("reviewed report")

    window.problem_report_page.send_button.click()

    assert "could not be opened" in window.problem_report_page.delivery_status.text()
    assert window.problem_report_page.copy_button.isEnabled()
    assert window.problem_report_page.save_button.isEnabled()
