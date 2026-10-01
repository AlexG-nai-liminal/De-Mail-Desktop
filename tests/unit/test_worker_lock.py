import os
import subprocess
import sys
from pathlib import Path

import pytest

from demail.jobs.worker_lock import WorkerLockedError, archive_worker_lock


@pytest.mark.parametrize("operation_id", [0, -1, True, "../escape", None, 1.5])
def test_invalid_operation_id_creates_no_lock(tmp_path: Path, operation_id) -> None:
    with (
        pytest.raises(ValueError, match="positive integer"),
        archive_worker_lock(tmp_path / "state.db", operation_id),
    ):
        pytest.fail("Invalid operation acquired a lock")
    assert list(tmp_path.iterdir()) == []


def test_lock_excludes_same_operation_but_allows_another(tmp_path: Path) -> None:
    database = tmp_path / "state.db"
    with archive_worker_lock(database, 1):
        with pytest.raises(WorkerLockedError), archive_worker_lock(database, 1):
            pytest.fail("A second worker entered")
        with archive_worker_lock(database, 2):
            pass
    with archive_worker_lock(database, 1):
        pass


def test_lock_releases_after_worker_failure(tmp_path: Path) -> None:
    database = tmp_path / "state.db"
    with pytest.raises(RuntimeError, match="interrupted"), archive_worker_lock(database, 1):
        raise RuntimeError("interrupted")
    with archive_worker_lock(database, 1):
        pass


def test_unavailable_lock_directory_fails_before_entering(tmp_path: Path) -> None:
    with pytest.raises(OSError), archive_worker_lock(tmp_path / "missing" / "state.db", 1):
        pytest.fail("Worker entered without a lock")


def test_process_crash_releases_lock(tmp_path: Path) -> None:
    database = tmp_path / "state.db"
    script = (
        "import sys, time; from pathlib import Path; "
        "from demail.jobs.worker_lock import archive_worker_lock; "
        "lock = archive_worker_lock(Path(sys.argv[1]), 1); lock.__enter__(); "
        "print('locked', flush=True); time.sleep(60)"
    )
    environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"))
    child = subprocess.Popen(
        [sys.executable, "-c", script, str(database)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )
    try:
        assert child.stdout is not None
        assert child.stdout.readline().strip() == "locked"
        with pytest.raises(WorkerLockedError), archive_worker_lock(database, 1):
            pytest.fail("A second process entered")
    finally:
        child.kill()
        child.communicate(timeout=10)
    with archive_worker_lock(database, 1):
        pass
