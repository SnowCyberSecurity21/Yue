"""Sozlamalar: `%APPDATA%\\Yue\\config.json`.

Faylda faqat sozlamalar va DPAPI bilan himoyalangan kalitlar bo'ladi (3-bosqich).
Yozish atomar: vaqtinchalik fayl → `os.replace`.
`ai.manba` — AI manbasi: "online" (faqat bulut API'lar) yoki "offline" (faqat Ollama).
Sxema 1-versiyadan boshlanadi (Nora sozlamalari ko'chirilmaydi, migratsiya yo'q).
"""

from __future__ import annotations

import contextlib
import copy
import json
import logging
import os
from pathlib import Path
from typing import Any

from yue import paths

log = logging.getLogger(__name__)

DEFAULTS: dict[str, Any] = {
    "version": 1,
    "pet": {
        "size": 1.0,  # 0.6 – 2.0
        "walk_on_windows": True,
        "sleep_after_min": 10,  # foydalanuvchi shuncha daqiqa harakatsiz bo'lsa uxlaydi
        "hide_fullscreen": True,
        "walk_speed": 50.0,  # `speed` siz (eski) yurish lentalari: mantiqiy px/s, o'lcham 1.0 da
        "walk_tempo": 1.0,  # 0.7 – 1.3: yurish fps i va tezligi birga (YUE_DEBUG → Sinov)
        "humor": "medium",  # hazil darajasi: low / medium / high — promptdagi [Holat] ga
        "hotkey": "Ctrl+Alt+Y",  # ko'rsatish/yashirish tugmasi (Sozlamalar → Umumiy)
    },
    "ai": {
        "manba": "online",  # online — faqat bulut (Claude, Gemini, OpenRouter); offline — Ollama
        "primary": "claude",  # asosiy provayder: claude / gemini / openrouter
        "mode": "smart",  # suhbat: smart — Sonnet (yoki Gemini 3.8) birinchi; fast — Haiku birinchi
        "openrouter_model": "meta-llama/llama-3.3-70b-instruct",  # kalit — `secrets.openrouter_key`
        "local_model": "",  # Offline: Ollama modeli (`/api/tags` dan tanlanadi)
    },
    "voice": {
        "enabled": True,  # ovoz (ElevenLabs); kalit — `secrets.elevenlabs_key`
        "volume": 80,  # 0 – 100
        "voice_id": "",  # ElevenLabs ovozi (foydalanuvchi tanlaydi)
        "model": "eleven_v4",  # eleven_v4 (standart) / eleven_v4_turbo (tez)
        "read_ai": True,  # AI javoblarini ham ovozda o'qish
        "daily_chars": 3000,  # kunlik chegara (harf ≈ kredit); 0 — cheklovsiz
        "hotkey": "Ctrl+Alt+Shift+U",  # jim qilish tugmasi (Sozlamalar → Ovoz)
    },
    "wardrobe": {
        "mode": "auto",  # auto / manual
        "outfit": None,  # tee / hoodie_black / hoodie_silver
        "glasses": None,  # True / False
        "phones": None,  # head / neck / none
        "hood": None,  # True / False
    },
}


def _merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


class Config:
    def __init__(self, data: dict[str, Any] | None = None, path: Path | None = None) -> None:
        self.data = _merge(DEFAULTS, dict(data or {}))
        self.path = path

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        path = path or paths.config_path()
        data: dict[str, Any] = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("config.json obyekt emas")
            except (OSError, ValueError):
                log.warning("config.json o'qilmadi — standart sozlamalar ishlatiladi")
                backup = path.with_suffix(".json.bad")
                with contextlib.suppress(OSError):
                    os.replace(path, backup)
                data = {}
        return cls(data, path)

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, dotted: str, value: Any) -> None:
        parts = dotted.split(".")
        node = self.data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
