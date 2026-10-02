"""Local support QR images supplied by the publisher."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

SUPPORT_CODES = (("PayPal", "paypal.png"), ("Cash App", "cash-app.png"), ("Venmo", "venmo.png"))


class SupportDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, *, asset_root: Path | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Support Continued Development")
        self.setModal(True)
        self.setStyleSheet("QDialog { background: #0B0B0B; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)
        description = QLabel("Support Continued Development")
        description.setStyleSheet("font-size: 20px; font-weight: 600;")
        description.setWordWrap(True)
        layout.addWidget(description)
        codes = QHBoxLayout()
        codes.setSpacing(18)
        root = asset_root or Path(__file__).resolve().parents[1] / "assets" / "support"
        self.code_labels: list[QLabel] = []
        for service, filename in SUPPORT_CODES:
            column = QVBoxLayout()
            title = QLabel(service)
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title.setStyleSheet("font-size: 16px; font-weight: 600;")
            image = QLabel()
            image.setFixedSize(220, 220)
            image.setAlignment(Qt.AlignmentFlag.AlignCenter)
            image.setWordWrap(True)
            image.setAccessibleName(f"{service} support QR code")
            pixmap = QPixmap(str(root / filename))
            if pixmap.isNull():
                image.setText(f"{service} QR code is unavailable.")
            else:
                image.setPixmap(pixmap.scaled(
                    image.size(), Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
            self.code_labels.append(image)
            column.addWidget(title)
            column.addWidget(image)
            codes.addLayout(column)
        layout.addLayout(codes)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        close.setDefault(True)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
