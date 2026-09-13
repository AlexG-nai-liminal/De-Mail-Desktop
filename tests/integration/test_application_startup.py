import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from demail.persistence.database import LATEST_SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[2]


def test_application_boots_offscreen_and_initializes_isolated_state(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "LOCALAPPDATA": str(tmp_path),
            "PYTHONPATH": str(ROOT / "src"),
            "QT_QPA_PLATFORM": "offscreen",
        }
    )
    script = (
        "from PySide6.QtWidgets import QApplication; "
        "QApplication.exec = lambda self: 0; "
        "from demail.app import main; "
        "raise SystemExit(main())"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    database = tmp_path / "de-Mail Desktop" / "de-mail.db"
    assert database.is_file()
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == (
            LATEST_SCHEMA_VERSION
        )


def test_application_startup_fails_safely_without_windows_data_folder(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONPATH": str(ROOT / "src"),
            "QT_QPA_PLATFORM": "offscreen",
        }
    )
    environment.pop("LOCALAPPDATA", None)
    script = (
        "from PySide6.QtWidgets import QApplication; "
        "QApplication.exec = lambda self: 0; "
        "from demail.app import main; main()"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode != 0
    assert "local application data folder is unavailable" in result.stderr.lower()
    assert not (tmp_path / "de-Mail Desktop").exists()
