import os
from collections.abc import Callable
from pathlib import Path


def open_folder(path: Path, opener: Callable[[str], object] | None = None) -> None:
    if not path.is_absolute() or not path.is_dir():
        raise OSError("Archive folder is unavailable.")
    launch = opener or os.startfile
    launch(str(path))
