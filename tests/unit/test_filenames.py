import pytest

from demail.archive.filenames import eml_filename, slug


def test_name_carries_utc_date_subject_and_gmail_id() -> None:
    assert eml_filename(1_673_787_600_000, "Your receipt", "18c9a1b2c3d4e5f6") == (
        "2023-01-15_1300_Your-receipt_18c9a1b2c3d4e5f6.eml"
    )


def test_invalid_windows_characters_and_path_traversal_do_not_survive() -> None:
    name = eml_filename(None, '../../etc/passwd & rm -rf * | <CON>?:"', "abc123")
    assert not any(character in name for character in '<>:"/\\|?*')
    assert ".." not in name
    assert name.endswith("_abc123.eml")


@pytest.mark.parametrize(
    "device_name",
    ["CON", "prn", "AUX", "nul", "COM1", "com9", "LPT1", "lpt9"],
)
def test_windows_device_names_are_guarded_case_insensitively(device_name: str) -> None:
    assert eml_filename(None, None, device_name).startswith("_")


def test_unicode_only_subject_falls_back_to_identifier() -> None:
    assert eml_filename(1_673_787_600_000, "日本語のみ", "id9") == (
        "2023-01-15_1300_id9.eml"
    )


def test_long_subject_is_bounded_without_losing_id() -> None:
    name = eml_filename(1_673_787_600_000, "x" * 500, "18c9a1b2c3d4e5f6")
    assert len(name) < 140
    assert name.endswith("_18c9a1b2c3d4e5f6.eml")


def test_retry_is_deterministic_and_ids_prevent_case_insensitive_collision() -> None:
    first = eml_filename(1, "Invoice", "aaa")
    assert eml_filename(1, "Invoice", "aaa") == first
    assert first.casefold() != eml_filename(1, "Invoice", "bbb").casefold()


def test_empty_metadata_still_produces_name() -> None:
    assert eml_filename(None, None, "!!!") == "message.eml"


@pytest.mark.parametrize(
    ("raw", "maximum", "expected"),
    [("  a    b  ", 40, "a-b"), ("---hello---", 40, "hello"), ("!!!", 40, ""), ("a", 0, "")],
)
def test_slug_boundaries(raw: str, maximum: int, expected: str) -> None:
    assert slug(raw, maximum) == expected


def test_filename_has_no_trailing_space_or_period_before_extension() -> None:
    stem = eml_filename(None, "hello... ", "id").removesuffix(".eml")
    assert not stem.endswith((" ", "."))

