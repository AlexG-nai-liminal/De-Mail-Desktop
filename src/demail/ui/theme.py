"""Monochrome desktop design system."""

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

BLACK = "#050505"
PANEL = "#0B0B0B"
CARD = "#111111"
CARD_HOVER = "#171717"
BORDER = "#292929"
MUTED = "#A3A3A3"
WHITE = "#FFFFFF"

STYLE_SHEET = f"""
* {{
    font-family: "Segoe UI Variable", "Segoe UI";
    color: {WHITE};
}}
QMainWindow, QWidget#appRoot, QStackedWidget {{ background: {BLACK}; }}
QWidget#navigationRail {{ background: {PANEL}; border-right: 1px solid {BORDER}; }}
QLabel#brand {{ font-size: 22px; font-weight: 650; letter-spacing: 0.5px; }}
QLabel#eyebrow {{ color: {MUTED}; font-size: 11px; font-weight: 650; letter-spacing: 1px; }}
QLabel#pageTitle {{ font-size: 30px; font-weight: 650; }}
QLabel#pageDescription, QLabel#muted {{ color: {MUTED}; font-size: 13px; }}
QFrame#card {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px; }}
QPushButton {{
    background: transparent; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 9px 14px; min-height: 20px; font-weight: 600;
}}
QPushButton:hover {{ background: {CARD_HOVER}; border-color: #3A3A3A; }}
QPushButton:focus {{ border: 2px solid {WHITE}; padding: 8px 13px; }}
QPushButton:disabled {{ color: #666666; border-color: #202020; }}
QPushButton[primary="true"] {{ background: {WHITE}; color: {BLACK}; border-color: {WHITE}; }}
QPushButton[primary="true"]:hover {{ background: #E6E6E6; }}
QPushButton[primary="true"]:disabled {{
    background: #303030; color: #777777; border-color: #3A3A3A;
}}
QPushButton[nav="true"] {{
    border: 0; border-radius: 8px; text-align: left; padding: 10px 12px;
    color: {MUTED}; font-weight: 500;
}}
QPushButton[nav="true"]:checked {{ background: {CARD_HOVER}; color: {WHITE}; }}
QLineEdit, QComboBox, QDateEdit, QPlainTextEdit {{
    background: {PANEL}; border: 1px solid {BORDER}; border-radius: 8px;
    min-height: 22px; padding: 9px 10px;
    selection-background-color: {WHITE}; selection-color: {BLACK};
}}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QPlainTextEdit:focus {{
    border: 2px solid {WHITE}; padding: 8px 9px;
}}
QComboBox QAbstractItemView::item {{ min-height: 30px; padding: 5px 8px; }}
QPushButton[quickArchive="true"] {{
    background: {PANEL}; border: 1px solid {BORDER}; border-radius: 0;
    min-height: 46px; padding: 10px 8px; font-size: 12px; font-weight: 650;
}}
QPushButton[quickArchive="true"][segmentPosition="middle"],
QPushButton[quickArchive="true"][segmentPosition="last"] {{ border-left: 0; }}
QPushButton[quickArchive="true"][segmentPosition="first"] {{
    border-top-left-radius: 9px; border-bottom-left-radius: 9px;
}}
QPushButton[quickArchive="true"][segmentPosition="last"] {{
    border-top-right-radius: 9px; border-bottom-right-radius: 9px;
}}
QPushButton[quickArchive="true"]:checked {{
    background: {WHITE}; color: {BLACK}; border-color: {WHITE};
}}
QPushButton[quickArchive="true"]:disabled {{
    background: {PANEL}; color: #666666; border-color: #202020;
}}
QProgressBar {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 5px; height: 8px; }}
QProgressBar::chunk {{ background: {WHITE}; border-radius: 4px; }}
QScrollArea {{ border: 0; background: transparent; }}
"""


def apply_theme(application: QApplication) -> None:
    application.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BLACK))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(WHITE))
    palette.setColor(QPalette.ColorRole.Base, QColor(PANEL))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(CARD))
    palette.setColor(QPalette.ColorRole.Text, QColor(WHITE))
    palette.setColor(QPalette.ColorRole.Button, QColor(CARD))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(WHITE))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(WHITE))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(BLACK))
    application.setPalette(palette)
    application.setStyleSheet(STYLE_SHEET)
