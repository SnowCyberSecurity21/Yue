"""Yuening oynasi: shaffof, ramkasiz, doim ustda, fokusni olmaydi. Chizish, sichqoncha, taymerlar.

Koordinatalar Qt mantiqiy piksellarida. Platforma oyna to'rtburchaklarini fizik piksellarda beradi —
`to_logical` ularni ekran DPR'i bo'yicha o'tkazadi (Qt6: ekran geometriyasining chap-yuqori
nuqtasi fizik, o'lchami mantiqiy).
"""

from __future__ import annotations

import contextlib
import logging
import math
import time
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QGuiApplication, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from yue.config import Config
from yue.pet.behavior import Behavior, Visual, crossfade_alphas
from yue.pet.pack import PackMeta, Variant
from yue.pet.physics import Rect, WinInfo, build_surfaces
from yue.pet.sprites import SpriteStore
from yue.pet.wardrobe import Look
from yue.platform import Platform

log = logging.getLogger(__name__)

GRAB_FRACTION = 0.45  # yoqa: ko'rinadigan qism tepasidan shuncha pastda (chibi boshi ~40%)
HIT_ALPHA = 40  # shundan shaffofroq joy bosilsa — Yuega tegilmagan hisoblanadi
HIT_RADIUS = 2  # qurilma px — ingichka joylarni (barmoq, soch) bosish osonroq bo'lsin
DRAG_THRESHOLD = 4
SURFACE_REFRESH_MS = 500
FAST_TICK_MS = 16  # yurish, sudrash, tushish, crossfade — ~60 Hz (yurish o'zgarmas tezlikda)


@dataclass(frozen=True)
class ScreenInfo:
    logical: Rect  # geometry() — mantiqiy
    native_left: float
    native_top: float
    dpr: float

    @property
    def native(self) -> Rect:
        lg = self.logical
        return Rect(
            self.native_left,
            self.native_top,
            self.native_left + lg.width * self.dpr,
            self.native_top + (lg.bottom - lg.top) * self.dpr,
        )


def to_logical(rect: tuple[int, int, int, int], screens: Sequence[ScreenInfo]) -> Rect:
    """Fizik to'rtburchakni (markazi turgan ekran DPR'i bo'yicha) mantiqiyga o'tkazish."""
    cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2

    def dist(s: ScreenInfo) -> float:
        n = s.native
        return max(n.left - cx, 0, cx - n.right) ** 2 + max(n.top - cy, 0, cy - n.bottom) ** 2

    s = min(screens, key=dist)
    ox, oy = s.logical.left, s.logical.top

    def conv(x: float, y: float) -> tuple[float, float]:
        return ox + (x - s.native_left) / s.dpr, oy + (y - s.native_top) / s.dpr

    left, top = conv(rect[0], rect[1])
    right, bottom = conv(rect[2], rect[3])
    return Rect(left, top, right, bottom)


