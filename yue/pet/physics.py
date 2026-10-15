"""Yue jismi: gravitatsiya, yuzalar (pol va oyna tepalari), yurish, otish.

Qt'ga bog'liq emas. Koordinatalar — Qt mantiqiy piksellari, global; (x, y) — oyoq tagi nuqtasi.
Yuzalar har ~0.5 s da platformadan olinadigan oynalar ro'yxatidan qayta quriladi.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

GRAVITY = 1900.0  # px/s²
MAX_FALL = 1500.0  # px/s
MAX_THROW = 1800.0  # px/s
WALK_SPEED = 52.0  # px/s, masshtab 1.0 da
THROWN_SPEED = 900.0  # shundan tez qo'nsa — "otildi"
WALL_BOUNCE = 0.45
MIN_SEG = 24.0  # bundan qisqa yuzada turib bo'lmaydi


@dataclass(frozen=True)
class Rect:
    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return self.right - self.left

    def contains_x(self, x: float) -> bool:
        return self.left <= x <= self.right

    def translated(self, dx: float, dy: float) -> Rect:
        return Rect(self.left + dx, self.top + dy, self.right + dx, self.bottom + dy)


@dataclass(frozen=True)
class WinInfo:
    """Ko'rinib turgan oyna (mantiqiy piksellarda). Ro'yxat z-tartibda: eng yuqorisi birinchi."""

    handle: int
    rect: Rect
    maximized: bool = False


@dataclass(frozen=True)
class Seg:
    """Ustida turish mumkin bo'lgan gorizontal chiziq. owner=None — ekran poli (taskbar tepasi)."""

    a: float
    b: float
    y: float
    owner: int | None = None

    def contains(self, x: float) -> bool:
        return self.a <= x <= self.b


def subtract(intervals: list[tuple[float, float]], a: float, b: float) -> list[tuple[float, float]]:
    """[a, b] oralig'ini intervallar ro'yxatidan ayirish."""
    out: list[tuple[float, float]] = []
    for lo, hi in intervals:
        if b <= lo or a >= hi:
            out.append((lo, hi))
            continue
        if lo < a:
            out.append((lo, a))
        if b < hi:
            out.append((b, hi))
    return out


def build_surfaces(
    screens: Sequence[Rect],
    windows: Sequence[WinInfo] = (),
    headroom: float = 60.0,
) -> list[Seg]:
    """Ekranlar ish maydonlari (taskbarsiz) va oynalardan yuzalar ro'yxati.

    - har ekranning pastki cheti — pol;
    - oyna tepasi — yuza, lekin undan yuqoridagi (z-tartibda oldinroq) oynalar yopgan qismlari
      chiqarib tashlanadi;
    - maksimallashgan oynalar va tepasida joy (headroom) yo'q oynalar hisobga olinmaydi.
    """
    segs = [Seg(s.left, s.right, s.bottom, None) for s in screens]
    for i, w in enumerate(windows):
        r = w.rect
        if w.maximized or r.width < MIN_SEG:
            continue
        screen = next((s for s in screens if s.left <= r.left + r.width / 2 <= s.right), None)
        if screen is None or not (screen.top + headroom <= r.top < screen.bottom - 4):
            continue
        parts = [(max(r.left, screen.left), min(r.right, screen.right))]
        for above in windows[:i]:
            ar = above.rect
            if ar.top <= r.top < ar.bottom:
                parts = subtract(parts, ar.left, ar.right)
        segs.extend(Seg(lo, hi, r.top, w.handle) for lo, hi in parts if hi - lo >= MIN_SEG)
    return segs


def screen_for(x: float, y: float, screens: Sequence[Rect]) -> Rect:
    """Nuqta turgan ekran (ekranlar orasidagi bo'shliqda — eng yaqini)."""

    def dist(s: Rect) -> float:
        dx = max(s.left - x, 0.0, x - s.right)
        dy = max(s.top - y, 0.0, y - s.bottom)
        return dx * dx + dy * dy

    return min(screens, key=dist)


