from pathlib import Path

import pytest

from demail.app import main, run_selftest

ROOT = Path(__file__).resolve().parents[2]


def test_release_build_is_fail_fast_and_checks_every_artifact() -> None:
    script = (ROOT / "tools" / "build_release.ps1").read_text(encoding="utf-8")

    assert "$ErrorActionPreference = 'Stop'" in script
    assert "tools\\check_version.py" in script
    assert "from tools.versioning import read_version" in script
    assert "The authoritative version is blank" in script
    assert "Refusing to clear an output directory outside dist" in script
    assert "Remove-Item -LiteralPath $payloadFull -Recurse -Force" in script
    assert "ruff check ." in script
    assert "-m pytest" in script
    assert ".VersionInfo.FileVersion" in script
    assert "--selftest" in script
    assert "--launchtest" in script
    assert "tools\\build_installer.py" in script
    assert "Get-FileHash" in script
    assert "SHA256SUMS.txt" in script


def test_installer_refuses_to_package_a_stale_standalone_build() -> None:
    script = (ROOT / "installer" / "de-mail-desktop.iss").read_text(encoding="utf-8")

    assert "GetVersionNumbersString(BuiltExePath)" in script
    assert "BuiltExeVersion != MyAppVersionQuad" in script
    assert "Stale standalone build" in script


def test_selftest_accepts_complete_packaged_resources() -> None:
    run_selftest()


def test_selftest_rejects_missing_packaged_resources(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="missing resource"):
        run_selftest(tmp_path)


def test_release_test_modes_are_mutually_exclusive(capsys) -> None:
    assert main(["--selftest", "--launchtest"]) == 2
    assert "only one" in capsys.readouterr().err


def test_version_mode_reports_runtime_version(capsys) -> None:
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == "0.2.0"
