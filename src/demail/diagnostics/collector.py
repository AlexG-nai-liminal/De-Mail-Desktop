import platform
import secrets
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from demail import __version__

from .redaction import mask_account, redact
from .report import DiagnosticReport

_ID_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


class DiagnosticRepository(Protocol):
    def operations(self, limit: int = 100): ...


class DiagnosticCollector:
    def __init__(self, repository: DiagnosticRepository, application_data: Path) -> None:
        self.repository = repository
        self.application_data = application_data

    def collect(
        self,
        *,
        stage: str,
        account_email: str | None = None,
        what_happened: str = "",
        what_were_you_doing: str = "",
    ) -> DiagnosticReport:
        rows = self.repository.operations(limit=1)
        operation = rows[0] if rows else None
        account = account_email or (operation["account_email"] if operation else None)
        facts: tuple[tuple[str, str], ...] = ()
        destination_kind = "none"
        last_status = None
        if operation is not None:
            facts = (
                ("Status", str(operation["status"])),
                ("Selected", str(operation["selected_count"])),
                ("Exported", str(operation["exported_count"])),
                ("Verified", str(operation["verified_count"])),
                ("Failed", str(operation["failed_count"])),
                ("Archived bytes", str(operation["total_bytes"])),
            )
            destination_kind = describe_destination(Path(operation["destination_path"]))
            last_status = redact(operation["status_detail"]) or None
        return DiagnosticReport(
            report_id="".join(secrets.choice(_ID_ALPHABET) for _ in range(6)),
            created_at=datetime.now(UTC).isoformat(),
            app_version=__version__,
            windows_release=f"{platform.system()} {platform.release()} build {platform.version()}",
            python_version=platform.python_version(),
            architecture=platform.machine() or "unknown",
            stage=redact(stage) or "unknown",
            account=mask_account(account),
            scopes="Gmail read-only",
            destination_kind=destination_kind,
            free_space=self._free_space(),
            operation_facts=facts,
            last_status=last_status,
            what_happened=redact(what_happened),
            what_were_you_doing=redact(what_were_you_doing),
        )

    def _free_space(self) -> str | None:
        try:
            free = shutil.disk_usage(self.application_data).free
            return f"{free} bytes free on the application data drive"
        except OSError:
            return None


def describe_destination(path: Path) -> str:
    text = str(path)
    if text.startswith("\\\\"):
        return "network storage"
    try:
        import ctypes

        root = path.anchor
        drive_type = ctypes.windll.kernel32.GetDriveTypeW(root)
        return {
            2: "removable storage",
            3: "fixed storage",
            4: "network storage",
            5: "optical storage",
            6: "RAM disk",
        }.get(drive_type, "unknown storage")
    except (AttributeError, OSError):
        return "unknown storage"
