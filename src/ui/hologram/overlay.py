"""
Hologram Overlay Widget.

Paints a circular, JARVIS-dial-style holographic HUD: a tick-marked
outer bezel, a segmented dash ring, a bright inner ring, a
voice-activity highlight arc, a small cluster of indicator dots, a
soft central glow, and optional floating light particles. No text is
drawn anywhere in it, by design. Deliberately original artwork —
geometric shapes and gradients built from scratch, not any
copyrighted asset — inspired by the general "sci-fi holographic dial"
aesthetic rather than reproducing any specific one.

Threading note: every method on this class must only ever be called on
the Qt thread that owns it (see service.py for why). The seven Signals
below are the one exception — Qt automatically marshals a signal
emitted from another thread onto this widget's thread as a queued,
thread-safe call to the connected slot, which is what makes
DesktopCompanionService's live-update methods (including
``set_speaking``) safe to call from anywhere.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen, QRadialGradient, QRegion
from PySide6.QtWidgets import QWidget

from src.ui.hologram.config import HologramConfig, HologramSize
from src.ui.hologram.theme import HologramPalette, get_palette


@dataclass
class _Particle:
    """One floating light particle. Mutable — updated in place every
    tick rather than reallocated, to keep the per-frame cost low."""

    x: float
    y: float
    speed: float
    drift_phase: float
    radius: float
    age: float = 0.0
    lifetime: float = 4.0


# "Energy scale" is how much bigger/brighter the hologram reads when
# EON is actively speaking versus idle — the pulse the person asked
# for. Idle sits a little below 1.0 (a slightly "resting" dial);
# speaking sits above it. Both leave headroom inside the widget so the
# dial can grow without ever being clipped by the window edge (see the
# 0.82 margin baked into the base radius in paintEvent).
_IDLE_ENERGY_SCALE = 0.90
_SPEAKING_ENERGY_SCALE = 1.10


class HologramOverlay(QWidget):
    """
    A frameless, translucent window that paints the hologram dial and
    nothing else — no buttons, no text. Its hit-testable area is
    masked down to a circle matching the drawn dial (see
    ``_apply_mask``), so:

      - Clicking and dragging the visible dial moves the window
        (``mousePressEvent``/``mouseMoveEvent`` below).
      - Clicking the transparent square corners around that circle
        still reaches whatever's on the desktop underneath, since
        those corners fall outside the mask entirely.
    """

    # Emitted by DesktopCompanionService's set_* methods, safe to call
    # from any thread — see the threading note in the module docstring.
    themeChanged = Signal(str)
    sizeChanged = Signal(str)
    particlesToggled = Signal(bool)
    glowChanged = Signal(float)
    speedChanged = Signal(float)
    transparencyChanged = Signal(float)
    speakingChanged = Signal(bool)

    # Degrees per frame each ring rotates at animation_speed == 1.0.
    # Different speeds/directions per ring is what sells the "layered
    # rotating HUD" look rather than everything spinning as one unit.
    _RING_SPEEDS = (0.35, -0.22, 0.55)

    def __init__(self, config: HologramConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._config = config
        self._palette: HologramPalette = get_palette(config.theme)

        self._ring_angles = [0.0, 0.0, 0.0]
        self._tick_angle = 0.0
        self._highlight_angle = 0.0
        self._wave_phase = 0.0
        self._particles: list[_Particle] = []

        self._speaking = False
        self._energy_scale = _IDLE_ENERGY_SCALE
        self._activity = 0.0  # 0.0 (idle) .. 1.0 (fully "speaking")

        self._drag_offset: QPoint | None = None

        self._configure_window()
        self._apply_geometry()
        self._apply_mask()
        self._seed_particles()

        self.themeChanged.connect(self._on_theme_changed)
        self.sizeChanged.connect(self._on_size_changed)
        self.particlesToggled.connect(self._on_particles_toggled)
        self.glowChanged.connect(self._on_glow_changed)
        self.speedChanged.connect(self._on_speed_changed)
        self.transparencyChanged.connect(self._on_transparency_changed)
        self.speakingChanged.connect(self._on_speaking_changed)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(max(1, 1000 // max(1, config.fps)))

    # ---- window setup ---------------------------------------------------

    def _configure_window(self) -> None:
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool  # no taskbar entry, no alt-tab entry
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        # Showing the overlay must never steal focus from whatever the
        # user is actually typing/clicking into.
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setWindowOpacity(self._config.transparency)

    def _apply_geometry(self) -> None:
        screen = QGuiApplication.primaryScreen()
        screen_rect = (
            screen.availableGeometry()
            if screen is not None
            else self.rect().adjusted(0, 0, 1920, 1080)
        )

        if self._config.size == HologramSize.FULLSCREEN:
            self.setGeometry(screen_rect)
            return

        diameter = self._config.diameter()
        margin = 24
        x = screen_rect.right() - diameter - margin
        y = screen_rect.bottom() - diameter - margin
        self.setGeometry(x, y, diameter, diameter)

    def _apply_mask(self) -> None:
        """
        Restricts both painting and mouse hit-testing to a circle
        matching the drawn dial (not the widget's full, square-ish
        bounding rect) — computed the same way as the base radius in
        ``paintEvent``, with a little extra room for the outer glow.

        Doing this by the dial's actual visual size rather than the
        widget's raw rect matters most in fullscreen mode, where the
        widget spans the whole (non-square) screen: masking to
        ``self.rect()`` there would stretch into a screen-covering
        ellipse and swallow clicks nowhere near the visible dial.
        Anchoring on ``min(width, height)`` keeps the interactive area
        a true circle, matching what's actually drawn, at every size.
        """
        center = self.rect().center()
        radius = int(min(self.width(), self.height()) / 2.0 * 0.95)
        mask_rect = QRect(
            center.x() - radius,
            center.y() - radius,
            radius * 2,
            radius * 2,
        )
        self.setMask(QRegion(mask_rect, QRegion.Ellipse))

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        super().resizeEvent(event)
        self._apply_mask()

    # ---- dragging ---------------------------------------------------

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        if self._drag_offset is not None and (event.buttons() & Qt.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        self._drag_offset = None
        event.accept()

    # ---- particles --------------------------------------------------

    def _seed_particles(self) -> None:
        self._particles = [self._spawn_particle() for _ in range(self._particle_count())]

    def _particle_count(self) -> int:
        if not self._config.particles_enabled:
            return 0

        # Scale with window area (relative to the medium preset) so
        # fullscreen mode doesn't try to animate an absurd number of
        # particles, and small mode isn't sparse — capped at both ends
        # to keep the effect lightweight regardless of size.
        area_factor = (min(self.width(), self.height()) / 380.0) ** 2
        return max(8, min(140, int(34 * area_factor)))

    def _spawn_particle(self) -> _Particle:
        width, height = max(self.width(), 1), max(self.height(), 1)
        return _Particle(
            x=random.uniform(width * 0.15, width * 0.85),
            y=random.uniform(height * 0.6, height * 1.05),
            speed=random.uniform(6.0, 16.0),
            drift_phase=random.uniform(0.0, math.tau),
            radius=random.uniform(1.2, 3.0),
            lifetime=random.uniform(3.0, 6.0),
        )

    # ---- live config updates (slots; always run on this widget's thread) --

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        self._config.theme = HologramConfig.parse_theme(theme)
        self._palette = get_palette(self._config.theme)

    @Slot(str)
    def _on_size_changed(self, size: str) -> None:
        self._config.size = HologramConfig.parse_size(size)
        self._apply_geometry()
        self._apply_mask()
        self._seed_particles()

    @Slot(bool)
    def _on_particles_toggled(self, enabled: bool) -> None:
        self._config.particles_enabled = enabled
        self._seed_particles()

    @Slot(float)
    def _on_glow_changed(self, value: float) -> None:
        self._config.glow_intensity = max(0.0, min(1.0, value))

    @Slot(float)
    def _on_speed_changed(self, value: float) -> None:
        self._config.animation_speed = max(0.0, value)

    @Slot(float)
    def _on_transparency_changed(self, value: float) -> None:
        self._config.transparency = max(0.05, min(1.0, value))
        self.setWindowOpacity(self._config.transparency)

    @Slot(bool)
    def _on_speaking_changed(self, speaking: bool) -> None:
        self._speaking = speaking

    # ---- animation ----------------------------------------------------

    def _tick(self) -> None:
        speed = self._config.animation_speed

        # Ease toward the target energy scale rather than snapping —
        # a smooth grow/shrink reads as "coming alive", a hard jump
        # reads as a glitch. The same eased 0..1 activity value also
        # drives glow/highlight-arc brightness below.
        target_scale = _SPEAKING_ENERGY_SCALE if self._speaking else _IDLE_ENERGY_SCALE
        self._energy_scale += (target_scale - self._energy_scale) * min(1.0, 0.12 * speed)
        span = _SPEAKING_ENERGY_SCALE - _IDLE_ENERGY_SCALE
        self._activity = max(
            0.0, min(1.0, (self._energy_scale - _IDLE_ENERGY_SCALE) / span if span else 0.0)
        )

        # Rings spin a little faster while EON is actively speaking —
        # the same "coming alive" idea applied to motion, not just size.
        rate_multiplier = 1.0 + self._activity * 0.8

        for i, ring_speed in enumerate(self._RING_SPEEDS):
            self._ring_angles[i] = (
                self._ring_angles[i] + ring_speed * speed * rate_multiplier
            ) % 360.0

        self._tick_angle = (self._tick_angle + 0.08 * speed) % 360.0
        self._highlight_angle = (self._highlight_angle - 0.5 * speed * rate_multiplier) % 360.0
        self._wave_phase = (self._wave_phase + 0.012 * speed) % 1.0

        if self._config.particles_enabled:
            self._update_particles(speed)

        self.update()

    def _update_particles(self, speed: float) -> None:
        dt = 1.0 / max(1, self._config.fps)

        for i, particle in enumerate(self._particles):
            particle.age += dt * speed
            particle.y -= particle.speed * dt * speed
            particle.x += math.sin(particle.age * 1.4 + particle.drift_phase) * 0.4

            if particle.age >= particle.lifetime or particle.y < -10:
                self._particles[i] = self._spawn_particle()

    # ---- painting -----------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = self.rect()
        center = QPointF(rect.center())
        # 0.62 (not something closer to the window edge) is deliberate:
        # the glow drawn in _paint_glow reaches out to radius * 1.35,
        # and _energy_scale can push radius up to 1.10x at full
        # speaking activity. 0.62 * 1.10 * 1.35 ≈ 0.92, which stays
        # inside the window (and the 0.95-radius mask in
        # _apply_mask) at every combination — a larger base fraction
        # would let the glow get hard-clipped at the window edge
        # right when it's brightest.
        radius = min(rect.width(), rect.height()) / 2.0 * 0.62 * self._energy_scale

        self._paint_glow(painter, center, radius)
        self._paint_energy_wave(painter, center, radius)
        self._paint_tick_bezel(painter, center, radius)
        self._paint_dash_ring(painter, center, radius)
        self._paint_core_ring(painter, center, radius)
        self._paint_highlight_arc(painter, center, radius)
        self._paint_indicator_dots(painter, center, radius)

        if self._config.particles_enabled:
            self._paint_particles(painter)

        painter.end()

    def _paint_glow(self, painter: QPainter, center: QPointF, radius: float) -> None:
        intensity = self._config.glow_intensity * (0.75 + 0.5 * self._activity)

        gradient = QRadialGradient(center, radius * 1.35)
        inner = QColor(self._palette.glow)
        inner.setAlphaF(min(1.0, 0.5 * intensity))
        outer = QColor(self._palette.glow)
        outer.setAlphaF(0.0)
        gradient.setColorAt(0.0, inner)
        gradient.setColorAt(1.0, outer)

        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(center, radius * 1.35, radius * 1.35)

    def _paint_energy_wave(self, painter: QPainter, center: QPointF, radius: float) -> None:
        # Two waves, offset half a cycle apart, so a new one is always
        # partway through expanding — a continuous pulse rather than a
        # single ring that resets abruptly.
        for offset in (0.0, 0.5):
            progress = (self._wave_phase + offset) % 1.0
            wave_radius = radius * (0.3 + 0.22 * progress)
            alpha = (
                max(0.0, 1.0 - progress)
                * (0.35 + 0.35 * self._activity)
                * self._config.glow_intensity
            )

            color = QColor(self._palette.accent)
            color.setAlphaF(alpha)

            painter.setPen(QPen(color, 1.2))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(center, wave_radius, wave_radius)

    def _paint_tick_bezel(self, painter: QPainter, center: QPointF, radius: float) -> None:
        """The outer ring of many short radial ticks — the dial-bezel
        look from the reference image's outermost band."""
        color = QColor(self._palette.accent)
        color.setAlphaF(0.55)
        painter.setPen(QPen(color, 1.4))

        outer = radius * 1.0
        inner = radius * 0.9
        tick_count = 72

        for i in range(tick_count):
            angle_rad = math.radians(self._tick_angle + i * (360.0 / tick_count))
            cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
            painter.drawLine(
                QPointF(center.x() + inner * cos_a, center.y() + inner * sin_a),
                QPointF(center.x() + outer * cos_a, center.y() + outer * sin_a),
            )

    def _paint_dash_ring(self, painter: QPainter, center: QPointF, radius: float) -> None:
        """A ring made of short dashes with gaps — the segmented band
        sitting just inside the tick bezel in the reference image."""
        dash_radius = radius * 0.78
        color = QColor(self._palette.ring)
        color.setAlphaF(0.6)
        pen = QPen(color, 5, Qt.SolidLine, Qt.FlatCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        rect = QRectF(
            center.x() - dash_radius,
            center.y() - dash_radius,
            dash_radius * 2,
            dash_radius * 2,
        )

        dash_count = 28
        dash_span = 6.0  # degrees of visible dash
        gap_span = (360.0 / dash_count) - dash_span

        for i in range(dash_count):
            start = self._ring_angles[1] + i * (dash_span + gap_span)
            painter.drawArc(rect, int(start * 16), int(dash_span * 16))

    def _paint_core_ring(self, painter: QPainter, center: QPointF, radius: float) -> None:
        """The bright, mostly-solid inner ring — the dial's main
        boundary, equivalent to the glowing cyan ring around the
        empty (text-free, by design) center in the reference image."""
        core_radius = radius * 0.58

        color = QColor(self._palette.ring)
        color.setAlphaF(min(1.0, 0.8 + 0.2 * self._activity))
        width = 5 + 2 * self._activity

        painter.setPen(QPen(color, width, Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(center, core_radius, core_radius)

        # A second, fainter ring just inside it for depth.
        inner_color = QColor(self._palette.accent)
        inner_color.setAlphaF(0.35)
        painter.setPen(QPen(inner_color, 1.5))
        painter.drawEllipse(center, core_radius * 0.88, core_radius * 0.88)

    def _paint_highlight_arc(self, painter: QPainter, center: QPointF, radius: float) -> None:
        """The single brighter, contrasting arc segment that stands out
        against the rest of the dial — a voice-activity indicator:
        short and dim while idle, sweeping wider and brighter while
        EON is speaking, echoing the one highlighted segment in the
        reference image."""
        arc_radius = radius * 0.78
        span = 18.0 + 70.0 * self._activity

        color = QColor(self._palette.particle)
        color.setAlphaF(min(1.0, 0.5 + 0.5 * self._activity))
        painter.setPen(QPen(color, 6, Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(Qt.NoBrush)

        rect = QRectF(
            center.x() - arc_radius,
            center.y() - arc_radius,
            arc_radius * 2,
            arc_radius * 2,
        )
        painter.drawArc(rect, int(self._highlight_angle * 16), int(span * 16))

    def _paint_indicator_dots(self, painter: QPainter, center: QPointF, radius: float) -> None:
        """A small cluster of dots near the top of the dial, each
        pulsing with its own phase while EON speaks — a lightweight
        nod to the little indicator lights in the reference image,
        doubling as a voice-activity readout."""
        dot_radius_base = radius * 0.9
        painter.setPen(Qt.NoPen)

        dot_angles = (-100.0, -85.0, -70.0, -55.0)

        for i, angle_deg in enumerate(dot_angles):
            angle_rad = math.radians(angle_deg)
            x = center.x() + dot_radius_base * math.cos(angle_rad)
            y = center.y() + dot_radius_base * math.sin(angle_rad)

            pulse = 0.5 + 0.5 * math.sin(self._tick_angle * 0.2 + i * 1.7)
            size = 2.2 + pulse * 2.4 * (0.4 + 0.6 * self._activity)

            color = QColor(self._palette.particle)
            color.setAlphaF(min(1.0, (0.35 + 0.5 * self._activity) * (0.5 + 0.5 * pulse)))

            painter.setBrush(color)
            painter.drawEllipse(QPointF(x, y), size, size)

        # A couple of small stationary dots further out, in the style
        # of corner readouts on a sci-fi HUD.
        static_color = QColor(self._palette.accent)
        static_color.setAlphaF(0.45)
        painter.setBrush(static_color)
        for dx_factor, dy_factor, dot_radius in (
            (-1.1, -0.85, 4),
            (1.15, 0.7, 3.5),
        ):
            painter.drawEllipse(
                QPointF(center.x() + radius * dx_factor, center.y() + radius * dy_factor),
                dot_radius,
                dot_radius,
            )

    def _paint_particles(self, painter: QPainter) -> None:
        base_color = self._palette.particle
        painter.setPen(Qt.NoPen)

        for particle in self._particles:
            life_ratio = 1.0 - (particle.age / particle.lifetime if particle.lifetime else 1.0)
            alpha = max(0.0, min(1.0, life_ratio)) * 0.85

            point = QPointF(particle.x, particle.y)
            glow_radius = particle.radius * 3

            gradient = QRadialGradient(point, glow_radius)
            near = QColor(base_color)
            near.setAlphaF(alpha)
            far = QColor(base_color)
            far.setAlphaF(0.0)
            gradient.setColorAt(0.0, near)
            gradient.setColorAt(1.0, far)

            painter.setBrush(gradient)
            painter.drawEllipse(point, glow_radius, glow_radius)
