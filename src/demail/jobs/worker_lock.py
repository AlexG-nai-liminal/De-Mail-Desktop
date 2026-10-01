"""Process-owned archive locks, released by the OS even after a crash."""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class WorkerLockedError(RuntimeError):
    pass


@contextmanager
def archive_worker_lock(database_path: Path, operation_id: int) -> Iterator[None]:
    if isinstance(operation_id, bool) or not isinstance(operation_id, int) or operation_id <= 0:
        raise ValueError("Archive operation ID must be a positive integer.")
    path = database_path.with_name(f"{database_path.name}.archive-{operation_id}.lock")
    with path.open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise WorkerLockedError("This archive operation is already running.") from error
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise WorkerLockedError("This archive operation is already running.") from error
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
