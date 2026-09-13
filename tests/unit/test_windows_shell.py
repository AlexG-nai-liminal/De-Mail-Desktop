from pathlib import Path

import pytest

from demail.windows.shell import open_folder


def test_open_folder_uses_validated_absolute_directory(tmp_path: Path) -> None:
    opened = []
    open_folder(tmp_path, opened.append)
    assert opened == [str(tmp_path)]


@pytest.mark.parametrize("value", [Path("relative"), Path("C:/missing-folder")])
def test_open_folder_rejects_unsafe_or_missing_path(value: Path) -> None:
    with pytest.raises(OSError, match="unavailable"):
        open_folder(value, lambda _: None)
