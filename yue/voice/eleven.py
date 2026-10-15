"""ElevenLabs — REST (`httpx`). Kalit faqat `xi-api-key` sarlavhasida (URL va logda yo'q).

Ovoz: `POST /v1/text-to-speech/{voice_id}?output_format=mp3_44100_128` (rasmiy hujjatdagi "Create
speech"; Eleven v4 shu endpoint'da ishlaydi). Javob — tayyor mp3.
Hisob: `GET /v1/user/subscription` (ishlatilgan va jami harflar), `GET /v1/voices`.

Xatolar (`VoiceError.kind`): auth — kalit noto'g'ri (401); perm — kalitda ruxsat yetishmaydi
(cheklangan kalit ham 401 qaytaradi: `detail.status`/`code` = "missing_permissions", hujjatda
403 "insufficient_permissions"); credits — kredit tugagan (402 yoki "quota_exceeded"); rate — 429
(bir necha marta kutib qayta uriniladi); network; bad — boshqasi (noto'g'ri voice_id ham — so'rov
umuman yuborilmaydi).
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

import httpx

log = logging.getLogger(__name__)

BASE_URL = "https://api.elevenlabs.io"
MODEL_STANDARD = "eleven_v4"
MODEL_FAST = "eleven_v4_turbo"  # real vaqt uchun (o'zbekcha va klonlangan ovoz qo'llanadi)
MODELS = (MODEL_STANDARD, MODEL_FAST)
LANGUAGE = "uz"
OUTPUT_FORMAT = "mp3_44100_128"
VOICE_SETTINGS: dict[str, float] = {"stability": 0.5, "similarity_boost": 0.75, "speed": 1.0}
RETRIES_429 = 3
TIMEOUT_S = 30.0
CREDIT_STATUSES = {
    "quota_exceeded", "insufficient_credits", "payment_required", "credits_exhausted",
}  # fmt: skip
PERM_STATUSES = {"missing_permissions", "insufficient_permissions"}
_VOICE_ID = re.compile(r"[A-Za-z0-9]{16,32}")  # ElevenLabs voice ID — odatda 20 ta harf/raqam
_PERM_NAME = re.compile(r"permissions?\s+['\"]?([a-z][a-z0-9_]{2,40})\b")


def valid_voice_id(value: str) -> bool:
    return bool(_VOICE_ID.fullmatch(value or ""))


def looks_like_key(value: str) -> bool:
    """API kalitga o'xshaydimi (Ovoz ID maydoniga adashib yozilgan)."""
    v = (value or "").strip()
    return v.lower().startswith(("sk_", "sk-", "xi-")) or len(v) > 32


class VoiceError(Exception):
    def __init__(self, kind: str, status: int | None = None, detail: str = "") -> None:
        super().__init__(kind)
        self.kind = kind
        self.status = status
        self.detail = detail  # perm: yetishmayotgan ruxsat nomi (masalan, user_read)


def api_settings(settings: dict[str, float] | None = None) -> dict[str, float]:
    """So'rovdagi voice_settings. Eleven v4 da tezlik slayderi yo'q: standart 1.0 yuborilmaydi
    (API standarti shu), boshqa qiymat bo'lsa yuboriladi."""
    out = dict(settings or VOICE_SETTINGS)
    if out.get("speed") == 1.0:
        out.pop("speed")
    return out


def _detail(body: bytes) -> tuple[set[str], str]:
    """Javobdagi ({status, code}, message) — kichik harflarda."""
    try:
        data = json.loads(body) if body else {}
    except (ValueError, TypeError):
        return set(), ""
    detail = data.get("detail") if isinstance(data, dict) else None
    if isinstance(detail, dict):
        codes = {str(detail.get(k) or "").lower() for k in ("status", "code")} - {""}
        return codes, str(detail.get("message") or "").lower()
    if isinstance(detail, str):
        return set(), detail.lower()
    return set(), ""


def classify(status: int, body: bytes) -> VoiceError:
    codes, message = _detail(body)
    if status == 402 or codes & CREDIT_STATUSES:
        return VoiceError("credits", status)
    if status in (401, 403) and (
        codes & PERM_STATUSES or any("permission" in c for c in codes) or "permission" in message
    ):
        m = _PERM_NAME.search(message)
        return VoiceError("perm", status, m.group(1) if m else "")
    if status == 401:
        return VoiceError("auth", status)
    if status == 429:
        return VoiceError("rate", status)
    return VoiceError("bad", status)


def _retry_after(r: httpx.Response, attempt: int) -> float:
    try:
        return min(10.0, max(0.5, float(r.headers.get("retry-after", ""))))
    except ValueError:
        return min(8.0, 1.0 * 2**attempt)


class ElevenLabs:
    def __init__(
        self,
        key: str,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._key = key
        self._client = client or httpx.Client(follow_redirects=False)
        self._sleep = sleep

    def __repr__(self) -> str:  # kalit hech qachon chiqmasin
        return "ElevenLabs()"

    def _headers(self, accept: str = "application/json") -> dict[str, str]:
        return {"xi-api-key": self._key, "accept": accept}

    def _request(self, method: str, path: str, **kw: Any) -> httpx.Response:
        for attempt in range(RETRIES_429 + 1):
            try:
                r = self._client.request(method, BASE_URL + path, timeout=TIMEOUT_S, **kw)
            except httpx.TimeoutException:
                raise VoiceError("network") from None
            except httpx.HTTPError:
                raise VoiceError("network") from None
            if r.status_code == 429 and attempt < RETRIES_429:
                self._sleep(_retry_after(r, attempt))
                continue
            if r.status_code >= 400:
                raise classify(r.status_code, r.content)
            return r
        raise VoiceError("rate", 429)  # pragma: no cover — sikl yuqorida tugaydi

    def synth(self, voice_id: str, text: str, model: str = MODEL_STANDARD) -> bytes:
        if not valid_voice_id(voice_id):  # kalit yoki boshqa narsa URL'ga tushmasin
            raise VoiceError("bad")
        body = {
            "text": text,
            "model_id": model,
            "language_code": LANGUAGE,
            "voice_settings": api_settings(),
        }
        r = self._request(
            "POST",
            f"/v1/text-to-speech/{quote(voice_id, safe='')}",
            params={"output_format": OUTPUT_FORMAT},
            headers=self._headers("audio/mpeg"),
            json=body,
        )
        if not r.content:
            raise VoiceError("bad", r.status_code)
        return r.content

    def credits(self) -> tuple[int, int]:
        """(ishlatilgan, jami) harf — joriy oy."""
        data = self._request("GET", "/v1/user/subscription", headers=self._headers()).json()
        return int(data.get("character_count", 0)), int(data.get("character_limit", 0))

    def voices(self) -> list[tuple[str, str]]:
        data = self._request("GET", "/v1/voices", headers=self._headers()).json()
        return [
            (str(v.get("voice_id", "")), str(v.get("name", "")))
            for v in data.get("voices", [])
            if isinstance(v, dict) and v.get("voice_id")
        ]
