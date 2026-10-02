import shutil
from pathlib import Path

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from demail.app import run_selftest
from demail.ui.about import AboutPage
from demail.ui.support import SUPPORT_CODES, SupportDialog

ASSETS = Path(__file__).resolve().parents[2] / "src" / "demail" / "assets"


def test_support_popup_contains_supplied_codes_in_order(qtbot) -> None:
    dialog = SupportDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.windowTitle() == "Support Continued Development"
    titles = [label.text() for label in dialog.findChildren(QLabel) if label.text()]
    assert titles == ["Support Continued Development", "PayPal", "Cash App", "Venmo"]
    for label, (service, _) in zip(dialog.code_labels, SUPPORT_CODES, strict=True):
        assert not label.pixmap().isNull()
        assert label.accessibleName() == f"{service} support QR code"
        assert label.pixmap().width() <= 220
        assert label.pixmap().height() <= 220
    qtbot.mouseClick(dialog.findChild(QPushButton), Qt.MouseButton.LeftButton)
    assert not dialog.isVisible()


def test_about_support_link_opens_dialog_and_can_reopen(qtbot) -> None:
    page = AboutPage("version history")
    qtbot.addWidget(page)
    page.show()
    assert page.support_button.text() == "Support"
    assert page.layout().itemAt(page.layout().count() - 1).widget() is page.support_button
    opened = []

    def close_dialog() -> None:
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, SupportDialog)
        opened.append(dialog.windowTitle())
        dialog.reject()

    for _ in range(2):
        QTimer.singleShot(0, close_dialog)
        page.support_button.click()
    assert opened == ["Support Continued Development"] * 2
    assert page.history.toPlainText() == "version history"


@pytest.mark.parametrize("content", [None, b"not an image", b""])
def test_missing_or_corrupt_code_does_not_hide_other_services(qtbot, tmp_path, content) -> None:
    for _, filename in SUPPORT_CODES:
        shutil.copyfile(ASSETS / "support" / filename, tmp_path / filename)
    paypal = tmp_path / "paypal.png"
    if content is None:
        paypal.unlink()
    else:
        paypal.write_bytes(content)
    dialog = SupportDialog(asset_root=tmp_path)
    qtbot.addWidget(dialog)
    assert dialog.code_labels[0].text() == "PayPal QR code is unavailable."
    assert all(not label.pixmap().isNull() for label in dialog.code_labels[1:])
    shutil.copyfile(ASSETS / "support" / "paypal.png", paypal)
    recovered = SupportDialog(asset_root=tmp_path)
    qtbot.addWidget(recovered)
    assert not recovered.code_labels[0].pixmap().isNull()


def test_frozen_selftest_requires_support_assets(qapp, tmp_path) -> None:
    shutil.copytree(ASSETS, tmp_path / "assets")
    root = tmp_path / "assets"
    run_selftest(root)
    (root / "support" / "venmo.png").unlink()
    with pytest.raises(RuntimeError, match="missing resource: venmo.png"):
        run_selftest(root)
