"""Gemini — REST (`httpx`), `streamGenerateContent?alt=sse`, kalit `x-goog-api-key` sarlavhasida.

429 javobidagi `google.rpc.RetryInfo.retryDelay` va `google.rpc.QuotaFailure` o'zimiz o'qiladi:
kunlik kvota (`quotaId` ichida "PerDay") — Tinch okeani yarim tunigacha cooldown.

`private` — foydalanuvchi "Gemini kalitim pullik" belgisini qo'ygan bo'lsa True. Bepul tarifda
Google so'rovlarni o'qitish uchun ishlatishi mumkin, shuning uchun u holda sog'liq va shaxsiy
faktlar yuborilmaydi (bu `yue.ai.prompt` da hal qilinadi).
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import httpx

from yue.ai.providers.base import (
    ChatMessage,
    ProviderError,
    SystemBlock,
    Usage,
    target_key,
)

log = logging.getLogger(__name__)

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
MODELS = ("gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite")
MODELS_CACHE_TTL = 24 * 3600
BLOCK_FINISH = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION", "IMAGE_SAFETY"}


def _parse_delay(value: Any) -> float | None:
    """ "14s" / "1.5s" / {"seconds": 14} → soniya."""
    if isinstance(value, dict):
        try:
            return float(value.get("seconds", 0)) + float(value.get("nanos", 0)) / 1e9
        except (TypeError, ValueError):
            return None
    if isinstance(value, str):
        m = re.fullmatch(r"\s*([\d.]+)\s*s\s*", value)
        if m:
            return float(m.group(1))
    return None


def classify_error(status: int, body: bytes | str) -> ProviderError:
    """Gemini HTTP xatosini router turiga o'tkazish."""
    try:
        data = json.loads(body) if body else {}
    except (ValueError, TypeError):
        data = {}
    if isinstance(data, list) and data:
        data = data[0]
    err = data.get("error", {}) if isinstance(data, dict) else {}
    details = err.get("details", []) if isinstance(err, dict) else []
    reasons = {d.get("reason") for d in details if isinstance(d, dict)}

    if status == 429:
        retry: float | None = None
        daily = False
        for d in details:
            if not isinstance(d, dict):
                continue
            kind = str(d.get("@type", ""))
            if kind.endswith("google.rpc.RetryInfo"):
                retry = _parse_delay(d.get("retryDelay"))
            elif kind.endswith("google.rpc.QuotaFailure"):
                for v in d.get("violations", []) or []:
                    quota_id = str(v.get("quotaId", "")) + str(v.get("quotaMetric", ""))
                    if "PerDay" in quota_id or "per_day" in quota_id.lower():
                        daily = True
        if daily:
            return ProviderError("quota_daily", status=429, retry_after=retry, detail="PerDay")
        return ProviderError("rate_limit", status=429, retry_after=retry)
    if status in (401, 403) or "API_KEY_INVALID" in reasons or "API_KEY_SERVICE_BLOCKED" in reasons:
        return ProviderError("auth", status=status)
    if status in (400, 404, 413):
        return ProviderError("bad_request", status=status)
    if status >= 500 or status == 408:
        return ProviderError("transient", status=status)
    return ProviderError("bad_request", status=status)


