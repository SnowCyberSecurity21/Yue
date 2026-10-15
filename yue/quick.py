"""AI'siz tez buyruqlar (kalit bo'lsa ham ishlaydi, AI'ga yuborilmaydi).

- "eslat: <matn>" — muddatsiz vazifa;
- "eslat <vaqt>: <matn>" — vaqt `tasks.timeparse.parse_user_time` bilan ("18:00", "ertaga 9:00",
  "1 daqiqadan keyin", "har kuni 08:00");
- "vazifalar" — ochiq vazifalar ro'yxati.

"eslat" dan keyin ikki nuqta bo'lmasa (masalan, "ertaga dori ichishni eslat") — bu buyruq emas,
xabar AI'ga ketadi. Qt'ga bog'liq emas.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Literal

from yue.tasks.timeparse import parse_user_time

QuickKind = Literal["add", "list", "bad"]
MAX_TEXT = 300
_PREFIX = re.compile(r"^\s*(eslat|эслат)\b", re.I)
_LIST = re.compile(r"^\s*/?(vazifalar|vazifalarim|вазифалар)\s*[.!?]*\s*$", re.I)


@dataclass(frozen=True)
class Quick:
    kind: QuickKind
    text: str = ""
    due: str | None = None
    repeat: str | None = None


def _split_colon(rest: str) -> int | None:
    """Vaqt va matnni ajratuvchi ikki nuqta (soatdagi "18:00" emas)."""
    for i, ch in enumerate(rest):
        if ch != ":":
            continue
        before, after = rest[i - 1 : i], rest[i + 1 : i + 2]
        if before.isdigit() and after.isdigit():
            continue
        return i
    return None


def parse(text: str, now: dt.datetime) -> Quick | None:
    """Tez buyruq bo'lsa — `Quick`, aks holda None (xabar odatdagidek AI'ga ketadi)."""
    if _LIST.match(text):
        return Quick("list")
    m = _PREFIX.match(text)
    if not m:
        return None
    rest = text[m.end() :]
    i = _split_colon(rest)
    if i is None:
        return None
    when, body = rest[:i].strip(), " ".join(rest[i + 1 :].split())[:MAX_TEXT]
    if not body:
        return Quick("bad")
    parsed = parse_user_time(when, now)
    if parsed is None:
        return Quick("bad")
    return Quick("add", body, *parsed)
