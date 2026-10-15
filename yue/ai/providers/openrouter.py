"""OpenRouter — OpenAI uslubidagi `/chat/completions` (`httpx`, SSE stream).

- Manzil: `https://openrouter.ai/api/v1`, kalit `Authorization: Bearer <KEY>` sarlavhasida.
- `provider.data_collection = "deny"` — so'rov faqat ma'lumotni saqlamaydigan va o'qitishga
  ishlatmaydigan provayderlarga yo'naltiriladi. Shuning uchun `private=True` (xotira beriladi).
- SSE: `:` bilan boshlanadigan qatorlar — keep-alive izohlari, `data: [DONE]` — oxiri.
  200 dan keyingi xato `error` obyekti yoki `finish_reason: "error"` bilan keladi.
- Xatolar: 401/403 → `auth`, 402 → `auth` (billing), 429 → `rate_limit`, 400/404/413/422 →
  `bad_request` (404 — model yoki mos provayder yo'q: router maqsadni o'chiradi), 408/5xx →
  `transient`. Xarajat — javobning oxirgi bo'lagidagi `usage.cost` (USD).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator, Sequence
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

BASE_URL = "https://openrouter.ai/api/v1"
MODELS = ("meta-llama/llama-3.3-70b-instruct", "mistralai/mistral-large-2407")
DEFAULT_MODEL = MODELS[0]
APP_TITLE = "Yue"


def _retry_after(headers: httpx.Headers) -> float | None:
    try:
        value = headers.get("retry-after")
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def classify_error(status: int, retry_after: float | None = None) -> ProviderError:
    """OpenRouter HTTP (yoki stream ichidagi `error.code`) xatosini router turiga o'tkazish."""
    if status == 402:
        return ProviderError("auth", status=402, detail="billing")
    if status in (401, 403):
        return ProviderError("auth", status=status)
    if status == 429:
        return ProviderError("rate_limit", status=429, retry_after=retry_after)
    if status in (400, 404, 413, 422):
        return ProviderError("bad_request", status=status)
    if status >= 500 or status == 408:
        return ProviderError("transient", status=status)
    return ProviderError("bad_request", status=status)


class OpenRouterProvider:
    name = "openrouter"

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        client: httpx.Client | None = None,
        base_url: str = BASE_URL,
    ) -> None:
        self.model = model or DEFAULT_MODEL
        self.private = True  # data_collection=deny — o'qitishga ishlatilmaydi
        self.last_usage: Usage | None = None
        self._key = api_key
        self._base = base_url.rstrip("/")
        self._client = client or httpx.Client(follow_redirects=False)

    @property
    def key(self) -> str:
        return target_key(self.name, self.model)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
            "X-Title": APP_TITLE,
        }

    def _body(
        self, system: Sequence[SystemBlock], messages: Sequence[ChatMessage], max_tokens: int
    ) -> dict[str, Any]:
        msgs: list[dict[str, str]] = []
        sys_text = "\n\n".join(b.text for b in system if b.text)
        if sys_text:
            msgs.append({"role": "system", "content": sys_text})
        msgs += [{"role": m.role, "content": m.text} for m in messages]
        return {
            "model": self.model,
            "messages": msgs,
            "stream": True,
            "max_tokens": max_tokens,
            "provider": {"data_collection": "deny"},
        }

    def stream(
        self,
        system: Sequence[SystemBlock],
        messages: Sequence[ChatMessage],
        max_tokens: int,
        timeout: float,
    ) -> Iterator[str]:
        self.last_usage = None
        got_text = False
        to = httpx.Timeout(timeout, connect=min(8.0, timeout))
        try:
            with self._client.stream(
                "POST",
                f"{self._base}/chat/completions",
                headers=self._headers(),
                json=self._body(system, messages, max_tokens),
                timeout=to,
            ) as resp:
                if resp.status_code != 200:
                    resp.read()
                    raise classify_error(resp.status_code, _retry_after(resp.headers))
                for line in resp.iter_lines():
                    if not line.startswith("data:"):
                        continue  # bo'sh qator yoki ": OPENROUTER PROCESSING" izohi
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                    except ValueError:
                        continue
                    error = chunk.get("error")
                    if isinstance(error, dict):
                        try:
                            code = int(error.get("code") or 0)
                        except (TypeError, ValueError):
                            code = 0
                        raise classify_error(code) if code else ProviderError("transient")
                    for choice in chunk.get("choices") or ():
                        text = (choice.get("delta") or {}).get("content") or ""
                        if text:
                            got_text = True
                            yield text
                        reason = choice.get("finish_reason")
                        if reason == "error":
                            raise ProviderError("transient", detail="stream")
                        if reason == "content_filter" and not got_text:
                            raise ProviderError("safety", detail="filter")
                    usage = chunk.get("usage")
                    if isinstance(usage, dict):
                        cost = usage.get("cost")
                        self.last_usage = Usage(
                            input_tokens=int(usage.get("prompt_tokens", 0) or 0),
                            output_tokens=int(usage.get("completion_tokens", 0) or 0),
                            cost=float(cost) if isinstance(cost, int | float) else None,
                        )
        except httpx.TimeoutException:
            raise ProviderError("transient", detail="timeout") from None
        except httpx.TransportError:
            raise ProviderError("network") from None
        if not got_text:
            raise ProviderError("empty")
