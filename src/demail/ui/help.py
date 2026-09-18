"""Compact OAuth help and a monochrome, keyboard-friendly tutorial gallery."""

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSequentialAnimationGroup,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPainterPath, QPixmap, QShortcut
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
from .theme import BLACK, BORDER, MUTED

TUTORIAL_ASSET_DIR = Path(__file__).resolve().parent.parent / "assets" / "tutorial"


@dataclass(frozen=True, slots=True)
class TutorialSlide:
    title: str
    description: str
    image_name: str


TUTORIAL_SLIDES = (
    TutorialSlide(
        "Download the desktop client file",
        "In Google Cloud, open APIs and Services, then Credentials. Create a Desktop app "
        "OAuth client and download its JSON file.",
        "oauth-download.png",
    ),
    TutorialSlide(
        "Choose the file in de-Mail",
        "Return to Settings, choose the downloaded JSON file, and keep it in a private folder.",
        "choose-client-file.png",
    ),
    TutorialSlide(
        "Approve read-only access",
        "Your browser signs you in. Google validates the desktop client and the local callback "
        "before granting Gmail read-only access.",
        "authorize-read-only.png",
    ),
    TutorialSlide(
        "Archive and verify",
        "Choose mail, review the exact count, choose a destination, and let de-Mail verify every "
        "saved message.",
        "archive-verify.png",
    ),
)


class TutorialIllustration(QWidget):
    clicked = Signal()

    def __init__(
        self, parent: QWidget | None = None, asset_dir: Path | None = None
    ) -> None:
        super().__init__(parent)
        self._asset_dir = asset_dir or TUTORIAL_ASSET_DIR
        self._image_name = ""
        self._pixmap = QPixmap()
        self.setMinimumHeight(250)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName("Tutorial illustration. Click for the next scene.")
        self.set_scene(TUTORIAL_SLIDES[0].image_name)

    @property
    def image_available(self) -> bool:
        return not self._pixmap.isNull()

    def set_scene(self, image_name: str) -> None:
        if image_name not in {slide.image_name for slide in TUTORIAL_SLIDES}:
            raise ValueError("Unknown tutorial scene")
        self._image_name = image_name
        self._pixmap = QPixmap(str(self._asset_dir / image_name))
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
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        bounds = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.setBrush(QColor(BLACK))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(bounds, 12, 12)
        clip = QPainterPath()
        clip.addRoundedRect(bounds, 12, 12)
        painter.setClipPath(clip)
        target = bounds.toAlignedRect()
        if self.image_available:
            scaled = self._pixmap.scaled(
                target.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            source = QRect(
                max(0, (scaled.width() - target.width()) // 2),
                max(0, (scaled.height() - target.height()) // 2),
                min(target.width(), scaled.width()),
                min(target.height(), scaled.height()),
            )
            painter.drawPixmap(target, scaled, source)
        else:
            painter.setPen(QColor(MUTED))
            painter.drawText(
                target,
                Qt.AlignmentFlag.AlignCenter,
                "Tutorial image unavailable",
            )
        painter.setClipping(False)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QColor(BORDER))
        painter.drawRoundedRect(bounds, 12, 12)


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
        self.illustration.set_scene(slide.image_name)
        self.slide_title.setText(slide.title)
        self.slide_description.setText(slide.description)
        self.progress_label.setText(f"{self._index + 1} of {len(TUTORIAL_SLIDES)}")
        self.previous_button.setEnabled(self._index > 0)
        self.next_button.setEnabled(self._index < len(TUTORIAL_SLIDES) - 1)


class HelpTutorialPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(38, 30, 38, 30)
        layout.setSpacing(18)
        heading, _ = page_heading(
            "Help",
            "OAuth and archiving",
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
