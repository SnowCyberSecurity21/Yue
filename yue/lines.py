"""Yuening tayyor iboralari (`persona/iboralar.json`) — AI'siz aytiladigan gaplar.

Har kalit uchun oxirgi `RECENT` ta gap qayta tanlanmaydi.
`{ism}` — foydalanuvchi ismi (`user.name`). Ism bo'sh bo'lsa, "{ism}, ", "{ism}! ", ", {ism}"
qismlari olib tashlanadi va gap katta harf bilan boshlanadi; boshqa joyda turgan `{ism}` li gap
(masalan, "Ana, {ism} keldi!") ism bo'lmasa tanlanmaydi.
"""

from __future__ import annotations

import json
import random
import re
from collections import deque
from collections.abc import Callable, Mapping
from functools import cache
from pathlib import Path
from typing import Any

from yue import paths

Line = tuple[str, str]  # (ifoda, matn)
RECENT = 5
NAME = "{ism}"
# Ismsiz: ", {ism}" — bo'lak oxirida ("Rahmat, {ism}." → "Rahmat."); "{ism}, " / "{ism}! " —
# gap boshida ("{ism}, suv ichdingizmi?" → "Suv ichdingizmi?")
_NAME_TAIL = re.compile(r", \{ism\}(?=[.!?…,])")
_NAME_HEAD = re.compile(r"(^|(?<=[.!?…] ))\{ism\}[,!] (\w)")


def _node_entries(root: Mapping[str, Any], key: str, sub: str | None) -> list[Any]:
    node: Any = root.get(key)
    if isinstance(node, dict):
        node = node.get(sub) if sub else None
    return node if isinstance(node, list) else []


def _node_options(root: Mapping[str, Any], key: str, sub: str | None) -> list[Line]:
    return [(str(entry[0]), str(entry[1])) for entry in _node_entries(root, key, sub)]


def fill_name(text: str, name: str) -> str | None:
    """`{ism}` ni ism bilan to'ldirish; ism bo'sh bo'lsa — olib tashlash (iloji bo'lmasa None)."""
    if NAME not in text:
        return text
    if name:
        return text.replace(NAME, name)
    text = _NAME_TAIL.sub("", text)
    text = _NAME_HEAD.sub(lambda m: m.group(1) + m.group(2).upper(), text)
    if NAME in text:
        return None
    return text[:1].upper() + text[1:]


class Lines:
    def __init__(self, data: Mapping[str, Any], rng: random.Random | None = None) -> None:
        self.data = data
        self.rng = rng or random.Random()
        self.name_fn: Callable[[], str] = lambda: ""  # foydalanuvchi ismi (Brain ulaydi)
        self._recent: dict[str, deque[str]] = {}

    @classmethod
    def load(cls, path: Path | None = None) -> Lines:
        return cls(_read(path or paths.PERSONA_DIR / "iboralar.json"))

    def options(self, key: str, sub: str | None = None) -> list[Line]:
        """Bo'limdagi variantlar."""
        return _node_options(self.data, key, sub)

    def has(self, key: str, sub: str | None = None) -> bool:
        return bool(self.options(key, sub))

    def pick(self, key: str, sub: str | None = None, **fmt: object) -> Line:
        """Tasodifiy ibora (oxirgi 5 tasi takrorlanmaydi). `{nom}` joylari to'ldiriladi."""
        name = self.name_fn().strip()
        options = self.options(key, sub)
        if not name:  # ismsiz aytib bo'lmaydigan gaplar chiqmaydi
            options = [o for o in options if fill_name(o[1], "") is not None]
        if not options:
            return ("neutral", "...")
        recent = self._recent.setdefault(f"{key}.{sub}", deque(maxlen=RECENT))
        fresh = [o for o in options if o[1] not in recent]
        # hammasi yaqinda aytilgan bo'lsa (variant 5 tadan kam) — istalgani
        expr, text = self.rng.choice(fresh or options)
        recent.append(text)
        if fmt:
            try:
                text = text.format(**{"ism": NAME, **fmt})
            except (KeyError, IndexError, ValueError):
                pass
        return expr, fill_name(text, name) or text

    def all_texts(self) -> list[str]:
        out: list[str] = []

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                for k, v in node.items():
                    if not str(k).startswith("_"):
                        walk(v)
            elif isinstance(node, list):
                for item in node:
                    if isinstance(item, list) and len(item) == 2:
                        out.append(str(item[1]))
            elif isinstance(node, str):
                out.append(node)

        walk(self.data)
        return out


@cache
def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
