"""Sprite to'plami metama'lumotlari (`pack.json`, versiya 3 yoki 4). Qt'ga bog'liq emas.

Ikkala versiya bitta modelga keltiriladi:
- **look** — rasmning bitta ko'rinishi (papka). v4: `tee`, `tee_glasses`, `hood_black`, ...
  (aksessuarlar rasmga chizilgan); v3: kiyim papkasi (`tee`, `hood_black`, ...) + qatlamlar.
- **variant** — slotning bitta look'dagi rasmi: bir yoki bir nechta lenta (`Strip`).
  Ifodalarda ikki lenta bo'ladi, kadr raqami ular bo'ylab ketma-ket hisoblanadi.
- **lenta** — gorizontal kadrlar qatori; v3 da qatorlar — qatlamlar (`rows`).
Langar: `(frame_width/2, foot_y)` — oyoq tagi nuqtasi.
Variantda o'z `fps` bo'lishi mumkin (slot `fps` idan ustun) va yurishlarda `speed` — tayanch
oyoqdan o'lchangan tezlik (lenta px/s, shu fps da; videodan olingan yurishlar).
O'tish klipida (`kind: transition`, masalan `hood_up`) `walk_frame` — klip oxiriga mos yurish
kadri: keyingi yurish shu kadrdan boshlanadi (sakrash bo'lmasin).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SUPPORTED_VERSIONS = (3, 4)


class PackError(Exception):
    """To'plam noto'g'ri yoki to'liq emas."""


@dataclass(frozen=True)
class Strip:
    file: str  # to'plam papkasiga nisbatan, masalan "tee/idle.png"
    frames: int
    frame_width: int
    frame_height: int
    foot_y: int
    names: tuple[str, ...] = ()
    rows: tuple[str, ...] = ("base",)  # v3: qatorlar = qatlamlar


@dataclass(frozen=True)
class Variant:
    strips: tuple[Strip, ...]
    fps: float | None = None  # slot fps idan ustun
    speed: float | None = None  # yurish: lenta px/s (fps da); yo'q — umumiy tezlik
    walk_frame: int | None = None  # o'tish klipi: undan keyingi yurish shu kadrdan boshlanadi

    @property
    def frames(self) -> int:
        return sum(s.frames for s in self.strips)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(n for s in self.strips for n in s.names)

    def locate(self, frame: int) -> tuple[Strip, int]:
        """Variantdagi kadr raqami → (lenta, lentadagi kadr)."""
        frame = max(0, min(frame, self.frames - 1))
        for s in self.strips:
            if frame < s.frames:
                return s, frame
            frame -= s.frames
        return self.strips[-1], self.strips[-1].frames - 1


@dataclass(frozen=True)
class LookInfo:
    outfit: str  # asosiy kiyim: tee / hoodie_black / hoodie_silver
    hood: bool = False
    glasses: bool = False
    phones: str = "none"  # head / neck / none


@dataclass(frozen=True)
class Blink:
    """Ko'z yumib-ochish (idle): `rest` kadrlari aylanadi, har `every_s` da bir marta `frames`."""

    frames: tuple[int, ...]
    rest: tuple[int, ...]
    every_s: tuple[float, float] = (3.0, 6.0)


@dataclass(frozen=True)
class SlotInfo:
    name: str
    fps: float
    loop: bool
    variants: Mapping[str, Variant]
    kind: str = "state"  # state / activity / reaction
    sheet: str = ""  # qaysi slot rasmi (sit, standup → sitdown)
    reverse: bool = False
    hold: int | None = None  # bitta kadrni ushlab turish (sit = sitdown oxirgi kadri: -1)
    faces_right: bool = False
    static: bool = False
    pose: str = ""  # lying / air / jump
    sit: bool = False  # oldidan sitdown, keyin standup
    fallback: str = ""
    time: tuple[str, ...] = ()
    blink: Blink | None = None
    fps_scale: float = 1.0  # teskari slot tezroq (hood_down = hood_up × 1.5)
    # v3 kiyim qoidalari
    outfits: tuple[str, ...] = ()
    require: tuple[str, ...] = ()
    forbid: tuple[str, ...] = ()
    prefer: Mapping[str, float] = field(default_factory=dict)

    @property
    def frames(self) -> int:
        """Birinchi variantdagi kadrlar soni (v3 da hamma kiyimda bir xil)."""
        v = next(iter(self.variants.values()), None)
        return v.frames if v else 0

    @property
    def names(self) -> tuple[str, ...]:
        v = next(iter(self.variants.values()), None)
        return v.names if v else ()

    def fps_of(self, variant: Variant | None) -> float:
        """Variantning o'z fps i bo'lsa — u, aks holda slotniki (× `fps_scale`)."""
        fps = variant.fps if variant is not None and variant.fps else self.fps
        return fps * self.fps_scale

    def duration(self, frames: int | None = None, fps: float | None = None) -> float:
        """Bir marta o'ynash vaqti (s)."""
        n = self.frames if frames is None else frames
        fps = self.fps if fps is None else fps
        if self.hold is not None or fps <= 0:
            return 0.0
        return n / fps

    def frame_at(self, t: float, frames: int | None = None, fps: float | None = None) -> int:
        """Slot boshlanganidan t soniya o'tgandagi kadr indeksi: floor(t × fps) (mod kadrlar)."""
        n = self.frames if frames is None else frames
        fps = self.fps if fps is None else fps
        if self.hold is not None:
            return self.hold % n if n else 0
        if self.static or fps <= 0 or n <= 1:
            return 0
        i = int(t * fps)
        i = i % n if self.loop else min(i, n - 1)
        return n - 1 - i if self.reverse else i

    def allowed_in(self, period: str) -> bool:
        return not self.time or period in self.time


