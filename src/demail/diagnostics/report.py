from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DiagnosticReport:
    report_id: str
    created_at: str
    app_version: str
    windows_release: str
    python_version: str
    architecture: str
    stage: str
    account: str
    scopes: str
    destination_kind: str
    free_space: str | None = None
    operation_facts: tuple[tuple[str, str], ...] = ()
    last_status: str | None = None
    what_happened: str = ""
    what_were_you_doing: str = ""


def render_report(report: DiagnosticReport) -> str:
    lines = [
        "de-Mail Desktop problem report",
        "==============================",
        "",
        f"Report ID     {report.report_id}",
        f"Created       {report.created_at}",
        f"App           de-Mail Desktop {report.app_version}",
        f"Windows       {report.windows_release}",
        f"Python        {report.python_version} ({report.architecture})",
        f"Screen        {report.stage}",
        f"Account       {report.account}",
        f"Permissions   {report.scopes}",
        f"Destination   {report.destination_kind}",
    ]
    if report.free_space:
        lines.append(f"Free space    {report.free_space}")
    if report.last_status:
        lines.append(f"Last status   {report.last_status}")
    if report.operation_facts:
        lines.extend(("", "Operation", "---------"))
        width = max(len(label) for label, _ in report.operation_facts)
        lines.extend(f"{label.ljust(width)}  {value}" for label, value in report.operation_facts)
    lines.extend(
        (
            "",
            "What happened",
            "-------------",
            report.what_happened or "(not described)",
            "",
            "What you were trying to do",
            "---------------------------",
            report.what_were_you_doing or "(not described)",
            "",
            "Privacy check",
            "-------------",
            "No message content, message metadata, folder names, or credentials were collected. ",
            "Text entered above was automatically redacted. Nothing is sent automatically.",
        )
    )
    return "\n".join(lines) + "\n"
