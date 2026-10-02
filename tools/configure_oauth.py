"""Validate and install a Desktop OAuth identity into ignored build assets."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from demail.auth.client_config import load_desktop_client
from demail.auth.client_source import bundled_client_path


def configure_client(source: Path, destination: Path | None = None) -> Path:
    destination = destination or bundled_client_path()
    payload = source.read_bytes()
    # Validate the exact bytes that will be packaged before replacing a working identity.
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        candidate = Path(directory) / "client.json"
        candidate.write_bytes(payload)
        load_desktop_client(candidate)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".json.partial")
    try:
        temporary.write_bytes(payload)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("client", type=Path)
    options = parser.parse_args()
    configure_client(options.client)
    print("Production Desktop OAuth identity configured for packaging.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
