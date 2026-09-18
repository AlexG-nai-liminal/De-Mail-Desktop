"""Advance the de-Mail Desktop version and release history."""

from __future__ import annotations

import argparse

from versioning import bump


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="patch, minor, major, or an exact newer version")
    parser.add_argument(
        "--note",
        action="append",
        default=[],
        help="release-history bullet; repeat for more than one note",
    )
    options = parser.parse_args(argv)
    version = bump(options.version, options.note)
    print(f"Advanced de-Mail Desktop to {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