@dataclass(frozen=True)
class PackMeta:
    root: Path
    name: str
    version: int
    outfits: tuple[str, ...]  # asosiy kiyimlar (v3: kiyim papkalari)
    layers: tuple[str, ...]  # v4: faqat "base"
    looks: Mapping[str, LookInfo]
    slots: Mapping[str, SlotInfo]
    raw: Mapping[str, Any]
    px_scale: float  # lenta pikseli → mantiqiy piksel (o'lcham 1.0 da)
    ref_width: float  # tik turgan Yuening taxminiy eni (lenta px) — devorlar uchun

    def scale_for(self, size: float = 1.0) -> float:
        """Lenta pikselidan mantiqiy pikselga koeffitsient."""
        return self.px_scale * size

    def path(self, strip: Strip) -> Path:
        return self.root / strip.file

    def variant(self, slot: str, look: str) -> Variant | None:
        info = self.slots.get(slot)
        return info.variants.get(look) if info else None

    def looks_for(self, slot: str, outfit: str) -> list[str]:
        """Slotning shu asosiy kiyimdagi look'lari (pack tartibida)."""
        info = self.slots.get(slot)
        if info is None:
            return []
        return [lk for lk in info.variants if lk in self.looks and self.looks[lk].outfit == outfit]

    def expression_names(self, tag: str) -> list[str]:
        """AI tegi → kadr nomlari (birinchi mavjudi ishlatiladi)."""
        mapping = self.raw.get("expression_map", {})
        return list(mapping.get(tag) or [tag])

    def expression_frame(self, look: str, tag: str) -> int | None:
        v = self.variant("expressions", look)
        if v is None:
            return None
        names = v.names
        for n in self.expression_names(tag):
            if n in names:
                return names.index(n)
        return None

    def all_strips(self) -> list[Strip]:
        seen: dict[str, Strip] = {}
        for info in self.slots.values():
            for v in info.variants.values():
                for s in v.strips:
                    seen.setdefault(s.file, s)
        return list(seen.values())

    def max_frame_size(self) -> tuple[int, int]:
        strips = self.all_strips()
        return max(s.frame_width for s in strips), max(s.frame_height for s in strips)

    def max_below_foot(self) -> int:
        """Oyoq chizig'idan pastdagi eng katta joy (lenta pikselida)."""
        return max(s.frame_height - s.foot_y for s in self.all_strips())

    def max_above_foot(self) -> int:
        return max(s.foot_y for s in self.all_strips())


