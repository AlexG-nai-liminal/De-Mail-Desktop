from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(22, 20, 22, 20)
        self.layout.setSpacing(12)


def page_heading(eyebrow: str, title: str, description: str) -> tuple[QWidget, QLabel]:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 8)
    layout.setSpacing(7)
    eyebrow_label = QLabel(eyebrow.upper())
    eyebrow_label.setObjectName("eyebrow")
    title_label = QLabel(title)
    title_label.setObjectName("pageTitle")
    description_label = QLabel(description)
    description_label.setObjectName("pageDescription")
    description_label.setWordWrap(True)
    description_label.setMaximumWidth(680)
    layout.addWidget(eyebrow_label)
    layout.addWidget(title_label)
    layout.addWidget(description_label)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    return container, title_label