class GeminiProvider:
    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str = MODELS[0],
        paid: bool = False,
        thinking_level: str | None = "low",
        client: httpx.Client | None = None,
        base_url: str = BASE_URL,
    ) -> None:
        self.model = model
        self.private = bool(paid)
        self.thinking_level = thinking_level
        self.last_usage: Usage | None = None
        self._key = api_key
        self._base = base_url.rstrip("/")
        self._client = client or httpx.Client(http2=False, follow_redirects=False)

    @property
    def key(self) -> str:
        return target_key(self.name, self.model)

    def _body(
        self, system: Sequence[SystemBlock], messages: Sequence[ChatMessage], max_tokens: int
    ):
        body: dict[str, Any] = {
            "contents": [
                {"role": "model" if m.role == "assistant" else "user", "parts": [{"text": m.text}]}
                for m in messages
            ],
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        sys_text = "\n\n".join(b.text for b in system if b.text)
        if sys_text:
            body["systemInstruction"] = {"parts": [{"text": sys_text}]}
        if self.thinking_level:
            body["generationConfig"]["thinkingConfig"] = {"thinkingLevel": self.thinking_level}
        return body

    def stream(
        self,
        system: Sequence[SystemBlock],
        messages: Sequence[ChatMessage],
        max_tokens: int,
        timeout: float,
    ) -> Iterator[str]:
        try:
            yield from self._stream_once(system, messages, max_tokens, timeout)
        except ProviderError as exc:
            # thinkingConfig bu modelda qabul qilinmasa — bir marta usiz qayta urinish
            if exc.kind == "bad_request" and exc.status == 400 and self.thinking_level:
                log.info("gemini: thinkingConfig qabul qilinmadi, usiz urinish (%s)", self.model)
                self.thinking_level = None
                yield from self._stream_once(system, messages, max_tokens, timeout)
            else:
                raise

    def _stream_once(self, system, messages, max_tokens, timeout) -> Iterator[str]:
        self.last_usage = None
        url = f"{self._base}/models/{self.model}:streamGenerateContent"
        headers = {"x-goog-api-key": self._key, "Content-Type": "application/json"}
        to = httpx.Timeout(timeout, connect=min(8.0, timeout))
        got_text = False
        blocked = False
        try:
            with self._client.stream(
                "POST",
                url,
                params={"alt": "sse"},
                headers=headers,
                json=self._body(system, messages, max_tokens),
                timeout=to,
            ) as resp:
                if resp.status_code != 200:
                    raise classify_error(resp.status_code, resp.read())
                for line in resp.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if not payload:
                        continue
                    try:
                        chunk = json.loads(payload)
                    except ValueError:
                        continue
                    if chunk.get("error"):
                        code = int(chunk["error"].get("code", 500) or 500)
                        raise classify_error(code, json.dumps(chunk))
                    if chunk.get("promptFeedback", {}).get("blockReason"):
                        blocked = True
                    for cand in chunk.get("candidates", []) or []:
                        for part in (cand.get("content") or {}).get("parts", []) or []:
                            text = part.get("text")
                            if text and not part.get("thought"):
                                got_text = True
                                yield text
                        if cand.get("finishReason") in BLOCK_FINISH:
                            blocked = True
                    meta = chunk.get("usageMetadata")
                    if meta:
                        self.last_usage = Usage(
                            input_tokens=int(meta.get("promptTokenCount", 0) or 0),
                            output_tokens=int(meta.get("candidatesTokenCount", 0) or 0)
                            + int(meta.get("thoughtsTokenCount", 0) or 0),
                            cache_read_tokens=int(meta.get("cachedContentTokenCount", 0) or 0),
                        )
        except httpx.TimeoutException:
            raise ProviderError("transient", detail="timeout") from None
        except httpx.TransportError:
            raise ProviderError("network") from None
        if blocked and not got_text:
            raise ProviderError("safety")
        if not got_text:
            raise ProviderError("empty")

    # --- mavjud modellar -----------------------------------------------------------------

    def list_models(self, timeout: float = 10.0) -> set[str]:
        """`models.list` — kalit bilan foydalanish mumkin bo'lgan modellar nomlari."""
        names: set[str] = set()
        page: str | None = None
        for _ in range(10):
            params: dict[str, Any] = {"pageSize": 1000}
            if page:
                params["pageToken"] = page
            try:
                r = self._client.get(
                    f"{self._base}/models",
                    params=params,
                    headers={"x-goog-api-key": self._key},
                    timeout=timeout,
                )
            except httpx.TimeoutException:
                raise ProviderError("transient", detail="timeout") from None
            except httpx.TransportError:
                raise ProviderError("network") from None
            if r.status_code != 200:
                raise classify_error(r.status_code, r.content)
            data = r.json()
            for m in data.get("models", []):
                name = str(m.get("name", ""))
                names.add(name.removeprefix("models/"))
            page = data.get("nextPageToken")
            if not page:
                break
        return names


def available_models(
    provider: GeminiProvider, cache_file: Path, now: float | None = None
) -> set[str] | None:
    """24 soatlik keshdan yoki `models.list` dan mavjud modellar. Aniqlab bo'lmasa — None."""
    now = time.time() if now is None else now
    try:
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        if now - float(cached.get("time", 0)) < MODELS_CACHE_TTL:
            return set(cached.get("models", []))
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    try:
        names = provider.list_models()
    except ProviderError:
        return None
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps({"time": now, "models": sorted(names)}), encoding="utf-8")
    except OSError:
        pass
    return names
