from demail.diagnostics.report import DiagnosticReport, render_report


def report(**changes) -> DiagnosticReport:
    values = {
        "report_id": "a3f2jk",
        "created_at": "2026-09-12T12:00:00+00:00",
        "app_version": "0.1.0",
        "windows_release": "Windows 11 build 26100",
        "python_version": "3.12.8",
        "architecture": "AMD64",
        "stage": "Archive progress",
        "account": "•••@gmail.com",
        "scopes": "Gmail read-only",
        "destination_kind": "fixed storage",
        "operation_facts": (("Status", "PARTIAL"), ("Selected", "9056")),
        "last_status": "HTTP 429",
        "what_happened": "The export stopped.",
        "what_were_you_doing": "Archiving a date range.",
    }
    values.update(changes)
    return DiagnosticReport(**values)


def test_report_contains_useful_facts_and_privacy_statement() -> None:
    text = render_report(report())
    for expected in (
        "0.1.0",
        "Windows 11",
        "3.12.8",
        "Archive progress",
        "HTTP 429",
        "9056",
        "•••@gmail.com",
        "Nothing is sent automatically",
    ):
        assert expected in text


def test_blank_descriptions_are_explicit_and_operation_is_optional() -> None:
    text = render_report(
        report(
            operation_facts=(),
            last_status=None,
            what_happened="",
            what_were_you_doing="",
        )
    )
    assert text.count("(not described)") == 2
    assert "\nOperation\n" not in text
