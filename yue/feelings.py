"""Yuening kayfiyati. Qoidaga asoslangan (model hal qilmaydi).

Qt'ga bog'liq emas.

Kayfiyat (`Mood`) — hodisalardan:
- 00:00–05:00 da foydalanuvchi faol — xavotirda; kechasi boshqa paytda — charchagan;
- maqtov — uyalgan (10 daqiqa, romantikasiz: maqtovga uyalib, jahl bilan yashiradi);
- muvaffaqiyat yoki bajarilgan vazifa — g'ururli (30 daqiqa).
Ustunlik: uyalgan > g'ururli > xavotirda > charchagan > xursand.
"""

from __future__ import annotations

import datetime as dt
import time
from collections.abc import Callable

from yue.commands import normalize

SHY_FOR = 10 * 60.0
PROUD_FOR = 30 * 60.0
LATE_HOURS = range(0, 5)  # 00:00–05:00: faol bo'lsa — xavotirda
NIGHT_HOURS = frozenset({22, 23, 0, 1, 2, 3, 4, 5})

DEFAULT_MOOD = "xursand"
MOODS = ("xursand", "xavotirda", "uyalgan", "g'ururli", "charchagan")
# Javobda [ifoda] tegi bo'lmasa — kayfiyatga mos ifoda (xursand — o'zgarmaydi)
MOOD_EXPRESSIONS = {
    "xavotirda": "sad",
    "uyalgan": "shy",
    "g'ururli": "smug",  # pack: smug → proud kadri
    "charchagan": "sleepy",
}

# So'z boshlari (normallashtirilgan, lotin va kirill)
PRAISE = (
    "zo'r", "aqlli", "rahmat", "barakalla", "yaxshi ko'raman", "qoyil", "ofarin", "ajoyib",
    "malades", "molodets",
    "зўр", "зор", "ақлли", "акли", "раҳмат", "рахмат", "баракалла", "яхши кўраман", "қойил",
    "офарин", "ажойиб", "молодец", "умница", "спасибо",
)  # fmt: skip
SUCCESS = (
    "uddaladim", "tugatdim", "bitirdim", "ishladi", "o'tdim", "topshirdim", "yutdim",
    "hal qildim", "tuzatdim", "tayyor bo'ldi", "qabul qilindi", "deploy qildim",
    "уддаладим", "тугатдим", "битирдим", "ишлади", "ўтдим", "топширдим", "ютдим", "ҳал қилдим",
    "получилось", "сделал", "сдал", "заработало",
)  # fmt: skip


def _phrases(words: tuple[str, ...]) -> list[tuple[str, ...]]:
    return sorted({tuple(normalize(w)) for w in words if normalize(w)}, key=len, reverse=True)


_PRAISE, _SUCCESS = _phrases(PRAISE), _phrases(SUCCESS)


# So'z boshi mos kelsa ham boshqa ma'noli so'zlar ("zo'rg'a" — "arang", "zo'rlab" — "majburan")
_NOT_PRAISE = ("zo'rg", "zo'rla", "зўрға", "зўрла")


def _has(text: str, phrases: list[tuple[str, ...]]) -> bool:
    """Matnda iboralardan biri bormi: so'zlar ketma-ket, har biri so'z boshi sifatida
    ("rahmat" → "rahmatli", "zo'r" → "zo'rsiz")."""
    words = [w for w in normalize(text) if not w.startswith(_NOT_PRAISE)]
    for ph in phrases:
        n = len(ph)
        for i in range(len(words) - n + 1):
            if all(words[i + k].startswith(ph[k]) for k in range(n)):
                return True
    return False


def is_praise(text: str) -> bool:
    return _has(text, _PRAISE)


def is_success(text: str) -> bool:
    return _has(text, _SUCCESS)


# --- kayfiyat ----------------------------------------------------------------------------------


class Mood:
    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self.clock = clock
        self.until: dict[str, float] = {}  # hodisa kayfiyati → qachongacha

    def on_user_message(self, text: str) -> None:
        now = self.clock()
        if is_praise(text):
            self.until["uyalgan"] = now + SHY_FOR
        if is_success(text):
            self.on_success()

    def on_success(self) -> None:
        self.until["g'ururli"] = self.clock() + PROUD_FOR

    def current(self, now: dt.datetime, active: bool) -> str:
        t = self.clock()
        for name in ("uyalgan", "g'ururli"):
            if self.until.get(name, 0.0) > t:
                return name
        if now.hour in LATE_HOURS and active:
            return "xavotirda"
        if now.hour in NIGHT_HOURS:
            return "charchagan"
        return DEFAULT_MOOD


def mood_expression(mood: str) -> str | None:
    return MOOD_EXPRESSIONS.get(mood)
