"""Log sozlash. Loglarda xabar matni, oyna sarlavhalari va kalitlar bo'lmaydi.

Kod log'ga matn yozmaslik qoidasiga amal qiladi; `RedactFilter` esa xato bilan tushib qolgan
kalitlarni (Anthropic, Google, OpenRouter, ElevenLabs) niqoblaydigan ikkinchi himoya qatlami.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from logging.handlers import RotatingFileHandler

from yue import paths

_SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-or-[A-Za-z0-9_\-]{8,}"),  # OpenRouter
    re.compile(r"sk_[A-Za-z0-9]{16,}"),  # ElevenLabs
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
    re.compile(
        r"(?i)(xi-api-key|x-api-key|x-goog-api-key|authorization)['\"]?\s*[:=]\s*['\"]?[^\s'\",}]+"
    ),
]


def redact(text: str) -> str:
    for pat in _SECRET_PATTERNS:
        text = pat.sub("[yashirildi]", text)
    return text


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # noqa: BLE001
            return True
        clean = redact(msg)
        if clean != msg:
            record.msg, record.args = clean, None
        if record.exc_info and record.exc_text is None:
            record.exc_text = redact(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
        return True


# Bu kutubxonalar DEBUG darajasida so'rov tanasini (xabar matnini) yozadi — ular hech qachon
# WARNING'dan pastga tushmaydi.
QUIET_LOGGERS = ("anthropic", "httpx", "httpx2", "httpcore", "httpcore2", "urllib3", "asyncio")


def debug_enabled() -> bool:
    return os.environ.get("YUE_DEBUG", "") not in ("", "0")


def setup_logging() -> None:
    level = logging.DEBUG if debug_enabled() else logging.INFO
    root = logging.getLogger()
    root.setLevel(level)
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        paths.logs_dir().mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            paths.logs_dir() / "yue.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        fh.setFormatter(fmt)
        fh.addFilter(RedactFilter())
        root.addHandler(fh)
    except OSError:
        pass
    if debug_enabled() and sys.stderr is not None:
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        sh.addFilter(RedactFilter())
        root.addHandler(sh)
