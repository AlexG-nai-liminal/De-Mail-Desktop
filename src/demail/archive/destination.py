"""Probe archive storage without leaving probe files behind."""

import errno
import os
import shutil
import tempfile
from pathlib import Path

MINIMUM_FREE_BYTES = 16 * 1024 * 1024


def check_destination(destination: Path) -> int:
    if not destination.is_absolute():
        raise ValueError("Choose an absolute archive destination.")
    destination.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(destination).free
    if free < MINIMUM_FREE_BYTES:
        raise OSError(errno.ENOSPC, "Not enough free space to start the archive.")
    # Checking permissions alone cannot detect a read-only or disconnected drive.
    descriptor, name = tempfile.mkstemp(prefix=".de-mail-probe-", dir=destination)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(b"de-Mail storage check")
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        Path(name).unlink(missing_ok=True)
    return free
