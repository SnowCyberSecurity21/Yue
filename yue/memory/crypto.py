"""Shifrlash: AES-256-GCM (ma'lumotlar) + Windows DPAPI (kalitlar).

- Birinchi ishga tushishda tasodifiy 256-bit ma'lumot kaliti yaratiladi; u DPAPI bilan himoyalanib
  `config.json → secrets.data_key` da saqlanadi (faqat shu Windows foydalanuvchisi ocha oladi).
- Har bir yozuv yangi 96-bit nonce bilan shifrlanadi. AAD = "jadval:ustun" — shifrlangan
  qiymatni boshqa ustunga ko'chirib bo'lmaydi.
- API kalitlar ham DPAPI bilan himoyalanib `secrets.<nom>` da saqlanadi.
Format: b"\\x01" + nonce(12) + shifrmatn+teg(16).
"""

from __future__ import annotations

import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from yue.config import Config
from yue.platform import Platform

VERSION = b"\x01"
NONCE_LEN = 12
KEY_LEN = 32


class CryptoError(Exception):
    """Shifrni ochib bo'lmadi (noto'g'ri kalit yoki buzilgan ma'lumot)."""


class Cipher:
    def __init__(self, key: bytes) -> None:
        if len(key) != KEY_LEN:
            raise ValueError("kalit 32 bayt bo'lishi kerak")
        self._aes = AESGCM(key)

    def encrypt(self, plaintext: str, aad: str) -> bytes:
        nonce = os.urandom(NONCE_LEN)
        return VERSION + nonce + self._aes.encrypt(nonce, plaintext.encode("utf-8"), aad.encode())

    def decrypt(self, blob: bytes, aad: str) -> str:
        if not blob or blob[:1] != VERSION or len(blob) < 1 + NONCE_LEN + 16:
            raise CryptoError("noma'lum format")
        nonce, ct = blob[1 : 1 + NONCE_LEN], blob[1 + NONCE_LEN :]
        try:
            return self._aes.decrypt(nonce, ct, aad.encode()).decode("utf-8")
        except (InvalidTag, UnicodeDecodeError) as exc:
            raise CryptoError("shifr ochilmadi") from exc


class SecretStore:
    """DPAPI bilan himoyalangan sirlar (`config.json → secrets`). Ochiq matn diskka yozilmaydi."""

    def __init__(self, cfg: Config, platform: Platform) -> None:
        self.cfg = cfg
        self.platform = platform

    def _secrets(self) -> dict[str, str]:
        node = self.cfg.data.setdefault("secrets", {})
        if not isinstance(node, dict):
            node = self.cfg.data["secrets"] = {}
        return node

    def get_bytes(self, name: str) -> bytes | None:
        value = self._secrets().get(name)
        if not value:
            return None
        try:
            return self.platform.unprotect(base64.b64decode(value))
        except (OSError, ValueError, NotImplementedError) as exc:
            raise CryptoError(f"DPAPI: '{name}' ochilmadi") from exc

    def set_bytes(self, name: str, data: bytes | None) -> None:
        secrets = self._secrets()
        if data is None:
            secrets.pop(name, None)
        else:
            secrets[name] = base64.b64encode(self.platform.protect(data)).decode("ascii")
        self.cfg.save()

    def get(self, name: str) -> str | None:
        raw = self.get_bytes(name)
        return raw.decode("utf-8") if raw is not None else None

    def set(self, name: str, value: str | None) -> None:
        self.set_bytes(name, value.strip().encode("utf-8") if value else None)

    def has(self, name: str) -> bool:
        return bool(self._secrets().get(name))


def load_or_create_data_key(secrets: SecretStore) -> tuple[bytes, bool]:
    """Ma'lumot kaliti. (kalit, yangi_yaratildimi). Ochib bo'lmasa — CryptoError."""
    key = secrets.get_bytes("data_key")
    if key is not None:
        if len(key) != KEY_LEN:
            raise CryptoError("ma'lumot kaliti noto'g'ri uzunlikda")
        return key, False
    key = AESGCM.generate_key(bit_length=256)
    secrets.set_bytes("data_key", key)
    return key, True
