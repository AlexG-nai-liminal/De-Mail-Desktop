from pathlib import Path

import pytest

from demail.diagnostics.report import DiagnosticReport
from demail.ui.diagnostics import DiagnosticController, ProblemReportPage, save_diagnostic_report


class ImmediatePool:
    def start(self, task) -> None:
        task.run()


class Collector:
    def collect(self, **kwargs) -> DiagnosticReport:
        assert kwargs["account_email"] == "person@gmail.com"
        return DiagnosticReport(
            "abc234",
            "2026-09-12T12:00:00+00:00",
            "0.1.0",
            "Windows 11",
            "3.12",
            "AMD64",
            kwargs["stage"],
            "•••@gmail.com",
            "Gmail read-only",
            "none",
            what_happened=kwargs["what_happened"],
            what_were_you_doing=kwargs["what_were_you_doing"],
        )


def test_problem_report_is_inspectable_before_copy_or_save(qtbot) -> None:
    page = ProblemReportPage()
    qtbot.addWidget(page)
    assert not page.copy_button.isEnabled()
    assert not page.send_button.isEnabled()
    page.what_happened.setPlainText("It stopped")
    with qtbot.waitSignal(page.build_requested) as request:
        page.build_button.click()
    assert request.args == ["It stopped", ""]
    page.set_report("complete report")
    assert page.preview.toPlainText() == "complete report"
    assert page.copy_button.isEnabled()
    assert page.send_button.isEnabled()
    page.copy_report()
    assert "copied" in page.delivery_status.text().lower()


def test_problem_report_opens_only_the_reviewed_preview_for_email(qtbot) -> None:
    page = ProblemReportPage()
    qtbot.addWidget(page)
    page.set_report("reviewed report")
    with qtbot.waitSignal(page.send_requested) as request:
        page.send_button.click()
    assert request.args == ["reviewed report"]
    assert page.send_button.text() == "Send report to"
    assert "alex@liminalmemory.com" in page.send_button.toolTip()


def test_problem_report_email_status_handles_success_and_recovery(qtbot) -> None:
    page = ProblemReportPage()
    qtbot.addWidget(page)
    page.set_email_opened("alex@liminalmemory.com")
    assert "review it before sending" in page.delivery_status.text().lower()
    page.set_delivery_error("Email unavailable. Copy the report instead.")
    assert "copy the report" in page.delivery_status.text().lower()


def test_diagnostic_controller_builds_and_redacts_failures(qtbot) -> None:
    controller = DiagnosticController(Collector, lambda: "person@gmail.com", ImmediatePool())
    with qtbot.waitSignal(controller.built) as built:
        controller.build("It stopped", "Archiving")
    assert "It stopped" in built.args[0]

    class BrokenCollector:
        def collect(self, **kwargs):
            raise RuntimeError("person@gmail.com secret-token")

    broken = DiagnosticController(BrokenCollector, thread_pool=ImmediatePool())
    with qtbot.waitSignal(broken.failed) as failed:
        broken.build("", "")
    assert "person@gmail.com" not in failed.args[0]


def test_report_save_is_atomic_and_rejects_invalid_input(tmp_path: Path) -> None:
    target = tmp_path / "report.txt"
    save_diagnostic_report(target, "safe report")
    assert target.read_text(encoding="utf-8") == "safe report"
    assert not (tmp_path / "report.txt.partial").exists()
    with pytest.raises(ValueError, match="blank"):
        save_diagnostic_report(target, "")
    with pytest.raises(OSError, match="unavailable"):
        save_diagnostic_report(Path("relative.txt"), "report")


def test_report_save_failure_preserves_existing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "report.txt"
    target.write_text("previous report", encoding="utf-8")

    def fail_write(self, data: bytes) -> int:
        raise OSError("simulated disk failure in a private folder")

    monkeypatch.setattr("demail.ui.diagnostics.AtomicArchiveFile.write", fail_write)
    with pytest.raises(OSError):
        save_diagnostic_report(target, "new report")
    assert target.read_text(encoding="utf-8") == "previous report"
    assert not (tmp_path / "report.txt.partial").exists()
