from pathlib import Path

import pytest

from demail.archive.report import save_report
from demail.ui.archive import ArchiveRunResult


def test_report_export_is_complete_unicode_and_replaces_existing(tmp_path):
    target = tmp_path / "report.txt"
    target.write_text("old")
    save_report(target, "Verified: 2\nUnresolved: café\n")
    assert target.read_text(encoding="utf-8") == "Verified: 2\nUnresolved: café\n"
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize("text", ["", " ", "\n"])
def test_empty_report_is_rejected_without_replacing_existing(tmp_path, text):
    target = tmp_path / "report.txt"
    target.write_text("old")
    with pytest.raises(ValueError):
        save_report(target, text)
    assert target.read_text() == "old"


def test_relative_report_destination_is_rejected():
    with pytest.raises(ValueError):
        save_report(Path("report.txt"), "result")


def test_report_publication_failure_preserves_old_file_and_can_retry(tmp_path, monkeypatch):
    target = tmp_path / "report.txt"
    target.write_text("old")
    with monkeypatch.context() as patch:
        def fail(*_):
            raise PermissionError("busy")
        patch.setattr(Path, "replace", fail)
        with pytest.raises(PermissionError):
            save_report(target, "new")
    assert target.read_text() == "old"
    assert list(tmp_path.iterdir()) == [target]
    save_report(target, "new")
    assert target.read_text() == "new"


@pytest.mark.parametrize("selected,exported,verified,failed", [
    (-1, 0, 0, 0), (1, 2, 1, 0), (2, 1, 2, 0), (2, 2, 1, 0), (2, 2, 2, 1)
])
def test_invalid_verified_result_cannot_claim_success(selected, exported, verified, failed):
    with pytest.raises(ValueError):
        ArchiveRunResult(1, "VERIFIED", selected, exported, verified, failed, 0, Path("C:/"))
