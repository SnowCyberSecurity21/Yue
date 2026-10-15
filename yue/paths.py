"""Fayl yo'llari: dastur resurslari (RES) va foydalanuvchi ma'lumotlari (DATA).

- RES: persona, rasmlar — manba versiyada loyiha papkasi, PyInstaller'da `_MEIPASS`.
- DATA: `%APPDATA%\\Yue` (`yue.db`, `config.json`, `logs\\`).
  Testlar va ishlab chiqish uchun `YUE_DATA` muhit o'zgaruvchisi bilan almashtiriladi.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))

if FROZEN:
    RES = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
else:
    RES = Path(__file__).resolve().parent.parent

# Hujjatlar (README, LICENSE, THIRD_PARTY_LICENSES.txt): o'rnatilganda exe yonida
APP_DIR = Path(sys.executable).parent if FROZEN else RES
PERSONA_DIR = RES / "persona"
PACKS_DIR = RES / "assets" / "packs"
DEFAULT_PACK = PACKS_DIR / "yue"  # Nora'dan ko'chirilgan (tools/sync_pack.py)
ICON = DEFAULT_PACK / "yue.ico"
ICON_PNG = DEFAULT_PACK / "icon.png"
_PACK_NAME = re.compile(r"^[a-z0-9_]{1,40}$")


def pack_dir() -> Path:
    """Ishlatiladigan to'plam: `YUE_PACK=<nom>` — `assets/packs/<nom>` (sinov uchun)."""
    name = os.environ.get("YUE_PACK", "").strip().lower()
    if name and _PACK_NAME.match(name) and (PACKS_DIR / name / "pack.json").is_file():
        return PACKS_DIR / name
    return DEFAULT_PACK


def data_dir() -> Path:
    """Foydalanuvchi ma'lumotlari papkasi (har chaqiruvda muhitdan o'qiladi)."""
    override = os.environ.get("YUE_DATA")
    if override:
        return Path(override)
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / "Yue"


def db_path() -> Path:
    return data_dir() / "yue.db"


def config_path() -> Path:
    return data_dir() / "config.json"


def logs_dir() -> Path:
    return data_dir() / "logs"
