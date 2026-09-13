import pytest

from demail.archive.layout import require_safe_archive_component


@pytest.mark.parametrize(
    "value",
    ["", ".", "..", "../outside", "..\\outside", "C:outside", "name.", "name ", "a\x00b"],
)
def test_unsafe_archive_components_are_rejected(value: str) -> None:
    with pytest.raises(ValueError, match="unsafe path"):
        require_safe_archive_component(value)


def test_archive_component_suffix_is_checked_case_insensitively() -> None:
    assert require_safe_archive_component("MESSAGE.EML", suffix=".eml") == "MESSAGE.EML"
    with pytest.raises(ValueError, match="unsafe path"):
        require_safe_archive_component("message.txt", suffix=".eml")
