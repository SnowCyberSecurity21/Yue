"""Tayyor iboralar ovozi: `%APPDATA%\\Yue\\voice\\<voice_id>\\<sha256>.mp3` va `index.json`.

Kalit — sha256(model | sozlamalar | ovoz matni): bir xil matn, model va sozlama — bir xil fayl.
AI javoblari bu yerga yozilmaydi (ularda shaxsiy gaplar bo'lishi mumkin).
`index.json` da faqat xizmat ma'lumoti: harflar soni, bosqich va {ism} uchun ishlatilgan ism.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from yue import paths

_SAFE_ID = re.compile(r"[^A-Za-z0-9_-]")


def cache_key(model: str, settings: dict[str, float], tts: str) -> str:
    blob = f"{model}|{json.dumps(settings, sort_keys=True)}|{tts}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


class VoiceCache:
    def __init__(self, voice_id: str, root: Path | None = None) -> None:
        safe = _SAFE_ID.sub("", voice_id)[:64] or "_"
        self.dir = (root or paths.data_dir() / "voice") / safe
        self._index: dict[str, dict[str, Any]] | None = None

    def path(self, key: str) -> Path:
        return self.dir / f"{key}.mp3"

    def get(self, key: str) -> Path | None:
        p = self.path(key)
        return p if p.is_file() and p.stat().st_size > 0 else None

    def has(self, key: str) -> bool:
        return self.get(key) is not None

    @property
    def index(self) -> dict[str, dict[str, Any]]:
        if self._index is None:
            try:
                data = json.loads((self.dir / "index.json").read_text(encoding="utf-8"))
                self._index = data if isinstance(data, dict) else {}
            except (OSError, ValueError):
                self._index = {}
        return self._index

    def _save_index(self) -> None:
        blob = json.dumps(self.index, ensure_ascii=False, indent=1).encode("utf-8")
        _atomic_write(self.dir / "index.json", blob)

    def put(self, key: str, audio: bytes, meta: dict[str, Any]) -> None:
        _atomic_write(self.path(key), audio)
        self.index[key] = meta
        self._save_index()

    def forget_names(self, current: str) -> int:
        """Boshqa ism bilan yasalgan {ism} li fayllarni o'chirish (ism o'zgardi)."""
        stale = [k for k, m in self.index.items() if m.get("ism") not in (None, current)]
        for k in stale:
            with contextlib.suppress(OSError):
                self.path(k).unlink()
            self.index.pop(k, None)
        if stale:
            self._save_index()
        return len(stale)
