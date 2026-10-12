import errno
from pathlib import Path
from types import SimpleNamespace

import pytest

from demail.archive.destination import MINIMUM_FREE_BYTES, check_destination
from demail.jobs.failures import explain_failure


def test_writable_destination_probe_is_removed(tmp_path):
    folder = tmp_path / "archive"
    assert check_destination(folder) >= MINIMUM_FREE_BYTES
    assert list(folder.iterdir()) == []


def test_relative_destination_is_rejected():
    with pytest.raises(ValueError, match="absolute"):
        check_destination(Path("relative"))


@pytest.mark.parametrize("free", [0, MINIMUM_FREE_BYTES - 1, MINIMUM_FREE_BYTES])
def test_space_boundary(tmp_path, monkeypatch, free):
    monkeypatch.setattr("demail.archive.destination.shutil.disk_usage",
                        lambda _: SimpleNamespace(free=free))
    if free < MINIMUM_FREE_BYTES:
        with pytest.raises(OSError) as caught:
            check_destination(tmp_path)
        assert caught.value.errno == errno.ENOSPC
    else:
        assert check_destination(tmp_path) == free
    assert list(tmp_path.iterdir()) == []


def test_probe_write_failure_cleans_up_and_can_recover(tmp_path, monkeypatch):
    import demail.archive.destination as module
    actual = module.os.fsync
    def fail(_):
        raise PermissionError("private path")
    monkeypatch.setattr(module.os, "fsync", fail)
    with pytest.raises(PermissionError):
        check_destination(tmp_path)
    assert list(tmp_path.iterdir()) == []
    monkeypatch.setattr(module.os, "fsync", actual)
    assert check_destination(tmp_path) >= MINIMUM_FREE_BYTES


@pytest.mark.parametrize("error,phrase", [
    (OSError(errno.ENOSPC, "private secret"), "drive is full"),
    (PermissionError("private secret"), "not writable"),
    (OSError("private secret"), "destination is unavailable"),
    (RuntimeError("private secret"), "stopped safely"),
])
def test_failure_explanations_are_actionable_and_redacted(error, phrase):
    explanation = explain_failure(error)
    assert phrase in explanation
    assert "private" not in explanation and "secret" not in explanation