def load_pack(root: Path) -> PackMeta:
    try:
        raw = json.loads((root / "pack.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PackError(f"pack.json o'qilmadi: {root}") from exc
    version = raw.get("version")
    try:
        if version == 4:
            return _load_v4(root, raw)
        if version == 3:
            return _load_v3(root, raw)
    except (KeyError, TypeError, ValueError) as exc:
        raise PackError(f"pack.json noto'g'ri: {exc}") from exc
    raise PackError(f"to'plam versiyasi {version}, kerak: {SUPPORTED_VERSIONS}")


def _strip(d: Mapping[str, Any], rows: tuple[str, ...] = ("base",)) -> Strip:
    return Strip(
        file=str(d["file"]),
        frames=int(d["frames"]),
        frame_width=int(d["frame_width"]),
        frame_height=int(d["frame_height"]),
        foot_y=int(d["foot_y"]),
        names=tuple(d.get("names", ())),
        rows=rows,
    )


def _common(name: str, s: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "fps": float(s.get("fps", 0)),
        "loop": bool(s.get("loop", False)),
        "kind": str(s.get("kind", "state")),
        "reverse": bool(s.get("reverse", False)),
        "faces_right": s.get("faces") == "right",
        "static": bool(s.get("static", False)),
        "pose": str(s.get("pose", "")),
        "sit": bool(s.get("sit", False)),
        "fallback": str(s.get("fallback", "")),
        "time": tuple(s.get("time", ())),
        "blink": _blink(s.get("blink")),
        "fps_scale": float(s.get("fps_scale", 1.0)),
    }


def _blink(d: Mapping[str, Any] | None) -> Blink | None:
    if not d:
        return None
    lo, hi = (float(x) for x in d.get("every_s", (3, 6)))
    return Blink(
        frames=tuple(int(x) for x in d["frames"]),
        rest=tuple(int(x) for x in d["rest"]),
        every_s=(lo, hi),
    )


def _load_v4(root: Path, raw: Mapping[str, Any]) -> PackMeta:
    looks = {
        name: LookInfo(
            outfit=str(d["outfit"]),
            hood=bool(d.get("hood", False)),
            glasses=bool(d.get("glasses", False)),
            phones=str(d.get("phones", "none")),
        )
        for name, d in raw["looks"].items()
    }
    rslots: Mapping[str, Any] = raw["slots"]

    def variants_of(s: Mapping[str, Any]) -> dict[str, Variant]:
        out: dict[str, Variant] = {}
        for look, d in s.get("variants", {}).items():
            sheets = d.get("sheets", [d])
            fps, speed, wf = d.get("fps"), d.get("speed"), d.get("walk_frame")
            out[look] = Variant(
                tuple(_strip(x) for x in sheets),
                fps=float(fps) if fps else None,
                speed=float(speed) if speed else None,
                walk_frame=int(wf) if wf is not None else None,
            )
        return out

    slots: dict[str, SlotInfo] = {}
    for name, s in rslots.items():
        source = s.get("source", name)
        variants = variants_of(rslots[source])
        hold = int(s["frame"]) if "frame" in s else None
        slots[name] = SlotInfo(variants=variants, sheet=source, hold=hold, **_common(name, s))
    for name, info in slots.items():
        if not info.variants:
            raise PackError(f"slotda variant yo'q: {name}")
    idle = next(iter(slots["idle"].variants.values())).strips[0]
    standing = float(raw.get("standing_height", 330))
    return PackMeta(
        root=root,
        name=str(raw.get("name", root.name)),
        version=4,
        outfits=tuple(raw["wardrobe"]["base_outfits"]),
        layers=("base",),
        looks=looks,
        slots=slots,
        raw=raw,
        px_scale=float(raw.get("height", 165)) / standing,
        ref_width=idle.frame_width * 0.5,
    )


def _load_v3(root: Path, raw: Mapping[str, Any]) -> PackMeta:
    fw, fh, fy = int(raw["frame_width"]), int(raw["frame_height"]), int(raw["foot_y"])
    folders = tuple(raw["outfits"])
    layers = tuple(raw["layers"])
    hood_map: Mapping[str, str] = raw.get("wardrobe", {}).get("hood", {}).get("map", {})
    under = {hooded: base for base, hooded in hood_map.items()}
    looks = {f: LookInfo(outfit=under.get(f, f), hood=f in under) for f in folders}
    slots: dict[str, SlotInfo] = {}
    for name, s in raw["slots"].items():
        sheet = s.get("sheet", name)
        strip = {
            "frames": int(s["frames"]),
            "frame_width": int(s.get("frame_width", fw)),
            "frame_height": int(s.get("frame_height", fh)),
            "foot_y": int(s.get("foot_y", fy)),
            "names": s.get("names", ()),
        }
        variants = {
            f: Variant((_strip({**strip, "file": f"{f}/{sheet}.png"}, layers),)) for f in folders
        }
        common = _common(name, s)
        common["kind"] = s.get("kind", "state")
        slots[name] = SlotInfo(
            variants=variants,
            sheet=sheet,
            outfits=tuple(s.get("outfits", ())),
            require=tuple(s.get("require", ())),
            forbid=tuple(s.get("forbid", ())),
            prefer=dict(s.get("prefer", {})),
            **common,
        )
    return PackMeta(
        root=root,
        name=str(raw.get("name", root.name)),
        version=3,
        outfits=folders,
        layers=layers,
        looks=looks,
        slots=slots,
        raw=raw,
        px_scale=float(raw.get("height", 150)) / max(fy, 1),
        ref_width=fw * 0.44,
    )
