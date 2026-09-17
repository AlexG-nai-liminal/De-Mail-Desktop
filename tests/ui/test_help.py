import pytest
from PySide6.QtCore import QAbstractAnimation, Qt

from demail.ui.help import TUTORIAL_SLIDES, HelpTutorialPage, TutorialGallery
from demail.ui.main_window import MainWindow


def wait_for_gallery(qtbot, gallery: TutorialGallery, index: int) -> None:
    qtbot.waitUntil(
        lambda: gallery.current_index == index
        and gallery.fade.state() == QAbstractAnimation.State.Stopped,
        timeout=1_000,
    )


def test_settings_opens_help_before_the_tutorial(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show_page(4)
    assert window.settings_stack.currentIndex() == 0

    window.open_help_button.click()

    assert window.settings_stack.currentIndex() == 1
    assert window.help_page.gallery.current_index == 0
    assert window.help_page.gallery.slide_title.text() == "Download the desktop client file"
    assert "OAuth client files" in [
        label.text()
        for label in window.help_page.findChildren(type(window.help_page.gallery.slide_title))
    ]


def test_tutorial_buttons_fade_between_four_scenes(qtbot) -> None:
    gallery = TutorialGallery()
    qtbot.addWidget(gallery)
    assert len(TUTORIAL_SLIDES) == 4
    assert not gallery.previous_button.isEnabled()

    gallery.next_button.click()
    assert gallery.fade.state() == QAbstractAnimation.State.Running
    wait_for_gallery(qtbot, gallery, 1)
    assert gallery.progress_label.text() == "2 of 4"

    gallery.set_slide(3, animate=False)
    assert not gallery.next_button.isEnabled()
    assert gallery.previous_button.isEnabled()


def test_tutorial_left_and_right_arrow_keys_change_scenes(qtbot) -> None:
    page = HelpTutorialPage()
    qtbot.addWidget(page)
    page.show()
    page.gallery.setFocus()

    qtbot.keyClick(page.gallery, Qt.Key.Key_Right)
    wait_for_gallery(qtbot, page.gallery, 1)
    qtbot.keyClick(page.gallery, Qt.Key.Key_Left)
    wait_for_gallery(qtbot, page.gallery, 0)


def test_tutorial_picture_click_advances_but_stops_at_last_scene(qtbot) -> None:
    gallery = TutorialGallery()
    qtbot.addWidget(gallery)
    gallery.illustration.clicked.emit()
    wait_for_gallery(qtbot, gallery, 1)
    gallery.set_slide(3, animate=False)
    gallery.illustration.clicked.emit()
    assert gallery.current_index == 3


@pytest.mark.parametrize("index", [-1, len(TUTORIAL_SLIDES)])
def test_tutorial_rejects_out_of_range_scene(index: int, qtbot) -> None:
    gallery = TutorialGallery()
    qtbot.addWidget(gallery)
    with pytest.raises(ValueError, match="out of range"):
        gallery.set_slide(index)
