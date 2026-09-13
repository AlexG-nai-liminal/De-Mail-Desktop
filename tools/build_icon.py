"""Render the scalable application mark into a multi-size Windows ICO file."""

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "demail" / "assets" / "app-icon.svg"
OUTPUT = ROOT / "src" / "demail" / "assets" / "de-mail.ico"
PNG_OUTPUT = ROOT / "src" / "demail" / "assets" / "de-mail.png"
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def render_png(renderer: QSvgRenderer, size: int) -> bytes:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    data = QByteArray()
    buffer = QBuffer(data)
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly) or not image.save(buffer, "PNG"):
        raise RuntimeError(f"Could not render the {size}-pixel icon frame.")
    return bytes(data)


def build_icon() -> None:
    _application = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    renderer = QSvgRenderer(str(SOURCE))
    if not renderer.isValid():
        raise ValueError("The application icon SVG is invalid.")
    frames = [(size, render_png(renderer, size)) for size in SIZES]
    PNG_OUTPUT.write_bytes(frames[-1][1])
    offset = 6 + 16 * len(frames)
    header = struct.pack("<HHH", 0, 1, len(frames))
    entries = bytearray()
    payload = bytearray()
    for size, png in frames:
        dimension = 0 if size == 256 else size
        entries.extend(
            struct.pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(png), offset)
        )
        payload.extend(png)
        offset += len(png)
    OUTPUT.write_bytes(header + entries + payload)


if __name__ == "__main__":
    build_icon()
