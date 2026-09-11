import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ApplicationPaths:
    data: Path
    database: Path
    authorization: Path


def application_paths(environment: dict[str, str] | None = None) -> ApplicationPaths:
    values = environment if environment is not None else os.environ
    local_app_data = values.get("LOCALAPPDATA")
    if not local_app_data:
        raise OSError("Windows local application data folder is unavailable.")
    data = Path(local_app_data) / "de-Mail Desktop"
    return ApplicationPaths(
        data=data,
        database=data / "de-mail.db",
        authorization=data / "authorization.bin",
    )

