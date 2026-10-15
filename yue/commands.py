"""Buyruqlar ro'yxati (`persona/harakatlar.json`) va AI'siz tez tanish. Qt'ga bog'liq emas.

Yangi harakat qo'shish uchun faqat ikki fayl o'zgaradi: `harakatlar.json` (yozuv) va
`persona_uz.txt` dagi HARAKATLAR ro'yxati. Kod ro'yxatni o'zi o'qiydi.

Tez tanish: xabar kichik harfga o'tkaziladi, tinish belgilari olib tashlanadi; u `sozlar` dan
biri bilan (butun so'z sifatida) boshlansa va 4 so'zdan oshmasa — buyruq. Savol ("?") — buyruq emas.
"""

from __future__ import annotations

import json
import random
import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Literal

from yue import paths

Mode = Literal["bir_marta", "soniya", "uygonguncha", "keyingi_buyruqgacha", "maxsus"]
MODES: tuple[str, ...] = ("bir_marta", "soniya", "uygonguncha", "keyingi_buyruqgacha", "maxsus")
FAST_MAX_WORDS = 4
FAST_REPEAT_S = 15.0  # tez tanilgan buyruq: AI javobidagi shu teg shu vaqt ichida takrorlanmaydi

_APOSTROPHES = str.maketrans({c: "'" for c in "ʻʼ’‘`´"})
_NON_WORD = re.compile(r"[^\w' ]+")


@dataclass(frozen=True)
class CommandSpec:
    name: str
    mode: str
    slot: str = ""
    seconds: float = 0.0
    line: str = ""  # iboralar kaliti: "harakat.uxla", "qoshiq", "sayr.boshlash"
    words: tuple[str, ...] = ()
    no_ai: bool = False  # "aisiz": true — tayyor ibora bilan, AI'ga yuborilmaydi (hazil ayt)

    @property
    def line_key(self) -> tuple[str, str | None]:
        """`Lines.pick` uchun (kalit, bo'lim)."""
        key, _, sub = self.line.partition(".")
        return key, sub or None


def normalize(text: str) -> list[str]:
    """Kichik harf, bir xil apostrof, tinish belgilarisiz so'zlar."""
    text = text.lower().translate(_APOSTROPHES)
    return [w.strip("'") for w in _NON_WORD.sub(" ", text).split() if w.strip("'")]


class Commands:
    def __init__(self, specs: Mapping[str, CommandSpec]) -> None:
        self.specs = dict(specs)
        # Uzunroq ibora oldin: "tur uyg'on" (uygon) "tur" dan oldin tekshiriladi.
        self._words = sorted(
            ((tuple(normalize(w)), name) for name, s in self.specs.items() for w in s.words),
            key=lambda x: -len(x[0]),
        )

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> Commands:
        specs = {}
        for name, d in (data.get("harakatlar") or {}).items():
            mode = str(d.get("rejim", "bir_marta"))
            if mode not in MODES:
                raise ValueError(f"noma'lum rejim: {name}: {mode}")
            specs[name] = CommandSpec(
                name=name,
                mode=mode,
                slot=str(d.get("slot", "")),
                seconds=float(d.get("davomiylik", 0) or 0),
                line=str(d.get("ibora", "")),
                words=tuple(str(w) for w in d.get("sozlar", ())),
                no_ai=bool(d.get("aisiz", False)),
            )
        return cls(specs)

    @classmethod
    def load(cls, path: Path | None = None) -> Commands:
        return cls.from_data(_read(path or paths.PERSONA_DIR / "harakatlar.json"))

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self.specs)

    def get(self, name: str) -> CommandSpec | None:
        return self.specs.get(name)

    def recognize(self, text: str) -> str | None:
        """Qisqa buyruqni AI'siz tanish ("Uxlab ol!" → "uxla"); tanilmasa None."""
        if "?" in text:
            return None
        words = normalize(text)
        if not words or len(words) > FAST_MAX_WORDS:
            return None
        for seq, name in self._words:
            if seq and tuple(words[: len(seq)]) == seq:
                return name
        return None


@cache
def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@cache
def default_names() -> frozenset[str]:
    """AI javobidagi <harakat> tegi uchun ruxsat etilgan nomlar."""
    return frozenset(Commands.load().names)


class UniquePicker:
    """Bitta sayr ichida bir gap takrorlanmaydi; hammasi aytilgach — yana boshidan."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.used: set[str] = set()

    def reset(self) -> None:
        self.used.clear()

    def pick(self, options: list[tuple[str, str]]) -> tuple[str, str] | None:
        if not options:
            return None
        fresh = [o for o in options if o[1] not in self.used]
        if not fresh:
            self.used -= {o[1] for o in options}
            fresh = options
        choice = self.rng.choice(fresh)
        self.used.add(choice[1])
        return choice
