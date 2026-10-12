"""Atomic user-requested export of the human-readable archive report."""

import os
import tempfile
from pathlib import Path


def save_report(path: Path, text: str) -> None:
    if not path.is_absolute() or not text.strip():
        raise ValueError("Choose an absolute report path and a nonempty report.")
    descriptor, name = tempfile.mkstemp(prefix=".de-mail-report-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
