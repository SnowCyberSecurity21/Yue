"""Sprite lentalarini yuklash: kerak bo'lganda dekod, kadrlarga kesish, masshtablash, LRU kesh.

Lenta: ustunlar — kadrlar; v3 da qatorlar — qatlamlar (`Strip.rows`). PNG yuqoridan pastga
o'qiladi, shuning uchun faqat kerakli qatorgacha dekod qilinadi (ClipRect).
Dekod fon oqimida (`request`), natija Qt signal orqali asosiy oqimga keladi.
Kesh kaliti: (fayl, qatlam, masshtab) → kadrlar ro'yxati (QImage, premultiplied).
Kichraytirish `SmoothTransformation` bilan, bir marta — keyin tayyor kadr chiziladi.
Asl (2x) lenta xotirada qolmaydi: dekoddan keyin faqat kichraytirilgan kadrlar saqlanadi.
Kadrlarning ko'rinadigan qismi (`box`) ham shu dekodda, hamma kadr uchun birdan hisoblanadi —
gap pufagi yurish paytida har yangi kadrda lentani qayta o'qimasin.
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, QRect, QSize, Qt, Signal
from PySide6.QtGui import QImage, QImageReader

from yue.pet.pack import PackMeta, Strip, Variant

log = logging.getLogger(__name__)

Key = tuple[str, str, int]  # fayl, qatlam, masshtab*1000
Box = tuple[int, int, int, int]  # chap, tepa, o'ng, past (lenta px, o'ng/past — ichiga kirmaydi)
DEFAULT_BUDGET = 64 * 1024 * 1024
ALPHA_SEEN = 40  # shundan shaffofroq piksel "ko'rinmaydi" (soch chetidagi tutun hisobga olinmaydi)


def _argb(img: QImage) -> tuple[bytes, int]:
    img = img.convertToFormat(QImage.Format.Format_ARGB32)
    bpl = img.bytesPerLine()
    return bytes(img.constBits())[: bpl * img.height()], bpl


def _box_in(data: bytes, bpl: int, x0: int, w: int, h: int, alpha_min: int) -> Box | None:
    """ARGB32 baytlaridagi [x0, x0+w) ustunlar oralig'ining ko'rinadigan qismi."""
    table = bytes(1 if a >= alpha_min else 0 for a in range(256))
    top = bottom = None
    left, right = w, -1
    for y in range(h):
        start = y * bpl + x0 * 4 + 3  # little-endian ARGB32 → B, G, R, A
        mask = data[start : start + w * 4 : 4].translate(table)
        first = mask.find(1)
        if first < 0:
            continue
        if top is None:
            top = y
        bottom = y
        left, right = min(left, first), max(right, mask.rfind(1))
    if top is None or bottom is None:
        return None
    return left, top, right + 1, bottom + 1


def visible_box(img: QImage, alpha_min: int = ALPHA_SEEN) -> Box | None:
    """Rasmning ko'rinadigan qismi chegarasi (ARGB32 formatida o'qiladi)."""
    data, bpl = _argb(img)
    return _box_in(data, bpl, 0, img.width(), img.height(), alpha_min)


def strip_boxes(img: QImage, strip: Strip) -> list[Box | None]:
    """Lentaning (birinchi qatori) hamma kadrlari uchun `visible_box`."""
    data, bpl = _argb(img)
    fw, fh = strip.frame_width, min(strip.frame_height, img.height())
    n = min(strip.frames, img.width() // max(fw, 1))
    return [_box_in(data, bpl, i * fw, fw, fh, ALPHA_SEEN) for i in range(n)]


class SpriteStore(QObject):
    loaded = Signal()

    def __init__(self, meta: PackMeta, k: float = 1.0, budget: int = DEFAULT_BUDGET) -> None:
        super().__init__()
        self.meta = meta
        self.budget = budget
        self._k = self._qk(k)
        self._cache: OrderedDict[Key, list[QImage]] = OrderedDict()
        self._bytes = 0
        self._pending: set[tuple[str, int]] = set()
        self._boxes: dict[tuple[str, int], Box | None] = {}
        self._boxed: set[str] = set()  # `box` lari hisoblangan lentalar
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="yue-sprites")

    @staticmethod
    def _qk(k: float) -> int:
        return max(1, round(k * 1000))

    @property
    def k(self) -> float:
        """Lenta pikseli → qurilma pikseli koeffitsienti (masshtab × DPR)."""
        return self._k / 1000

    def set_k(self, k: float) -> None:
        qk = self._qk(k)
        if qk == self._k:
            return
        with self._lock:
            self._k = qk
            self._cache.clear()
            self._bytes = 0

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

    # --- o'qish ------------------------------------------------------------------------------

    def frames(self, strip: Strip, layer: str = "base") -> list[QImage] | None:
        key = (strip.file, layer, self._k)
        with self._lock:
            got = self._cache.get(key)
            if got is not None:
                self._cache.move_to_end(key)
            return got

    def frame(self, variant: Variant, index: int, layer: str = "base") -> QImage | None:
        strip, i = variant.locate(index)
        frames = self.frames(strip, layer)
        if frames and 0 <= i < len(frames):
            return frames[i]
        return None

    @staticmethod
    def _layers_of(strip: Strip, layers: Iterable[str]) -> tuple[str, ...]:
        return tuple(layer for layer in layers if layer in strip.rows) or ("base",)

    def ready(self, variant: Variant, layers: Iterable[str] = ("base",)) -> bool:
        layers = tuple(layers)
        return all(
            self.frames(s, layer) is not None
            for s in variant.strips
            for layer in self._layers_of(s, layers)
        )

    def request(self, variant: Variant, layers: Iterable[str] = ("base",)) -> None:
        """Fon oqimida yuklash (allaqachon keshda bo'lsa — hech narsa qilmaydi)."""
        layers = tuple(layers)
        for s in variant.strips:
            want = self._layers_of(s, layers)
            if all(self.frames(s, layer) is not None for layer in want):
                continue
            job = (s.file, self._k)
            with self._lock:
                if job in self._pending:
                    continue
                self._pending.add(job)
            self._pool.submit(self._load_job, s, want, self._k)

    def load_now(self, variant: Variant, layers: Iterable[str] = ("base",)) -> None:
        """Sinxron yuklash (dastur ochilganda birinchi kadrlar uchun)."""
        layers = tuple(layers)
        for s in variant.strips:
            want = self._layers_of(s, layers)
            if not all(self.frames(s, layer) is not None for layer in want):
                self._store(self._decode(s, want, self._k), self._k)

    def _load_job(self, strip: Strip, layers: tuple[str, ...], qk: int) -> None:
        try:
            self._store(self._decode(strip, layers, qk), qk)
        except Exception:
            log.exception("sprite yuklanmadi: %s", strip.file)
        finally:
            with self._lock:
                self._pending.discard((strip.file, qk))
        self.loaded.emit()

    def _decode(self, strip: Strip, layers: tuple[str, ...], qk: int) -> dict[Key, list[QImage]]:
        rows = strip.rows
        # Kamida base; so'ralgan qatlamlar va undan oldingilar (qatorlar ketma-ket o'qiladi).
        wanted = {"base", *layers}
        last_row = max(rows.index(layer) for layer in wanted if layer in rows)
        fw, fh, n = strip.frame_width, strip.frame_height, strip.frames
        path = self.meta.path(strip)
        reader = QImageReader(str(path))
        reader.setClipRect(QRect(0, 0, fw * n, fh * (last_row + 1)))
        img = reader.read()
        if img.isNull():
            raise OSError(f"lenta o'qilmadi: {path.name} ({reader.errorString()})")
        with self._lock:
            boxed = strip.file in self._boxed
        if not boxed:
            self._save_boxes(strip, strip_boxes(img, strip))
        img = img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        k = qk / 1000
        tw, th = max(1, round(fw * k)), max(1, round(fh * k))
        out: dict[Key, list[QImage]] = {}
        for row, layer in enumerate(rows[: last_row + 1]):
            frames = []
            for i in range(n):
                # Kadrma-kadr: qo'shni kadr chetlari aralashib ketmaydi.
                src = img.copy(i * fw, row * fh, fw, fh)
                frames.append(
                    src.scaled(
                        QSize(tw, th),
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            out[(strip.file, layer, qk)] = frames
        return out

    def _store(self, items: dict[Key, list[QImage]], qk: int) -> None:
        with self._lock:
            if qk != self._k:
                return  # masshtab o'zgarib ketdi — eskirgan natija
            for key, frames in items.items():
                if key in self._cache:
                    continue
                self._cache[key] = frames
                self._bytes += sum(f.sizeInBytes() for f in frames)
            while self._bytes > self.budget and len(self._cache) > 1:
                _, old = self._cache.popitem(last=False)
                self._bytes -= sum(f.sizeInBytes() for f in old)

    @property
    def cached_bytes(self) -> int:
        return self._bytes

    # --- ko'rinadigan qism -------------------------------------------------------------------

    def _save_boxes(self, strip: Strip, boxes: list[Box | None]) -> None:
        with self._lock:
            self._boxed.add(strip.file)
            for i in range(strip.frames):
                self._boxes[(strip.file, i)] = boxes[i] if i < len(boxes) else None

    def box(self, variant: Variant, index: int) -> Box | None:
        """Kadrning ko'rinadigan qismi (asl lenta pikselida). Lenta dekodida hamma kadr uchun
        birdan hisoblanadi; hali yuklanmagan bo'lsa — shu yerda (bir marta) o'qiladi."""
        strip, i = variant.locate(index)
        key = (strip.file, i)
        with self._lock:
            if key in self._boxes:
                return self._boxes[key]
        reader = QImageReader(str(self.meta.path(strip)))
        reader.setClipRect(QRect(0, 0, strip.frame_width * strip.frames, strip.frame_height))
        img = reader.read()
        self._save_boxes(strip, [] if img.isNull() else strip_boxes(img, strip))
        with self._lock:
            return self._boxes.get(key)
