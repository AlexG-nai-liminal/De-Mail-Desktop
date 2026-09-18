from datetime import date
from pathlib import Path

import pytest

from tools.versioning import (
    Version,
    add_changelog_entry,
    bump,
    next_version,
    parse_version,
    read_version,
    render_deploy_spec,
    validate_generated_files,
    write_generated_files,
)


def _release_tree(root: Path, version: str = "1.2.3") -> Path:
    package = root / "src" / "demail"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        f'"""Package."""\n\n__version__ = "{version}"\n', encoding="utf-8"
    )
    (root / "installer").mkdir()
    (root / "pysidedeploy.spec").write_text(
        "extra_args = --file-version=1.2.3.0 --product-version=1.2.3.0\n",
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        "# Version history\n\nIntro.\n\n## 1.2.3 - 2026-01-01\n\n- Existing.\n",
        encoding="utf-8",
    )
    write_generated_files(root)
    return root


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0.0.0", Version(0, 0, 0)),
        ("1.2.3", Version(1, 2, 3)),
        ("2147483647.0.9", Version(2147483647, 0, 9)),
    ],
)
def test_parse_version_accepts_strict_three_part_versions(
    value: str, expected: Version
) -> None:
    assert parse_version(value) == expected


@pytest.mark.parametrize(
    "value",
    ["", "1", "1.2", "1.2.3.4", "v1.2.3", "1.2.3-beta", "01.2.3", "1.-2.3"],
)
def test_parse_version_rejects_malformed_input(value: str) -> None:
    with pytest.raises(ValueError, match="Invalid version"):
        parse_version(value)


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        ("patch", Version(1, 2, 4)),
        ("minor", Version(1, 3, 0)),
        ("major", Version(2, 0, 0)),
        ("3.4.5", Version(3, 4, 5)),
    ],
)
def test_next_version_supports_release_levels_and_exact_versions(
    requested: str, expected: Version
) -> None:
    assert next_version(Version(1, 2, 3), requested) == expected


@pytest.mark.parametrize("requested", ["1.2.3", "1.2.2", "0.99.99"])
def test_next_version_rejects_equal_or_backwards_versions(requested: str) -> None:
    with pytest.raises(ValueError, match="must be newer"):
        next_version(Version(1, 2, 3), requested)


def test_render_deploy_spec_requires_both_windows_version_arguments() -> None:
    with pytest.raises(ValueError, match="product-version"):
        render_deploy_spec("extra_args = --file-version=1.2.3.0", Version(2, 0, 0))


def test_add_changelog_entry_rejects_duplicate_version() -> None:
    source = "# Version history\n\n## 2.0.0 - 2026-01-01\n\n- Existing.\n"
    with pytest.raises(ValueError, match="already contains"):
        add_changelog_entry(source, Version(2, 0, 0), ["Duplicate."])


def test_add_changelog_entry_requires_existing_release_history() -> None:
    with pytest.raises(ValueError, match="no existing release"):
        add_changelog_entry("# Version history\n", Version(2, 0, 0), [])


def test_bump_updates_authority_history_and_generated_files(tmp_path: Path) -> None:
    root = _release_tree(tmp_path)

    result = bump(
        "minor",
        ["Added safe update checks.", "Improved setup builds."],
        root=root,
        released=date(2026, 9, 17),
    )

    assert result == Version(1, 3, 0)
    assert read_version(root) == Version(1, 3, 0)
    history = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    assert history.index("## 1.3.0") < history.index("## 1.2.3")
    assert "- Added safe update checks." in history
    assert '#define MyAppVersion "1.3.0"' in (
        root / "installer" / "version.iss"
    ).read_text(encoding="utf-8")
    assert "--file-version=1.3.0.0" in (root / "pysidedeploy.spec").read_text(
        encoding="utf-8"
    )
    assert validate_generated_files(root) == []


def test_validate_generated_files_reports_stale_or_missing_surfaces(tmp_path: Path) -> None:
    root = _release_tree(tmp_path)
    (root / "installer" / "version.iss").write_text("stale\n", encoding="utf-8")
    (root / "pysidedeploy.spec").write_text(
        "extra_args = --file-version=0.0.0.0 --product-version=0.0.0.0\n",
        encoding="utf-8",
    )

    assert validate_generated_files(root) == [
        "installer\\version.iss" if "\\" in str(Path("a\\b")) else "installer/version.iss",
        "pysidedeploy.spec",
    ]


def test_read_version_rejects_missing_authority(tmp_path: Path) -> None:
    package = tmp_path / "src" / "demail"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("# missing\n", encoding="utf-8")

    with pytest.raises(ValueError, match="No __version__"):
        read_version(tmp_path)
