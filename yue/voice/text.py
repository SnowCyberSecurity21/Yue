"""Ovozga yuboriladigan matn. Pufakdagi matn o'zgarmaydi — bu faqat TTS uchun.

- `*harakat*` (masalan, "*jilmayadi*") o'qilmaydi;
- `persona/talaffuz.json` — so'z chegarasi bo'yicha, katta-kichik harf farqsiz
  ("Yue" → "Yu-e");
- raqamlar o'zbekcha so'z bilan (0–9999), soat "15:30" → "o'n besh o'ttiz", "%" → "foiz".
"""

from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path

from yue import paths

ONES = ("nol", "bir", "ikki", "uch", "to'rt", "besh", "olti", "yetti", "sakkiz", "to'qqiz")
TENS = ("", "o'n", "yigirma", "o'ttiz", "qirq", "ellik", "oltmish", "yetmish", "sakson", "to'qson")
MAX_NUMBER = 9999

_ACTION = re.compile(r"\*[^*\n]{1,120}\*")
_MARKUP = re.compile(r"[*_`#]+")
_TIME = re.compile(r"(?<![\d:])([01]?\d|2[0-3]):([0-5]\d)(?![\d:])")
_NUMBER = re.compile(r"(?<![\d.,])\d{1,4}(?![\d])")
_PERCENT = re.compile(r"\s*%")
_SPACES = re.compile(r"\s+")
# Gap oxiri: . ! ? … (bir nechtasi ham) va ortidan bo'shliq
_SENTENCE_END = re.compile(r"[.!?…]+[\"')»]*\s+")
MIN_SENTENCE = 15  # bundan qisqa bo'lak keyingi gapga qo'shiladi (ortiqcha so'rov bo'lmasin)


def number_words(n: int) -> str:
    """0–9999 → o'zbekcha so'z."""
    if not 0 <= n <= MAX_NUMBER:
        raise ValueError(n)
    if n < 10:
        return ONES[n]
    parts: list[str] = []
    thousands, n = divmod(n, 1000)
    if thousands:
        parts.append("ming" if thousands == 1 else f"{ONES[thousands]} ming")
    hundreds, n = divmod(n, 100)
    if hundreds:
        parts.append("yuz" if hundreds == 1 else f"{ONES[hundreds]} yuz")
    tens, ones = divmod(n, 10)
    if tens:
        parts.append(TENS[tens])
    if ones:
        parts.append(ONES[ones])
    return " ".join(parts)


def _time_words(m: re.Match[str]) -> str:
    hour, minute = int(m.group(1)), int(m.group(2))
    if minute == 0:
        return number_words(hour)
    if minute < 10:
        return f"{number_words(hour)} nol {number_words(minute)}"
    return f"{number_words(hour)} {number_words(minute)}"


def spell_numbers(text: str) -> str:
    text = _TIME.sub(_time_words, text)
    text = _PERCENT.sub(" foiz", text)
    return _NUMBER.sub(lambda m: number_words(int(m.group(0))), text)


@cache
def _load_lexicon(path: Path) -> tuple[tuple[re.Pattern[str], str], ...]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    rules = []
    for word, say in data.items():
        if word.startswith("_") or not isinstance(say, str) or not word.strip():
            continue
        rules.append((re.compile(rf"(?<!\w){re.escape(word)}(?!\w)", re.I), say))
    return tuple(rules)


def lexicon(path: Path | None = None) -> tuple[tuple[re.Pattern[str], str], ...]:
    return _load_lexicon(path or paths.PERSONA_DIR / "talaffuz.json")


def apply_lexicon(text: str, rules: tuple[tuple[re.Pattern[str], str], ...] | None = None) -> str:
    for pattern, say in lexicon() if rules is None else rules:
        text = pattern.sub(lambda _m, s=say: s, text)
    return text


def tts_text(text: str, rules: tuple[tuple[re.Pattern[str], str], ...] | None = None) -> str:
    """Pufak matni → ovoz matni (bo'sh bo'lishi mumkin — masalan, faqat "*harakat*")."""
    text = _ACTION.sub(" ", text)
    text = _MARKUP.sub("", text)
    text = apply_lexicon(text, rules)
    text = spell_numbers(text)
    return _SPACES.sub(" ", text).strip()


def _merge_short(parts: list[str]) -> list[str]:
    out: list[str] = []
    for p in parts:
        if out and len(out[-1]) < MIN_SENTENCE:
            out[-1] = f"{out[-1]} {p}"
        else:
            out.append(p)
    return out


def split_complete(text: str) -> tuple[list[str], int]:
    """Oqim matnidan tugagan gaplar va ular egallagan uzunlik (qolgani hali yozilmoqda).

    Qisqa gap ("Voy!") keyingisi bilan birga yuboriladi — shuning uchun oxirgi qisqa bo'lak
    hali tugamagan hisoblanadi.
    """
    parts: list[str] = []
    used = 0
    pos = 0
    pending = ""
    for m in _SENTENCE_END.finditer(text):
        chunk = text[pos : m.end()].strip()
        pos = m.end()
        pending = f"{pending} {chunk}".strip() if pending else chunk
        if len(pending) >= MIN_SENTENCE:
            parts.append(pending)
            pending = ""
            used = pos
    return parts, used


def split_sentences(text: str) -> list[str]:
    """Butun matnni gaplarga bo'lish (AI javobi oqimsiz kelganda)."""
    parts, used = split_complete(text + " ")
    tail = text[used:].strip()
    if tail:
        parts.append(tail)
    return _merge_short(parts)
