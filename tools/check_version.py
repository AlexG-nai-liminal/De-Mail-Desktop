"""Fail when generated release files do not match the authoritative version."""

from __future__ import annotations

from versioning import read_version, validate_generated_files


def main() -> int:
    stale = validate_generated_files()
    if stale:
        joined = ", ".join(stale)
        raise SystemExit(f"Generated version files are stale: {joined}")
    print(f"Release versions agree: {read_version()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