class PetWindow(QWidget):
    clicked = Signal()
    context_requested = Signal(QPoint)
    pet_event = Signal(str, object)
    moved = Signal()

    def __init__(
        self,
        meta: PackMeta,
        behavior: Behavior,
        store: SpriteStore,
        platform: Platform,
        cfg: Config,
    ) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("Yue")

        self.meta = meta
        self.behavior = behavior
        self.store = store
        self.platform = platform
        self.cfg = cfg

        self.scale = 1.0
        self.anchor = QPointF()
        self.set_size(float(cfg.get("pet.size", 1.0)))

        self._shown: Visual | None = None
        self._painted_key: tuple | None = None
        self._press: QPointF | None = None
        self._grab = QPointF()  # kursordan langargacha (mantiqiy px), sudrash boshida hisoblanadi
        self._drag_samples: deque[tuple[float, float, float]] = deque(maxlen=8)
        self._dpr = 0.0

        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self._tick)
        self.surface_timer = QTimer(self)
        self.surface_timer.timeout.connect(self.refresh_surfaces)
        self.store.loaded.connect(self._on_sprites_loaded)

    # --- o'lcham va joylashuv ----------------------------------------------------------------

    def set_size(self, size: float) -> None:
        size = max(0.5, min(2.0, size))
        self.scale = self.meta.scale_for(size)
        fw, _ = self.meta.max_frame_size()
        above = self.meta.max_above_foot() * self.scale
        below = self.meta.max_below_foot() * self.scale
        w = math.ceil(fw * self.scale) + 4
        h = math.ceil(above + below) + 4
        self.setFixedSize(w, h)
        self.anchor = QPointF(w / 2, above + 2)
        self.behavior.scale = self.scale / self.meta.scale_for(1.0)
        self.behavior.half_width = 0.5 * self.meta.ref_width * self.scale
        self._dpr = 0.0  # keyingi kadrda sprite masshtabi qayta hisoblanadi

    @property
    def char_height(self) -> float:
        return self.meta.max_above_foot() * self.scale

    def place(self) -> None:
        b = self.behavior.body
        x, y = round(b.x - self.anchor.x()), round(b.y - self.anchor.y())
        if x != self.x() or y != self.y():
            self.move(x, y)
            self.moved.emit()

    def head_anchor(self) -> tuple[float, float, float]:
        """(markaz x, bosh tepasi y, oyoq y) — global mantiqiy px, gap pufagi uchun."""
        b = self.behavior.body
        vis = self._shown
        foot_y = self.meta.max_above_foot()
        if vis is not None:
            variant = self.meta.variant(vis.slot, vis.look.outfit)
            if variant is not None:
                strip, _ = variant.locate(vis.frame)
                foot_y = strip.foot_y
                box = self.store.box(variant, vis.frame)
                if box is not None:
                    foot_y -= box[1]  # ko'rinadigan qism tepasi
        top = b.y - foot_y * self.scale + 6 * self.scale
        return b.x, top, b.y

    def screens(self) -> list[ScreenInfo]:
        out = []
        for sc in QGuiApplication.screens():
            g = sc.geometry()
            out.append(
                ScreenInfo(
                    Rect(g.left(), g.top(), g.left() + g.width(), g.top() + g.height()),
                    g.left(),
                    g.top(),
                    sc.devicePixelRatio(),
                )
            )
        return out

    @staticmethod
    def work_areas() -> list[Rect]:
        out = []
        for sc in QGuiApplication.screens():
            a = sc.availableGeometry()
            out.append(Rect(a.left(), a.top(), a.left() + a.width(), a.top() + a.height()))
        return out

    def refresh_surfaces(self) -> None:
        areas = self.work_areas()
        windows: list[WinInfo] = []
        if self.cfg.get("pet.walk_on_windows", True):
            try:
                scr = self.screens()
                windows = [
                    WinInfo(w.handle, to_logical(w.rect, scr), w.maximized)
                    for w in self.platform.visible_windows()
                ]
            except OSError:
                log.warning("oynalar ro'yxati olinmadi")
        bh = self.behavior
        bh.screens = areas
        bh.windows = windows
        bh.surfaces = build_surfaces(areas, windows, headroom=self.char_height * 0.9)
        if bh.body.grounded and not bh.dragging:
            if bh.body.follow_ground(bh.surfaces, windows) == "lost":
                bh.look = bh.wardrobe.adapt(bh.look, "fall")

    def spawn(self) -> None:
        """Ekran tepasidan tushib keladi (dastur ochilganda)."""
        import random

        scr = QGuiApplication.primaryScreen().availableGeometry()
        b = self.behavior.body
        b.x = random.uniform(scr.left() + scr.width() * 0.2, scr.right() - scr.width() * 0.2)
        b.y = scr.top() + self.char_height
        b.drop()
        self.behavior.gentle_drop = True  # ochilishda tushib kelish — "yiqilish" emas
        self.refresh_surfaces()
        self.place()

    def summon(self) -> None:
        """Kursor turgan joyga tepadan tushib keladi."""
        pos = QCursor.pos()
        sc = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        a = sc.availableGeometry()
        b = self.behavior.body
        b.x = float(max(a.left() + 40, min(a.right() - 40, pos.x())))
        b.y = float(max(a.top() + self.char_height, pos.y() - 40))
        self.behavior.plan.clear()
        self.behavior.step = None
        b.drop()
        self.behavior.gentle_drop = True
        self.refresh_surfaces()
        self.place()

    def drop_from_top(self) -> None:
        """Sinov: Yueni turgan joyidan ekran tepasiga ko'tarib tashlash (fall → land)."""
        b = self.behavior.body
        sc = QGuiApplication.screenAt(QPoint(int(b.x), int(b.y) - 5))
        a = (sc or QGuiApplication.primaryScreen()).availableGeometry()
        self.behavior.plan.clear()
        self.behavior.step = None
        b.y = float(a.top() + self.char_height)
        b.drop()
        self.behavior.gentle_drop = False
        self.refresh_surfaces()
        self.place()

    # --- kadr ---------------------------------------------------------------------------------

    def _check_dpr(self) -> None:
        dpr = self.devicePixelRatioF()
        if dpr != self._dpr:
            self._dpr = dpr
            self.store.set_k(self.scale * dpr)

    @staticmethod
    def _layers(vis: Visual) -> tuple[str, ...]:
        return ("base", *vis.look.overlays)

    def _ensure(self, vis: Visual) -> bool:
        variant = self.meta.variant(vis.slot, vis.look.outfit)
        if variant is None:
            return True  # chizadigan narsa yo'q (buzilgan to'plam) — bo'sh kadr
        layers = self._layers(vis)
        if self.store.ready(variant, layers):
            return True
        self.store.request(variant, layers)
        return False

    def _request(self, slot: str, look: Look) -> None:
        dslot, dlook, _ = self.behavior.resolve(slot, look)
        variant = self.meta.variant(dslot, dlook.outfit)
        if variant is not None:
            self.store.request(variant, ("base", *dlook.overlays))

    def _prefetch(self) -> None:
        bh = self.behavior
        look = bh.look
        for step in list(bh.plan)[:4]:
            lk = step.look or look
            self._request(step.slot, lk)
        for slot in ("dangle", "fall"):
            self._request(slot, bh.wardrobe.adapt(look, slot))

    def _tick(self) -> None:
        now = time.monotonic()
        self._check_dpr()
        vis = self.behavior.tick(now)
        for name, data in self.behavior.pop_events():
            if name in ("landed", "thrown", "action", "drag", "sayr", "command", "command_end"):
                self.pet_event.emit(name, data)
            if name == "landed":
                self.refresh_surfaces()
        self.place()

        if self._ensure(vis) and (vis.fade_from is None or self._ensure(vis.fade_from)):
            self._shown = vis
        self._prefetch()
        key = self._paint_key(self._shown)
        if key != self._painted_key:
            self.update()

        bh = self.behavior
        moving = bh.dragging or not bh.body.grounded
        walking = bh.step is not None and bh.step.mode == "walk"
        if moving or walking or (vis.fade_from is not None):
            interval = FAST_TICK_MS
        else:
            fps = bh.fps(vis.slot, self.meta.variant(vis.slot, vis.look.outfit))
            interval = 250 if fps <= 0 else max(33, int(1000 / fps))
        if self.timer.interval() != interval:
            self.timer.setInterval(interval)

    def _on_sprites_loaded(self) -> None:
        if self.isVisible():
            self._tick()

    @staticmethod
    def _paint_key(vis: Visual | None) -> tuple | None:
        if vis is None:
            return None
        fade = None
        if vis.fade_from is not None:
            f = vis.fade_from
            fade = (f.slot, f.frame, f.look, f.mirror, round(vis.fade, 2))
        return (vis.slot, vis.frame, vis.look, vis.mirror, fade)

    def paintEvent(self, _e: QPaintEvent) -> None:  # noqa: N802
        vis = self._shown
        self._painted_key = self._paint_key(vis)
        if vis is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if vis.fade_from is not None:
            # Eski kadr birinchi yarmida to'liq, yangisi ikkinchi yarmida to'liq; yangisi ustida.
            old, new = crossfade_alphas(vis.fade)
            self._draw(p, vis.fade_from, old)
            self._draw(p, vis, new)
        else:
            self._draw(p, vis, 1.0)
        p.end()

    def _target(self, vis: Visual) -> tuple[QRectF, Variant] | None:
        """Kadr chiziladigan to'rtburchak (oyna koordinatasi, langar bo'yicha) va variant."""
        variant = self.meta.variant(vis.slot, vis.look.outfit)
        if variant is None:
            return None
        strip, _ = variant.locate(vis.frame)
        w, h = strip.frame_width * self.scale, strip.frame_height * self.scale
        ax, ay = self.anchor.x(), self.anchor.y()
        return QRectF(ax - w / 2, ay - strip.foot_y * self.scale, w, h), variant

    def _draw(self, p: QPainter, vis: Visual, opacity: float) -> None:
        got = self._target(vis)
        if got is None:
            return
        target, variant = got
        ax = self.anchor.x()
        if opacity <= 0:
            return
        p.save()
        p.setOpacity(opacity)
        if vis.mirror:
            p.translate(ax, 0)
            p.scale(-1, 1)
            p.translate(-ax, 0)
        for layer in self._layers(vis):
            img = self.store.frame(variant, vis.frame, layer)
            if img is not None:
                p.drawImage(target, img)
        p.restore()

    def hit(self, pos: QPointF) -> bool:
        """Oynadagi nuqtada Yue bormi (kadrning shaffofligi bo'yicha)."""
        vis = self._shown
        if vis is None:
            return False
        for v in (vis, vis.fade_from) if vis.fade_from is not None else (vis,):
            got = self._target(v)
            if got is None:
                continue
            target, variant = got
            img = self.store.frame(variant, v.frame)
            if img is None:
                continue
            x = 2 * self.anchor.x() - pos.x() if v.mirror else pos.x()
            ix = int((x - target.left()) / target.width() * img.width())
            iy = int((pos.y() - target.top()) / target.height() * img.height())
            r = HIT_RADIUS
            for py in range(max(0, iy - r), min(img.height(), iy + r + 1)):
                for px in range(max(0, ix - r), min(img.width(), ix + r + 1)):
                    if img.pixelColor(px, py).alpha() >= HIT_ALPHA:
                        return True
        return False

    def grab_offset(self) -> QPointF:
        """Kursordan langargacha masofa (mantiqiy px): kursor yoqadan ushlaydi.

        Yoqa — `dangle` (yoki uning o'rnini bosuvchi) kadr 0 ning ko'rinadigan qismi tepasidan
        ~45% pastda, markazda (rasmlarda o'lchangan; 22% da nuqta peshonaga tushardi).
        """
        bh = self.behavior
        slot, look, frame = bh.resolve("dangle", bh.look)
        variant = self.meta.variant(slot, look.outfit)
        if variant is None:
            return QPointF(0, 0)
        index = frame if frame is not None else 0
        strip, _ = variant.locate(index)
        box = self.store.box(variant, index) or (0, 0, strip.frame_width, strip.foot_y)
        left, top, right, bottom = box
        gx = (left + right) / 2
        gy = top + GRAB_FRACTION * (bottom - top)
        return QPointF((strip.frame_width / 2 - gx) * self.scale, (strip.foot_y - gy) * self.scale)

    # --- sichqoncha --------------------------------------------------------------------------

    def mousePressEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if not self.hit(e.position()):
            e.ignore()  # shaffof joy — Yuega tegilmadi
            return
        if e.button() == Qt.MouseButton.LeftButton:
            self._press = e.globalPosition()
        elif e.button() == Qt.MouseButton.RightButton:
            self.context_requested.emit(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if self._press is None:
            return
        g = e.globalPosition()
        bh = self.behavior
        if not bh.dragging:
            if (g - self._press).manhattanLength() < DRAG_THRESHOLD:
                return
            bh.start_drag(time.monotonic())
            self._drag_samples.clear()
            self._grab = self.grab_offset()
        bh.drag_to(g.x() + self._grab.x(), g.y() + self._grab.y())
        self._drag_samples.append((time.monotonic(), g.x(), g.y()))
        self.place()

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.button() != Qt.MouseButton.LeftButton or self._press is None:
            return
        self._press = None
        bh = self.behavior
        if bh.dragging:
            vx = vy = 0.0
            s = [x for x in self._drag_samples if time.monotonic() - x[0] < 0.12]
            if len(s) >= 2 and s[-1][0] > s[0][0]:
                dt = s[-1][0] - s[0][0]
                vx, vy = (s[-1][1] - s[0][1]) / dt, (s[-1][2] - s[0][2]) / dt
            self.refresh_surfaces()
            bh.end_drag(vx, vy)
            self.pet_event.emit("released", (vx, vy))
        else:
            self.clicked.emit()

    # --- ko'rinish ---------------------------------------------------------------------------

    def showEvent(self, e) -> None:  # noqa: N802
        super().showEvent(e)
        with contextlib.suppress(OSError, ValueError):
            self.platform.set_noactivate(int(self.winId()))
        self.behavior.last = time.monotonic()
        self.timer.start(33)
        self.surface_timer.start(SURFACE_REFRESH_MS)

    def hideEvent(self, e) -> None:  # noqa: N802
        self.timer.stop()
        self.surface_timer.stop()
        super().hideEvent(e)
