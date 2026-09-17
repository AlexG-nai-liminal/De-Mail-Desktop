"""Compact OAuth help and a monochrome, keyboard-friendly tutorial gallery."""

from dataclasses import dataclass

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSequentialAnimationGroup,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .components import Card, page_heading
from .theme import BLACK, BORDER, CARD, MUTED, WHITE


@dataclass(frozen=True, slots=True)
class TutorialSlide:
    title: str
    description: str
    scene: str


TUTORIAL_SLIDES = (
    TutorialSlide(
        "Download the desktop client file",
        "In Google Cloud, open APIs and Services, then Credentials. Create a Desktop app "
        "OAuth client and download its JSON file.",
        "download",
    ),
    TutorialSlide(
        "Choose the file in de-Mail",
        "Return to Settings, choose the downloaded JSON file, and keep it in a private folder.",
        "choose",
    ),
    TutorialSlide(
        "Approve read-only access",
        "Your browser signs you in. Google validates the desktop client and the local callback "
        "before granting Gmail read-only access.",
        "authorize",
    ),
    TutorialSlide(
        "Archive and verify",
        "Choose mail, review the exact count, choose a destination, and let de-Mail verify every "
        "saved message.",
        "archive",
    ),
)


class TutorialIllustration(QWidget):
    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = TUTORIAL_SLIDES[0].scene
        self.setMinimumHeight(190)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName("Tutorial illustration. Click for the next scene.")

    def set_scene(self, scene: str) -> None:
        if scene not in {slide.scene for slide in TUTORIAL_SLIDES}:
            raise ValueError("Unknown tutorial scene")
        self._scene = scene
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.setBrush(QColor(BLACK))
        painter.setPen(QPen(QColor(BORDER), 1.5))
        painter.drawRoundedRect(bounds, 12, 12)
        painter.translate(bounds.left(), bounds.top())
        width, height = bounds.width(), bounds.height()
        painter.setPen(QPen(QColor(WHITE), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        if self._scene == "download":
            self._draw_cloud(painter, width, height)
        elif self._scene == "choose":
            self._draw_file_picker(painter, width, height)
        elif self._scene == "authorize":
            self._draw_authorization(painter, width, height)
        else:
            self._draw_archive(painter, width, height)

    @staticmethod
    def _draw_cloud(painter: QPainter, width: float, height: float) -> None:
        center = QPointF(width * 0.42, height * 0.46)
        painter.drawEllipse(QRectF(center.x() - 54, center.y() - 22, 54, 44))
        painter.drawEllipse(QRectF(center.x() - 16, center.y() - 44, 70, 66))
        painter.drawLine(center.x() - 52, center.y() + 22, center.x() + 52, center.y() + 22)
        x = width * 0.70
        painter.drawRoundedRect(QRectF(x - 28, height * 0.30, 56, 76), 5, 5)
        painter.drawLine(width * 0.52, height * 0.50, x - 38, height * 0.50)
        painter.drawLine(x - 46, height * 0.44, x - 38, height * 0.50)
        painter.drawLine(x - 46, height * 0.56, x - 38, height * 0.50)
        painter.setPen(QPen(QColor(MUTED), 2))
        painter.drawLine(x - 15, height * 0.43, x + 15, height * 0.43)
        painter.drawLine(x - 15, height * 0.53, x + 10, height * 0.53)

    @staticmethod
    def _draw_file_picker(painter: QPainter, width: float, height: float) -> None:
        window = QRectF(width * 0.18, height * 0.20, width * 0.64, height * 0.60)
        painter.drawRoundedRect(window, 8, 8)
        painter.drawLine(window.left(), window.top() + 30, window.right(), window.top() + 30)
        painter.setPen(QPen(QColor(MUTED), 2))
        for offset in (0.39, 0.50, 0.61):
            painter.drawLine(width * 0.28, height * offset, width * 0.61, height * offset)
        painter.setPen(QPen(QColor(WHITE), 3))
        painter.drawRoundedRect(QRectF(width * 0.62, height * 0.59, 70, 30), 6, 6)

    @staticmethod
    def _draw_authorization(painter: QPainter, width: float, height: float) -> None:
        painter.drawRoundedRect(
            QRectF(width * 0.16, height * 0.18, width * 0.68, height * 0.64), 9, 9
        )
        painter.drawLine(width * 0.16, height * 0.34, width * 0.84, height * 0.34)
        center = QPointF(width * 0.50, height * 0.56)
        shield = [
            QPointF(center.x(), center.y() - 40),
            QPointF(center.x() + 38, center.y() - 24),
            QPointF(center.x() + 30, center.y() + 25),
            QPointF(center.x(), center.y() + 46),
            QPointF(center.x() - 30, center.y() + 25),
            QPointF(center.x() - 38, center.y() - 24),
        ]
        painter.drawPolygon(shield)
        painter.drawLine(center.x() - 16, center.y() + 1, center.x() - 4, center.y() + 14)
        painter.drawLine(center.x() - 4, center.y() + 14, center.x() + 21, center.y() - 15)

    @staticmethod
    def _draw_archive(painter: QPainter, width: float, height: float) -> None:
        left = width * 0.18
        top = height * 0.30
        segment_width = width * 0.18
        for index in range(3):
            rect = QRectF(left + index * segment_width, top, segment_width, 48)
            painter.setBrush(QColor(WHITE) if index < 2 else QColor(CARD))
            painter.drawRect(rect)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(width * 0.50, height * 0.60, width * 0.50, height * 0.73)
        painter.drawLine(width * 0.45, height * 0.68, width * 0.50, height * 0.73)
        painter.drawLine(width * 0.55, height * 0.68, width * 0.50, height * 0.73)
        painter.drawRoundedRect(QRectF(width * 0.38, height * 0.73, width * 0.24, 28), 5, 5)


class TutorialGallery(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._index = 0
        self._pending_index: int | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.illustration = TutorialIllustration()
        self.illustration.clicked.connect(self.next_slide)
        self.opacity = QGraphicsOpacityEffect(self.illustration)
        self.opacity.setOpacity(1.0)
        self.illustration.setGraphicsEffect(self.opacity)
        layout.addWidget(self.illustration)
        self.slide_title = QLabel()
        self.slide_title.setStyleSheet("font-size: 16px; font-weight: 650;")
        self.slide_description = QLabel()
        self.slide_description.setObjectName("muted")
        self.slide_description.setWordWrap(True)
        layout.addWidget(self.slide_title)
        layout.addWidget(self.slide_description)
        controls = QHBoxLayout()
        self.previous_button = QPushButton("Previous")
        self.previous_button.clicked.connect(self.previous_slide)
        self.progress_label = QLabel()
        self.progress_label.setObjectName("muted")
        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.next_slide)
        controls.addWidget(self.previous_button)
        controls.addStretch()
        controls.addWidget(self.progress_label)
        controls.addStretch()
        controls.addWidget(self.next_button)
        layout.addLayout(controls)

        self.fade = QSequentialAnimationGroup(self)
        fade_out = QPropertyAnimation(self.opacity, b"opacity", self.fade)
        fade_out.setDuration(120)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.12)
        fade_out.setEasingCurve(QEasingCurve.Type.InQuad)
        fade_out.finished.connect(self._swap_pending_slide)
        fade_in = QPropertyAnimation(self.opacity, b"opacity", self.fade)
        fade_in.setDuration(190)
        fade_in.setStartValue(0.12)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.fade.addAnimation(fade_out)
        self.fade.addAnimation(fade_in)
        self.fade.finished.connect(self._animation_finished)

        left = QShortcut(QKeySequence("Left"), self)
        left.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        left.activated.connect(self.previous_slide)
        right = QShortcut(QKeySequence("Right"), self)
        right.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        right.activated.connect(self.next_slide)
        self._shortcuts = (left, right)
        self._show_slide()

    @property
    def current_index(self) -> int:
        return self._index

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Left:
            self.previous_slide()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Right:
            self.next_slide()
            event.accept()
            return
        super().keyPressEvent(event)

    def set_slide(self, index: int, *, animate: bool = True) -> None:
        if not 0 <= index < len(TUTORIAL_SLIDES):
            raise ValueError("Tutorial slide is out of range")
        if index == self._index or self.fade.state() != self.fade.State.Stopped:
            return
        if not animate:
            self._index = index
            self._show_slide()
            return
        self._pending_index = index
        self.previous_button.setEnabled(False)
        self.next_button.setEnabled(False)
        self.fade.start()

    def previous_slide(self) -> None:
        if self._index > 0:
            self.set_slide(self._index - 1)

    def next_slide(self) -> None:
        if self._index < len(TUTORIAL_SLIDES) - 1:
            self.set_slide(self._index + 1)

    def _swap_pending_slide(self) -> None:
        if self._pending_index is None:
            return
        self._index = self._pending_index
        self._pending_index = None
        self._show_slide()

    def _animation_finished(self) -> None:
        self.opacity.setOpacity(1.0)
        self._show_slide()

    def _show_slide(self) -> None:
        slide = TUTORIAL_SLIDES[self._index]
        self.illustration.set_scene(slide.scene)
        self.slide_title.setText(slide.title)
        self.slide_description.setText(slide.description)
        self.progress_label.setText(f"{self._index + 1} of {len(TUTORIAL_SLIDES)}")
        self.previous_button.setEnabled(self._index > 0)
        self.next_button.setEnabled(self._index < len(TUTORIAL_SLIDES) - 1)


class HelpTutorialPage(QWidget):
    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(38, 30, 38, 30)
        layout.setSpacing(18)
        heading, _ = page_heading(
            "Settings",
            "Help",
            "A quick explanation of Google authorization, followed by a visual walkthrough.",
        )
        layout.addWidget(heading)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(16)

        help_card = Card()
        help_title = QLabel("OAuth client files")
        help_title.setStyleSheet("font-size: 17px; font-weight: 650;")
        help_card.layout.addWidget(help_title)
        bullets = (
            "• What it is: a small JSON identity file for the desktop app, not your Gmail data.",
            "• Where it comes from: Google Cloud Console, under APIs and Services, then "
            "Credentials.",
            "• How it validates: Google matches the client identity and local browser callback "
            "before granting Gmail read-only access.",
            "• What to keep private: the client file and Windows-protected sign-in credentials.",
            "• Android and desktop can share one Cloud project, but desktop uses its own Desktop "
            "app client file.",
        )
        for text in bullets:
            label = QLabel(text)
            label.setObjectName("muted")
            label.setWordWrap(True)
            help_card.layout.addWidget(label)
        body_layout.addWidget(help_card)

        tutorial_card = Card()
        tutorial_title = QLabel("Tutorial")
        tutorial_title.setStyleSheet("font-size: 17px; font-weight: 650;")
        tutorial_hint = QLabel(
            "Click the picture or use Next. The Left and Right arrow keys work anywhere here."
        )
        tutorial_hint.setObjectName("muted")
        tutorial_hint.setWordWrap(True)
        tutorial_card.layout.addWidget(tutorial_title)
        tutorial_card.layout.addWidget(tutorial_hint)
        self.gallery = TutorialGallery()
        tutorial_card.layout.addWidget(self.gallery)
        body_layout.addWidget(tutorial_card)
        body_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)
        self.back_button = QPushButton("Back to Settings")
        self.back_button.clicked.connect(self.back_requested.emit)
        layout.addWidget(self.back_button, alignment=Qt.AlignmentFlag.AlignLeft)
