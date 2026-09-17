from datetime import date
from pathlib import Path

import pytest
from PySide6.QtCore import QAbstractAnimation, Qt

from demail.domain.eras import Era, EraKind
from demail.gmail.client import GmailLabel, GmailMessageMetadata
from demail.jobs.archive_operation import ArchiveProgress
from demail.ui.archive import ArchiveRunResult
from demail.ui.archive_flow import ArchiveWorkflow


def mailbox_thirds() -> tuple[Era, Era, Era]:
    return (
        Era(EraKind.FAR_PAST, None, date(2012, 1, 1), 1_001),
        Era(EraKind.RECENT_PAST, date(2012, 1, 1), date(2021, 1, 1), 998),
        Era(EraKind.PRESENT, date(2021, 1, 1), None, 1_000),
    )


def test_selection_modes_show_only_relevant_controls(qtbot) -> None:
    flow = ArchiveWorkflow()
    qtbot.addWidget(flow)
    flow.set_step(1)
    flow.show()
    flow.selection_mode.setCurrentText("Sender")
    assert not flow.era_combo.isVisibleTo(flow)
    assert flow.sender_input.isVisibleTo(flow)
    assert not flow.manual_candidates.isVisibleTo(flow)
    flow.selection_mode.setCurrentText("Manual selection")
    assert flow.sender_input.isVisibleTo(flow)
    assert flow.manual_candidates.isVisibleTo(flow)


def test_labels_preserve_exact_gmail_id(qtbot) -> None:
    flow = ArchiveWorkflow()
    qtbot.addWidget(flow)
    flow.set_labels((GmailLabel("Label_42", "Receipts", "user"),))
    flow.selection_mode.setCurrentText("Gmail label")
    criteria = flow.selection_criteria()
    assert criteria.label_id == "Label_42"
    assert criteria.label_name == "Receipts"


def test_era_selection_uses_exact_date_boundaries(qtbot) -> None:
    flow = ArchiveWorkflow()
    qtbot.addWidget(flow)
    era = Era(EraKind.FAR_PAST, None, date(2020, 1, 1), 1_234)
    flow.set_eras((era,))
    criteria = flow.selection_criteria()
    assert criteria.start_date is None
    assert criteria.end_date == "2019-12-31"


def test_quick_archive_is_one_three_part_selector(qtbot) -> None:
    flow = ArchiveWorkflow()
    qtbot.addWidget(flow)

    assert flow.quick_archive_container.layout().spacing() == 0
    assert len(flow.quick_archive_buttons) == 3
    assert [button.property("segmentPosition") for button in flow.quick_archive_buttons] == [
        "first",
        "middle",
        "last",
    ]
    assert all("33.33%" in button.text() for button in flow.quick_archive_buttons)


def test_quick_archive_click_calculates_then_selects_requested_third(qtbot) -> None:
    flow = ArchiveWorkflow()
    qtbot.addWidget(flow)
    flow.include_spam.setChecked(True)

    with qtbot.waitSignal(flow.eras_requested) as request:
        flow.quick_archive_buttons[1].click()

    assert request.args == [True]
    assert not any(button.isEnabled() for button in flow.quick_archive_buttons)
    flow.set_eras(mailbox_thirds())
    assert flow.selection_mode.currentText() == "Quick archive thirds"
    assert flow.quick_archive_buttons[1].isChecked()
    assert flow.selection_criteria().start_date == "2012-01-01"
    assert flow.selection_criteria().end_date == "2020-12-31"
    assert "998" in flow.quick_archive_buttons[1].text()


def test_loaded_quick_archive_third_switches_from_detailed_selection(qtbot) -> None:
    flow = ArchiveWorkflow()
    qtbot.addWidget(flow)
    flow.set_eras(mailbox_thirds())
    flow.selection_mode.setCurrentText("Gmail search")
    flow.search_input.setText("has:attachment")

    flow.quick_archive_buttons[2].click()

    assert flow.selection_mode.currentText() == "Quick archive thirds"
    assert flow.selection_criteria().start_date == "2021-01-01"
    assert flow.selection_criteria().end_date is None


def test_quick_archive_allows_two_nonadjacent_thirds(qtbot) -> None:
    flow = ArchiveWorkflow()
    qtbot.addWidget(flow)
    flow.set_eras(mailbox_thirds())

    flow.quick_archive_buttons[0].click()
    flow.quick_archive_buttons[2].click()

    criteria = flow.selection_criteria()
    assert [button.isChecked() for button in flow.quick_archive_buttons] == [True, False, True]
    assert criteria.start_date is None
    assert criteria.end_date is None
    assert criteria.date_ranges == ((None, "2011-12-31"), ("2021-01-01", None))


