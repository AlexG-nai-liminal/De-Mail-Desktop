import importlib.util
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "build_installer.py"
SPEC = importlib.util.spec_from_file_location("build_installer", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
build_installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_installer)


def _complete_payload(path: Path) -> Path:
    (path / "PySide6" / "qt-plugins" / "platforms").mkdir(parents=True)
    (path / "main.exe").write_bytes(b"MZ executable")
    (path / "PySide6" / "qt-plugins" / "platforms" / "qwindows.dll").write_bytes(
        b"platform"
    )
    return path


def test_installer_contract_is_per_user_branded_and_preserves_user_data() -> None:
    script = (ROOT / "installer" / "de-mail-desktop.iss").read_text(encoding="utf-8")
    with (ROOT / "pyproject.toml").open("rb") as stream:
        version = tomllib.load(stream)["project"]["version"]

    assert f'#define MyAppVersion "{version}"' in script
    assert "PrivilegesRequired=lowest" in script
    assert "UsePreviousAppDir=yes" in script
    assert "DefaultDirName={localappdata}\\Programs\\{#MyAppName}" in script
    assert 'DestName: "{#MyAppExeName}"' in script
    assert "WizardStyle=modern" in script
    assert "[UninstallDelete]" not in script
    assert "client_secret" not in script.casefold()
    assert "credential" not in script.casefold()


def test_locate_iscc_prefers_an_explicit_existing_candidate(tmp_path: Path) -> None:
    compiler = tmp_path / "ISCC.exe"
    compiler.write_bytes(b"compiler")

    assert build_installer.locate_iscc([tmp_path / "missing.exe", compiler]) == compiler


def test_locate_iscc_rejects_missing_compiler(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(build_installer.shutil, "which", lambda _name: None)

    with pytest.raises(FileNotFoundError, match="Inno Setup 6"):
        build_installer.locate_iscc([tmp_path / "missing.exe"])


@pytest.mark.parametrize("state", ["missing", "empty"])
def test_validate_payload_rejects_missing_or_empty_directory(
    tmp_path: Path, state: str
) -> None:
    payload = tmp_path / "payload"
    if state == "empty":
        payload.mkdir()

    with pytest.raises((FileNotFoundError, ValueError)):
        build_installer.validate_payload(payload)


@pytest.mark.parametrize(
    "missing_relative",
    [Path("main.exe"), Path("PySide6/qt-plugins/platforms/qwindows.dll")],
)
def test_validate_payload_rejects_incomplete_runtime(
    tmp_path: Path, missing_relative: Path
) -> None:
    payload = _complete_payload(tmp_path / "payload")
    (payload / missing_relative).unlink()

    with pytest.raises(FileNotFoundError, match="incomplete"):
        build_installer.validate_payload(payload)


def test_validate_payload_accepts_complete_runtime(tmp_path: Path) -> None:
    payload = _complete_payload(tmp_path / "payload")

    files = build_installer.validate_payload(payload)

    assert {path.name for path in files} == {"main.exe", "qwindows.dll"}


def test_build_installer_invokes_compiler_and_returns_artifact(
    monkeypatch, tmp_path: Path
) -> None:
    payload = _complete_payload(tmp_path / "payload")
    script = tmp_path / "setup.iss"
    script.write_text("[Setup]", encoding="utf-8")
    compiler = tmp_path / "ISCC.exe"
    compiler.write_bytes(b"compiler")
    output = tmp_path / "out" / "setup.exe"
    calls = []

    def run(command, *, cwd, check):
        calls.append((command, cwd, check))
        output.write_bytes(b"MZ installer")

    monkeypatch.setattr(build_installer.subprocess, "run", run)

    result = build_installer.build_installer(
        compiler=compiler,
        script=script,
        payload_dir=payload,
        output_file=output,
    )

    assert result == output
    assert calls == [([str(compiler), "/Qp", str(script)], ROOT, True)]


def test_build_installer_propagates_compiler_failure(monkeypatch, tmp_path: Path) -> None:
    payload = _complete_payload(tmp_path / "payload")
    script = tmp_path / "setup.iss"
    script.write_text("[Setup]", encoding="utf-8")
    compiler = tmp_path / "ISCC.exe"
    compiler.write_bytes(b"compiler")

    def fail(command, *, cwd, check):
        raise subprocess.CalledProcessError(2, command)

    monkeypatch.setattr(build_installer.subprocess, "run", fail)

    with pytest.raises(subprocess.CalledProcessError):
        build_installer.build_installer(
            compiler=compiler,
            script=script,
            payload_dir=payload,
            output_file=tmp_path / "setup.exe",
        )


def test_build_installer_rejects_success_without_output(monkeypatch, tmp_path: Path) -> None:
    payload = _complete_payload(tmp_path / "payload")
    script = tmp_path / "setup.iss"
    script.write_text("[Setup]", encoding="utf-8")
    compiler = tmp_path / "ISCC.exe"
    compiler.write_bytes(b"compiler")
    monkeypatch.setattr(build_installer.subprocess, "run", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="did not create"):
        build_installer.build_installer(
            compiler=compiler,
            script=script,
            payload_dir=payload,
            output_file=tmp_path / "setup.exe",
        )


def test_update_installation_uses_silent_in_place_setup(monkeypatch, tmp_path: Path) -> None:
    installer = tmp_path / "setup.exe"
    installer.write_bytes(b"MZ installer")
    calls = []

    def run(command, *, cwd, check):
        calls.append((command, cwd, check))

    monkeypatch.setattr(build_installer.subprocess, "run", run)

    build_installer.update_installation(installer)

    assert calls == [
        (
            [
                str(installer),
                "/VERYSILENT",
                "/SUPPRESSMSGBOXES",
                "/NORESTART",
            ],
            ROOT,
            True,
        )
    ]


def test_update_installation_rejects_missing_or_empty_setup(tmp_path: Path) -> None:
    installer = tmp_path / "setup.exe"
    with pytest.raises(FileNotFoundError):
        build_installer.update_installation(installer)
    installer.touch()
    with pytest.raises(FileNotFoundError):
        build_installer.update_installation(installer)
