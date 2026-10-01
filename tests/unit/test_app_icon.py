import re
import struct
from pathlib import Path

from PySide6.QtGui import QIcon

ROOT = Path(__file__).resolve().parents[2]
ICON = ROOT / "src" / "demail" / "assets" / "de-mail.ico"


def test_windows_icon_contains_all_required_pixel_sizes(qapp) -> None:
    payload = ICON.read_bytes()
    reserved, image_type, count = struct.unpack_from("<HHH", payload)
    assert (reserved, image_type, count) == (0, 1, 9)
    sizes = set()
    for index in range(count):
        width, height = struct.unpack_from("<BB", payload, 6 + index * 16)
        sizes.add((256 if width == 0 else width, 256 if height == 0 else height))
    assert sizes == {(size, size) for size in (16, 20, 24, 32, 40, 48, 64, 128, 256)}
    assert not QIcon(str(ICON)).isNull()


def test_application_icon_palette_is_black_and_white() -> None:
    svg = (ICON.with_name("app-icon.svg")).read_text(encoding="utf-8")
    colors = {value.upper() for value in re.findall(r"#[0-9A-Fa-f]{6}", svg)}
    assert colors == {"#050505", "#FFFFFF"}
    assert 'stroke-linecap="round"' in svg
    assert svg.count("<path") == 3
