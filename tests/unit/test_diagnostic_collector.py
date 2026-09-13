from pathlib import Path

from demail.diagnostics.collector import DiagnosticCollector


class Repository:
    def __init__(self, rows) -> None:
        self.rows = rows

    def operations(self, limit=100):
        assert limit == 1
        return self.rows


def test_collector_uses_shapes_not_personal_operation_content(tmp_path: Path) -> None:
    personal_folder = tmp_path / "Alex Personal Archive"
    row = {
        "account_email": "alex@gmail.com",
        "status": "PARTIAL",
        "selected_count": 9,
        "exported_count": 5,
        "verified_count": 5,
        "failed_count": 4,
        "total_bytes": 123,
        "destination_path": str(personal_folder),
        "status_detail": r"write failed at C:\Alex Personal Archive\private-subject.eml",
        "selection_description": "from confidential-sender@example.com",
    }
    report = DiagnosticCollector(Repository([row]), tmp_path).collect(
        stage="Report a problem",
        what_happened="Failed for alex@gmail.com",
        what_were_you_doing=r"Writing C:\Alex Personal Archive\mail",
    )
    rendered_values = repr(report)
    assert "alex@gmail.com" not in rendered_values
    assert "confidential-sender" not in rendered_values
    assert "Personal Archive" not in rendered_values
    assert report.account == "•••@gmail.com"
    assert ("Selected", "9") in report.operation_facts
    assert report.scopes == "Gmail read-only"


def test_collector_without_operation_or_disk_stats_still_builds(
    tmp_path: Path, monkeypatch
) -> None:
    def unavailable(_: Path) -> None:
        raise OSError

    monkeypatch.setattr("demail.diagnostics.collector.shutil.disk_usage", unavailable)
    report = DiagnosticCollector(Repository([]), tmp_path).collect(stage="Settings")
    assert report.account == "not connected"
    assert report.destination_kind == "none"
    assert report.operation_facts == ()
    assert report.free_space is None
    assert len(report.report_id) == 6