def test_quick_archive_allows_all_three_thirds_as_whole_mailbox(qtbot) -> None:
    flow = ArchiveWorkflow()
    qtbot.addWidget(flow)
    flow.set_eras(mailbox_thirds())
    for button in flow.quick_archive_buttons:
        button.click()

    criteria = flow.selection_criteria()
    assert all(button.isChecked() for button in flow.quick_archive_buttons)
    assert criteria.is_whole_mailbox


def test_quick_archive_requires_one_checked_third(qtbot) -> None:
    flow = ArchiveWorkflow()
    qtbot.addWidget(flow)
    flow.set_eras(mailbox_thirds())
    flow.quick_archive_buttons[0].click()
    flow.quick_archive_buttons[0].click()

    with pytest.raises(ValueError, match="at least one"):
        flow.selection_criteria()


def test_mailbox_that_cannot_form_thirds_fails_safely(qtbot) -> None:
    flow = ArchiveWorkflow()
    qtbot.addWidget(flow)
    flow.set_eras((Era(EraKind.PRESENT, None, None, 2),))

    assert not any(button.isEnabled() for button in flow.quick_archive_buttons)
    assert all("Unavailable" in button.text() for button in flow.quick_archive_buttons)


def test_quick_archive_scan_failure_is_retryable(qtbot) -> None:
    flow = ArchiveWorkflow()
    qtbot.addWidget(flow)
    flow.quick_archive_buttons[0].click()

    flow.set_era_scan_error("Gmail selection could not be loaded.")

    assert all(button.isEnabled() for button in flow.quick_archive_buttons)
    assert all("33.33%" in button.text() for button in flow.quick_archive_buttons)
    assert "could not be loaded" in flow.selection_error.text()


def test_selection_fields_have_room_for_full_text(qtbot) -> None:
    flow = ArchiveWorkflow()
    qtbot.addWidget(flow)
    flow.resize(960, 720)
    flow.set_step(1)
    flow.show()

    fields = (
        flow.selection_mode,
        flow.era_combo,
        flow.start_date,
        flow.end_date,
        flow.sender_input,
        flow.search_input,
        flow.label_combo,
    )
    assert all(field.minimumHeight() >= 42 for field in fields)
    assert flow.selection_mode.height() >= flow.selection_mode.fontMetrics().height() + 16


def test_manual_candidates_become_explicit_message_ids(qtbot) -> None:
    flow = ArchiveWorkflow()
    qtbot.addWidget(flow)
    flow.selection_mode.setCurrentText("Manual selection")
    flow.set_manual_candidates(
        (
            GmailMessageMetadata("a", None, None, "First", "a@example.com", ()),
            GmailMessageMetadata("b", None, None, "Second", "b@example.com", ()),
        )
    )
    flow.manual_candidates.item(1).setCheckState(Qt.CheckState.Checked)
    assert flow.selection_criteria().explicit_message_ids == ("b",)


def test_invalid_selection_stays_on_page_and_shows_reason(qtbot) -> None:
    flow = ArchiveWorkflow()
    qtbot.addWidget(flow)
    flow.selection_mode.setCurrentText("Sender")
    with pytest.raises(ValueError, match="Sender"):
        flow.selection_criteria()


def test_exact_count_request_emits_immutable_criteria(qtbot) -> None:
    flow = ArchiveWorkflow()
    qtbot.addWidget(flow)
    flow.selection_mode.setCurrentText("Gmail search")
    flow.search_input.setText("has:attachment")
    with qtbot.waitSignal(flow.exact_count_requested) as blocker:
        flow.count_button.click()
    assert blocker.args[0].search_query == "has:attachment"
    assert not flow.count_button.isEnabled()


def test_changing_selection_invalidates_a_completed_count(qtbot) -> None:
    flow = ArchiveWorkflow()
    qtbot.addWidget(flow)
    flow.selection_mode.setCurrentText("Gmail search")
    flow.search_input.setText("older:2020/01/01")
    flow.set_step(2)
    flow.set_exact_count(42)
    assert flow.next_button.isEnabled()
    flow.search_input.setText("newer:2020/01/01")
    assert flow.count_label.text() == "Count not calculated"
    assert not flow.next_button.isEnabled()