@dataclass
class Body:
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    seg: Seg | None = None
    owner_rect: Rect | None = None  # ustida turgan oynaning oxirgi ma'lum o'rni

    @property
    def grounded(self) -> bool:
        return self.seg is not None

    # --- tushish -----------------------------------------------------------------------------

    def drop(self, vx: float = 0.0, vy: float = 0.0) -> None:
        self.seg = None
        self.owner_rect = None
        self.vx = max(-MAX_THROW, min(MAX_THROW, vx))
        self.vy = max(-MAX_THROW, min(MAX_THROW, vy))

    def step_fall(
        self, dt: float, surfaces: Sequence[Seg], screens: Sequence[Rect], half_width: float
    ) -> float | None:
        """Bir qadam tushish. Qo'nsa — qo'nish tezligi (px/s), aks holda None."""
        if self.grounded:
            return None
        self.vy = min(MAX_FALL, self.vy + GRAVITY * dt)
        y0 = self.y
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vx *= max(0.0, 1.0 - 0.35 * dt)  # havo qarshiligi

        scr = screen_for(self.x, y0, screens)
        lo, hi = scr.left + half_width, scr.right - half_width
        if self.x < lo:
            self.x, self.vx = lo, abs(self.vx) * WALL_BOUNCE
        elif self.x > hi:
            self.x, self.vx = hi, -abs(self.vx) * WALL_BOUNCE

        if self.vy < 0:
            if self.y < scr.top:  # ekran tepasidan chiqib ketmasin
                self.y, self.vy = scr.top, 0.0
            return None

        hit = self._first_crossed(surfaces, y0, self.y)
        if hit is None:
            if self.y > scr.bottom:  # hech qaysi yuzaga tushmadi — shu ekran poliga
                floor = Seg(scr.left, scr.right, scr.bottom, None)
                return self.land(floor, None)
            return None
        return self.land(hit, None)

    def _first_crossed(self, surfaces: Iterable[Seg], y0: float, y1: float) -> Seg | None:
        best: Seg | None = None
        for s in surfaces:
            if s.contains(self.x) and y0 <= s.y <= y1 and (best is None or s.y < best.y):
                best = s
        return best

    def land(self, seg: Seg, owner_rect: Rect | None) -> float:
        speed = self.vy
        self.y = seg.y
        self.vx = self.vy = 0.0
        self.seg = seg
        self.owner_rect = owner_rect
        return speed

    # --- yer ustida --------------------------------------------------------------------------

    def step_walk(self, dt: float, target: float, speed: float) -> bool:
        """Maqsad tomon yurish. True — yetib keldi. Yuza tugasa — tushishni boshlaydi."""
        if not self.grounded:
            return False
        d = target - self.x
        step = speed * dt
        if abs(d) <= step:
            self.x = target
            arrived = True
        else:
            self.x += step if d > 0 else -step
            arrived = False
        if self.seg is not None and not self.seg.contains(self.x):
            self.drop(vx=(speed if d > 0 else -speed) * 0.6)
            return False
        return arrived

    def follow_ground(self, surfaces: Sequence[Seg], windows: Sequence[WinInfo]) -> str:
        """Yuzalar yangilangach: "ok", "moved" (oyna bilan surildi) yoki "lost" (tushadi)."""
        if self.seg is None:
            return "lost"
        owner = self.seg.owner
        moved = False
        if owner is not None:
            win = next((w for w in windows if w.handle == owner), None)
            if win is None:
                self.drop()
                return "lost"
            if self.owner_rect is not None and win.rect != self.owner_rect:
                old = self.owner_rect
                # Faqat surilish (o'lcham o'zgarishi emas) — x ham suriladi
                if abs(win.rect.width - old.width) < 1.0:
                    self.x += win.rect.left - old.left
                moved = True
            self.owner_rect = win.rect
            candidates = [s for s in surfaces if s.owner == owner and abs(s.y - win.rect.top) < 1]
        else:
            candidates = [s for s in surfaces if s.owner is None]
        new = next((s for s in candidates if s.contains(self.x)), None)
        if new is None:
            self.drop()
            return "lost"
        if abs(new.y - self.y) > 0.5:
            moved = True
        self.seg, self.y = new, new.y
        return "moved" if moved else "ok"

    def attach_owner(self, windows: Sequence[WinInfo]) -> None:
        """Qo'nganda ustida turgan oynaning o'rnini eslab qolish."""
        if self.seg is None or self.seg.owner is None:
            self.owner_rect = None
            return
        win = next((w for w in windows if w.handle == self.seg.owner), None)
        self.owner_rect = win.rect if win else None
