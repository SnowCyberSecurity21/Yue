"""Foydalanuvchi tanlagan tezkor tugma birikmasi ("Ctrl+Alt+Shift+U" kabi, Qt PortableText).

OS'ga bog'liq emas: faqat matnni tahlil qiladi; ro'yxatdan o'tkazish — `yue.platform`.
Kamida bitta Ctrl/Alt/Win bo'lishi shart (yolg'iz harf yoki Shift+harf yozishga xalaqit beradi).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_TOGGLE = "Ctrl+Alt+Y"
DEFAULT_VOICE = "Ctrl+Alt+Shift+U"
_MODS = {
    "ctrl": "ctrl", "control": "ctrl", "alt": "alt", "shift": "shift", "meta": "win", "win": "win",
}  # fmt: skip
_KEY = re.compile(r"[A-Z0-9]|F([1-9]|1[0-9]|2[0-4])")


@dataclass(frozen=True)
class Combo:
    mods: frozenset[str]  # ctrl / alt / shift / win
    key: str  # A–Z, 0–9 yoki F1–F24

    def portable(self) -> str:
        """Qt PortableText ko'rinishida (Win — "Meta")."""
        order = ("ctrl", "alt", "shift", "win")
        names = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Meta"}
        return "+".join([names[m] for m in order if m in self.mods] + [self.key])


def parse(text: str) -> Combo | None:
    """ "Ctrl+Alt+Shift+U" → Combo; ishlamaydigan birikma — None."""
    parts = [p.strip() for p in (text or "").split("+")]
    if len(parts) < 2 or not all(parts):
        return None
    *mods, key = parts
    found: set[str] = set()
    for m in mods:
        name = _MODS.get(m.lower())
        if name is None or name in found:
            return None
        found.add(name)
    key = key.upper()
    if not _KEY.fullmatch(key) or not found & {"ctrl", "alt", "win"}:
        return None
    return Combo(frozenset(found), key)
