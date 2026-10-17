"""Tests for EON's drawn mark.

Nothing is shipped as an icon file: the orb is painted at whatever size
the shell asks for. So what these check is that the painting actually
happens — at every size, with something visible in it, in the right
colours — and that installing it is harmless in the cases where it has
nothing to install onto.

Runs against Qt's ``offscreen`` platform plugin, like the window tests.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from src.ui.assets import (  # noqa: E402
    ICON_SIZES,
    claim_taskbar_identity,
    eon_icon,
    install_app_icon,
)


@pytest.fixture(scope="module")
def app():
    """A process-wide QApplication, as EON has in practice."""
    instance = QApplication.instance() or QApplication(["EON-tests"])
    yield instance


# --- the drawing -----------------------------------------------------------


def test_the_mark_is_drawn_at_every_size_windows_asks_for(app):
    icon = eon_icon()

    assert not icon.isNull()
    assert sorted(s.width() for s in icon.availableSizes()) == sorted(ICON_SIZES)


@pytest.mark.parametrize("size", ICON_SIZES)
def test_every_size_has_a_drawing_in_it(app, size):
    """A size that came out blank or clipped would be invisible."""
    pixmap = eon_icon().pixmap(size, size)

    assert (pixmap.width(), pixmap.height()) == (size, size)

    image = pixmap.toImage()
    painted = sum(
        1
        for y in range(size)
        for x in range(size)
        if image.pixelColor(x, y).alpha() > 0
    )

    assert painted > size * size * 0.25, f"{size}px drew almost nothing"


@pytest.mark.parametrize("size", (32, 256))
def test_the_mark_is_a_bright_cyan_orb(app, size):
    image = eon_icon().pixmap(size, size).toImage()

    core = image.pixelColor(size // 2, size // 2)

    assert core.alpha() > 0
    # Bright and cool. A grey mark, or a red one, fails here.
    assert core.blue() > core.red()
    assert core.green() > core.red()
    assert min(core.red(), core.green(), core.blue()) > 180

    # And teal rather than white once you are out towards the rim.
    rim = image.pixelColor(size // 2 + int(size * 0.30), size // 2)

    assert rim.alpha() > 0
    assert rim.blue() > rim.red()
    assert rim.green() > rim.red()


def test_the_ring_inside_the_orb_is_lighter_than_the_orb(app):
    """The mark is an orb *with a ring*, not a plain ball.

    Drawn in the orb's own teal the ring disappeared into it, which is
    why it is nearly white now — so this checks there is a band between
    the core and the rim that is brighter than both.
    """
    size = 256
    image = eon_icon().pixmap(size, size).toImage()

    def brightness(offset: float) -> int:
        pixel = image.pixelColor(size // 2 + int(size * offset), size // 2)
        return min(pixel.red(), pixel.green(), pixel.blue())

    ring = brightness(0.245)
    between = brightness(0.31)

    assert ring > between, "the ring should stand out from the orb"


# --- installing it ---------------------------------------------------------


def test_installing_sets_the_icon_on_the_application(app):
    install_app_icon(app)

    assert not app.windowIcon().isNull()
    assert sorted(
        s.width() for s in app.windowIcon().availableSizes()
    ) == sorted(ICON_SIZES)


def test_installing_with_no_argument_falls_back_to_the_running_app(app):
    """The two services call it without one, from different threads of
    startup, and either of them may be the one that made the app."""
    install_app_icon()

    assert not app.windowIcon().isNull()


def test_claiming_the_taskbar_identity_is_safe_off_windows():
    """A no-op everywhere but Windows, and it must never raise."""
    claim_taskbar_identity()
