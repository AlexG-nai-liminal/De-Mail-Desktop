"""Build the Windows setup executable from the verified standalone payload."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path

try:
    from tools.versioning import read_version, validate_generated_files
except ModuleNotFoundError:  # Direct execution adds tools, rather than the repository, to sys.path.
    from versioning import read_version, validate_generated_files

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_DIR = ROOT / "dist" / "de-Mail Desktop.dist"
INSTALLER_SCRIPT = ROOT / "installer" / "de-mail-desktop.iss"


def output_file(root: Path = ROOT) -> Path:
    """Return the installer path for the authoritative application version."""
    return root / "dist" / "installer" / f"de-Mail-Desktop-Setup-{read_version(root)}.exe"


def default_iscc_candidates() -> tuple[Path, ...]:
    """Return deterministic Inno Setup compiler locations for Windows."""
    locations: list[Path] = []
    for variable in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(variable)
        if base:
            locations.append(Path(base) / "Inno Setup 6" / "ISCC.exe")
    return tuple(locations)


def locate_iscc(candidates: Iterable[Path] | None = None) -> Path:
    """Find the Inno Setup compiler or raise a useful error."""
    for candidate in candidates if candidates is not None else default_iscc_candidates():
        if candidate.is_file():
            return candidate

    executable = shutil.which("ISCC.exe") or shutil.which("iscc")
    if executable:
        return Path(executable)
    raise FileNotFoundError("Inno Setup 6 compiler was not found")


def validate_payload(payload_dir: Path = PAYLOAD_DIR) -> tuple[Path, ...]:
    """Reject missing or incomplete standalone payloads before compilation."""
    if not payload_dir.is_dir():
        raise FileNotFoundError(f"Standalone payload directory not found: {payload_dir}")

    files = tuple(sorted(path for path in payload_dir.rglob("*") if path.is_file()))
    if not files:
        raise ValueError(f"Standalone payload directory is empty: {payload_dir}")

    required = (
        payload_dir / "main.exe",
        payload_dir / "PySide6" / "qt-plugins" / "platforms" / "qwindows.dll",
    )
    missing = [path for path in required if not path.is_file()]
    if missing:
        names = ", ".join(str(path.relative_to(payload_dir)) for path in missing)
        raise FileNotFoundError(f"Standalone payload is incomplete; missing: {names}")
    return files


def build_installer(
    *,
    compiler: Path | None = None,
    script: Path = INSTALLER_SCRIPT,
    payload_dir: Path = PAYLOAD_DIR,
    output_file: Path | None = None,
) -> Path:
    """Compile the installer and verify that the expected artifact exists."""
    stale = validate_generated_files(ROOT)
    if stale:
        raise ValueError("Generated version files are stale: " + ", ".join(stale))
    validate_payload(payload_dir)
    if not script.is_file():
        raise FileNotFoundError(f"Installer script not found: {script}")

    iscc = compiler or locate_iscc()
    expected_output = output_file or globals()["output_file"]()
    expected_output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(iscc), "/Qp", str(script)], cwd=ROOT, check=True)
    if not expected_output.is_file() or expected_output.stat().st_size == 0:
        raise RuntimeError(f"Installer compiler did not create: {expected_output}")
    return expected_output


def update_installation(installer: Path | None = None) -> None:
    """Install or upgrade the permanent per-user installation in place."""
    installer = installer or output_file()
    if not installer.is_file() or installer.stat().st_size == 0:
        raise FileNotFoundError(f"Setup executable not found: {installer}")
    subprocess.run(
        [
            str(installer),
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
        ],
        cwd=ROOT,
        check=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--install",
        action="store_true",
        help="install or upgrade the permanent per-user installation after building",
    )
    options = parser.parse_args(argv)
    output = build_installer()
    print(output)
    if options.install:
        update_installation(output)
        print("Permanent installation updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
