"""EON's mark: the cyan orb, drawn rather than shipped.

Windows labels every taskbar button with the icon of the process that
owns the window. EON runs under ``python.exe`` and set no icon of its
own, so its windows wore the Python logo.

The mark is painted with ``QPainter`` instead of loaded from a file.
That is deliberate:

    - There is no icon file to lose, and nothing to keep in step with
      the code that shows it.
    - Windows asks for an icon at several sizes (16 in the taskbar, 32
      in alt-tab, 256 in the file picker), and one PNG scaled up looks
      soft. Painting each size on demand keeps every one of them sharp.
    - It is text, so it reviews and merges like the rest of the code.

It is the same orb as the hologram: a bright core inside a ring, in the
cyan theme. The proportions below are fractions of the requested size,
so the drawing is identical at 16px and at 256px.

Requires: PySide6 (already a dependency for the hologram overlay).
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import QApplication

#: The sizes Windows asks for, from the taskbar up to the file picker.
#: Painting each one is cheap and beats letting the shell scale a
#: single bitmap.
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)

#: The orb's palette, taken from the hologram's cyan theme.
CORE = QColor("#f4fffd")
MID = QColor("#7ff0e0")
RING = AColor("#5eead4")
EDGE = QColor("#0f766e")

#: The inner ring is nearly white on purpose. Drawn in the same teal as
#: the orb it vanished into it, and the mark read as a plain ball
#: rather than an orb with a ring.
HILITE = QColor("#c8fff4")

#: Names EON's windows to the Windows shell. Without it the shell
#: groups every window of ``python.exe`` together and can take the
#: button's icon from the executable; with it, EON's windows are their
#: own group with their own icon.
APP_USER_MODEL_ID = "Sarvam.EON"

# --- the shape, as fractions of the requested size -------------------------

_GLOW_RADIUS = 0.50
_ORB_RADIUS = 0.37
_RING_RADIUS = 0.245
_RING_WIDTH = 0.062
_CORE_RADIUS = 0.10
_HIGHLIGHT_SHIFT = 0.09


def _paint_orb(painter: QPainter, size: int) -> None:
    """Paints the orb to fill a ``size`` x ``size`` square.

    Args:
        painter: An active painter. The caller owns it.
        size: The side of the square, in pixels.
    """
    centre = QPointF(size / 2, size / 2)

    # A soft halo, so the mark has some presence on a dark taskbar
    # without a hard edge. It fades to nothing at the square's edge.
    glow = QRadialGradient(centre, size * _GLOW_RADIUS)
    edge = QColor(RING)
    edge.setAlpha(0)
    near = QColor(RING)
    near.setAlpha(70)
    glow.setColorAt(0.62, edge)
    glow.setColorAt(0.86, near)
    glow.setColorAt(1.00, edge)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(glow)
    painter.drawEllipse(centre, size * _GLOW_RADIUS, size * _GLOW_RADIUS)

    # The orb itself, lit from the upper left: a bright core falling
    # away to the rim colour.
    orb = QRadialGradient(
        centre,
        size * _ORB_RADIUS,
        QPointF(
            centre.x() - size * _HIGHLIGHT_SHIFT,
            centre.y() - size * _HIGHLIGHT_SHIFT,
        ),
    )
    orb.setColorAt(0.00, CORE)
    orb.setColorAt(0.38, MID)
    orb.setColorAt(0.78, RING)
    orb.setColorAt(1.00, EDGE)

    painter.setBrush(orb)
    painter.drawEllipse(centre, size * _ORB_RADIUS, size * _ORB_RADIUS)

    # The ring the hologram has, which is what makes this EON's mark
    # rather than a generic dot.
    pen = QPen(HILITE)
    pen.setWidthF(size * _RING_WIDTH)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(centre, size * _RING_RADIUS, size * _RING_RADIUS)

    # And the core, back on top of the ring.
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(CORE)
    painter.drawEllipse(centre, size * _CORE_RADIUS, size * _CORE_RADIUS)


def eon_icon() -> QIcon:
    """EON's mark, at every size Windows asks for.

    Must be called after a ``QApplication`` exists — a ``QPixmap``
    cannot be made without one.

    Returns:
        A multi-size icon.
    """
    icon = QIcon()

    for size in ICON_SIZES:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        try:
            _paint_orb(painter, size)
        finally:
            # A painter left running on a pixmap leaves it unusable.
            painter.end()

        icon.addPixmap(pixmap)

    return icon


def install_app_icon(app: QApplication | None = None) -> None:
    """Gives EON's windows EON's icon instead of Python's.

    Sets it on the application rather than on each window, so every
    window EON opens inherits it and nothing has to remember to ask.

    Args:
        app: The application to set it on. Defaults to the process's
            own ``QApplication``, if there is one.
    """
    app = app if app is not None else QApplication.instance()

    if app is None:
        return

    app.setWindowIcon(eon_icon())
    claim_taskbar_identity()


def claim_taskbar_identity() -> None:
    """Tells the Windows shell that EON's windows are EON's.

    Cosmetic, and Windows-only: on any other platform it does nothing.
    Every failure is swallowed, because a taskbar that groups EON's
    windows with Python's is not worth refusing to start over.
    """
    if sys.platform != "win32":
        return

    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            APP_USER_MODEL_ID
        )
    except Exception:  # pragma: no cover - Windows-only, cosmetic
        pass