def test_invalid_date_range_cannot_advance_to_review(qtbot) -> None:
    flow = ArchiveWorkflow()
    qtbot.addWidget(flow)
    flow._connected = True
    flow.set_step(1)
    flow.selection_mode.setCurrentText("Date range")
    flow.start_date.setDate(flow.end_date.date().addDays(1))
    flow.go_forward()
    assert flow.current_step == 1
    assert "start date" in flow.selection_error.text().lower()


def test_destination_is_required_before_archive_start(qtbot, tmp_path: Path) -> None:
    flow = ArchiveWorkflow()
    qtbot.addWidget(flow)
    flow.selection_mode.setCurrentText("Gmail search")
    flow.search_input.setText("has:attachment")
    flow.set_exact_count(1)
    flow.set_step(3)
    assert not flow.next_button.isEnabled()
    with pytest.raises(ValueError, match="existing"):
        flow.set_destination(str(tmp_path / "missing"))
    flow.set_destination(str(tmp_path))
    assert flow.next_button.isEnabled()
    with qtbot.waitSignal(flow.archive_requested) as request:
        flow.next_button.click()
    assert request.args[0].search_query == "has:attachment"
    assert request.args[1] == str(tmp_path)


def test_archive_progress_and_verified_report(qtbot, tmp_path: Path) -> None:
    flow = ArchiveWorkflow()
    qtbot.addWidget(flow)
    flow.set_archive_started()
    assert flow.current_step == 4
    assert not flow.back_button.isEnabled()
    flow.set_archive_progress(ArchiveProgress("export", 1, 2))
    assert flow.archive_progress.value() == 1
    flow.set_archive_progress(ArchiveProgress("verify", 2, 2))
    assert flow.current_step == 5
    result = ArchiveRunResult(7, "VERIFIED", 2, 2, 2, 0, 1536, tmp_path)
    flow.set_archive_complete(result)
    assert flow.current_step == 5
    assert flow.next_button.isEnabled()
    assert flow.next_button_fade.state() == QAbstractAnimation.State.Running
    assert flow.next_button_effect.opacity() < 1.0
    assert flow.verify_label.text() == "Verification complete. Continue to the archive report."
    qtbot.waitUntil(lambda: flow.next_button_effect.opacity() == 1.0, timeout=1_000)
    flow.next_button.click()
    assert flow.current_step == 6
    assert flow.report_title.text() == "Archive verified"
    assert "1.5 KB" in flow.report_detail.text()
    assert flow.next_button.text() == "Archive more"


def test_archive_more_returns_to_connected_start_and_clears_previous_run(
    qtbot, tmp_path: Path
) -> None:
    flow = ArchiveWorkflow()
    qtbot.addWidget(flow)
    flow.set_connected("archive@example.com", "3,000 messages")
    flow.set_eras(mailbox_thirds())
    flow.quick_archive_buttons[0].click()
    flow.set_exact_count(1_001)
    flow.set_destination(str(tmp_path))
    flow.set_archive_started()
    flow.set_archive_complete(
        ArchiveRunResult(1, "VERIFIED", 1_001, 1_001, 1_001, 0, 1024, tmp_path)
    )
    flow.next_button.click()
    assert flow.current_step == 6

    flow.next_button.click()

    assert flow.current_step == 0
    assert flow.next_button.text() == "Continue"
    assert flow.next_button.isEnabled()
    assert flow.count_label.text() == "Count not calculated"
    assert not flow.destination_input.text()
    assert not any(button.isChecked() for button in flow.quick_archive_buttons)
    assert flow.selection_mode.currentText() == "Quick archive thirds"


def test_running_archive_cannot_be_reset(qtbot) -> None:
    flow = ArchiveWorkflow()
    qtbot.addWidget(flow)
    flow.set_archive_started()
    with pytest.raises(RuntimeError, match="progress"):
        flow.reset_for_another_archive()


def test_archive_failure_message_does_not_expose_exception_details(qtbot) -> None:
    flow = ArchiveWorkflow()
    qtbot.addWidget(flow)
    flow.set_archive_started()
    flow.set_archive_error("The archive stopped safely. Completed files remain available.")
    assert flow.current_step == 6
    assert flow.report_title.text() == "Archive stopped safely"


def test_continue_is_visibly_disabled_while_archive_is_running(qtbot) -> None:
    flow = ArchiveWorkflow()
    qtbot.addWidget(flow)
    flow.set_archive_started()

    assert flow.current_step == 4
    assert not flow.next_button.isEnabled()
    assert flow.next_button.property("primary") is True
