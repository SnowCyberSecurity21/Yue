"""AI manbasi (Online/Offline): holat va chatdagi kalit so'zlar.

Manba (`ai.manba`) — qaysi AI javob beradi: "online" (bulut API'lar) yoki "offline" (Ollama).

Kalit so'z AI'ga yuborilmaydi — tez tanish qatlami hal qiladi. Lotin va kirill yozuvi, katta-kichik
harf farqsiz; xabar butunligicha kalit so'z bo'lishi kerak ("offline rejim haqida gapir" — emas).
Qt'ga bog'liq emas.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from yue.config import Config

Switch = Literal["online", "offline"]
Source = Literal["online", "offline"]

_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "ғ": "g'", "д": "d", "е": "e", "ё": "yo", "ж": "j",
    "з": "z", "и": "i", "й": "y", "к": "k", "қ": "q", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ў": "o'", "ф": "f", "х": "x", "ҳ": "h",
    "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "'", "ь": "", "ы": "i", "э": "e", "ю": "yu",
    "я": "ya",
}  # fmt: skip
_TRANSLIT = str.maketrans(_CYR)
_APOSTROPHES = str.maketrans({c: "'" for c in "ʻʼ’‘`´"})

PHRASES: dict[str, Switch] = {
    # AI manbasi
    "/online": "online",
    "online": "online",
    "online rejim": "online",
    "online rejimga o't": "online",
    "onlayn": "online",
    "onlayn rejim": "online",
    "/ochiq": "online",
    "offline rejimni o'chir": "online",
    "/offline": "offline",
    "offline": "offline",
    "offline rejim": "offline",
    "offline rejimga o't": "offline",
    "oflayn": "offline",
    "oflayn rejim": "offline",
    "online rejimni o'chir": "offline",
}


def normalize(text: str) -> str:
    """Kichik harf, kirill → lotin, bir xil apostrof; tinish belgilari (boshidagi "/" dan
    tashqari) va ortiqcha bo'shliqlar olib tashlanadi."""
    text = text.strip().lower().translate(_TRANSLIT).translate(_APOSTROPHES)
    slash = text.startswith("/")
    text = re.sub(r"[^\w' ]+", " ", text)
    text = " ".join(w.strip("'") for w in text.split() if w.strip("'"))
    return ("/" + text) if slash else text


def recognize(text: str) -> Switch | None:
    return PHRASES.get(normalize(text))


# --- holat (config) ----------------------------------------------------------------------------


def source(cfg: Config) -> Source:
    return "offline" if cfg.get("ai.manba", "online") == "offline" else "online"
