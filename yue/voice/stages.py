"""Tayyor iboralarni bosqichma-bosqich oldindan ovozlashtirish (`persona/ovoz_bosqich.json`).

- 1, 2 — ro'yxatdagi bo'limlar; "*" — qolgan hamma kalitlar.
- O'zgaruvchili gaplar ({task}, {count}, {hours}, {percent}…) yasalmaydi — ular jonli o'qiladi.
- {ism} li gaplar joriy ism bilan yasaladi (ism bo'sh bo'lsa — ismsiz shakli yoki umuman yo'q).
- Keshda bori o'tkazib yuboriladi: to'xtatilgan tayyorlash keyin shu joydan davom etadi.
"""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from yue import paths
from yue.lines import NAME, fill_name
from yue.voice.cache import VoiceCache, cache_key
from yue.voice.eleven import VoiceError
from yue.voice.text import tts_text

REST = "*"
_VARIABLE = re.compile(r"\{(?!ism\})[^}]*\}")


@dataclass(frozen=True)
class Item:
    key: str  # kesh kaliti
    tts: str  # ovozga yuboriladigan matn
    named: bool  # {ism} bilan yasalgan


@cache
def _read(path: Path) -> dict[int, tuple[str, ...]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {int(k): tuple(v) for k, v in data.items() if not k.startswith("_")}


def load_stages(path: Path | None = None) -> dict[int, tuple[str, ...]]:
    return _read(path or paths.PERSONA_DIR / "ovoz_bosqich.json")


def is_variable(text: str) -> bool:
    return bool(_VARIABLE.search(text))


def stage_keys(data: Mapping[str, Any], stages: Mapping[int, tuple[str, ...]]) -> dict[str, int]:
    """iboralar.json dagi har ro'yxatli kalit → bosqich (ro'yxatda yo'qlari — "*")."""
    rest = next((n for n, keys in stages.items() if REST in keys), max(stages))
    named = {k: n for n, keys in stages.items() for k in keys if k != REST}
    out = {}
    for key, node in data.items():
        if key.startswith("_") or not isinstance(node, dict | list):
            continue
        out[key] = named.get(key, rest)
    return out


def _texts(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for k, v in node.items():
            if not str(k).startswith("_"):
                yield from _texts(v)
    elif isinstance(node, list):
        for e in node:
            if isinstance(e, list) and len(e) >= 2 and isinstance(e[1], str):
                yield e[1]


def stage_texts(data: Mapping[str, Any], stage: int, name: str, stages=None) -> list[str]:
    """Bosqichdagi gaplar (pufakda qanday ko'rinsa, shunday; takrorsiz)."""
    keys = stage_keys(data, stages or load_stages())
    out: dict[str, None] = {}
    for key, n in keys.items():
        if n != stage:
            continue
        for text in _texts(data[key]):
            if is_variable(text):
                continue
            filled = fill_name(text, name)
            if filled:
                out[filled] = None
    return list(out)


def plan(
    data: Mapping[str, Any],
    stage: int,
    name: str,
    model: str,
    settings: dict[str, float],
    cache_: VoiceCache,
    stages=None,
) -> tuple[list[Item], int]:
    """Keshda yo'q gaplar va ularning harflari soni (≈ kredit)."""
    items: dict[str, Item] = {}
    raw = {fill_name(t, name): NAME in t for t in _texts(data)}
    for text in stage_texts(data, stage, name, stages):
        tts = tts_text(text)
        if not tts:
            continue
        key = cache_key(model, settings, tts)
        if key not in items and not cache_.has(key):
            items[key] = Item(key, tts, bool(raw.get(text)))
    todo = list(items.values())
    return todo, sum(len(i.tts) for i in todo)


def run(
    items: list[Item],
    synth: Callable[[str], bytes],
    cache_: VoiceCache,
    stage: int,
    name: str,
    stop: threading.Event,
    progress: Callable[[int, int], None],
) -> str:
    """Fon oqimida: ketma-ket yasab keshga yozish. Natija: done / stopped / xato turi."""
    total = len(items)
    for i, item in enumerate(items):
        if stop.is_set():
            return "stopped"
        if cache_.has(item.key):
            progress(i + 1, total)
            continue
        try:
            audio = synth(item.tts)
        except VoiceError as exc:
            return exc.kind
        meta: dict[str, Any] = {"bosqich": stage, "harf": len(item.tts)}
        if item.named:
            meta["ism"] = name
        cache_.put(item.key, audio, meta)
        progress(i + 1, total)
    return "done"
