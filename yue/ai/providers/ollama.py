"""Offline model — lokal Ollama (`http://127.0.0.1:11434/api/chat`), stream (NDJSON), `httpx`.

- Ma'lumot kompyuterdan chiqmaydi → `private=True` (xotira va sog'liq daftari ham beriladi).
- `options.num_ctx = 16384`; `num_predict` — javob uzunligi chegarasi.
- Xatolar: Ollama ishlamayapti (ulanish yo'q) → `network`; vaqt tugadi → `transient`;
  model o'rnatilmagan (404) → `bad_request` (router maqsadni o'chiradi); 5xx → `transient`.
"""

from __future__ import annotations

import http.client
import json
import logging
from collections.abc import Iterator, Sequence
from typing import Any
from urllib.parse import urlsplit

import httpx

from yue.ai.providers.base import (
    ChatMessage,
    ProviderError,
    SystemBlock,
    Usage,
    target_key,
)

log = logging.getLogger(__name__)

BASE_URL = "http://127.0.0.1:11434"
NUM_CTX = 16384


def _error(status: int, body: bytes | str) -> ProviderError:
    if status == 404:
        return ProviderError("bad_request", status=404, detail="model")
    if status in (400, 413, 422):
        return ProviderError("bad_request", status=status)
    if status >= 500 or status in (408, 429):
        return ProviderError("transient", status=status)
    return ProviderError("bad_request", status=status)


class OllamaProvider:
    name = "ollama"
    local = True  # router: birinchi token byudjeti cheklamaydi, o'z vaqt chegarasi

    def __init__(
        self,
        model: str,
        base_url: str = BASE_URL,
        client: httpx.Client | None = None,
        num_ctx: int = NUM_CTX,
    ) -> None:
        self.model = model
        self.private = True  # lokal: hech narsa tashqariga chiqmaydi
        self.last_usage: Usage | None = None
        self.num_ctx = num_ctx
        self._base = base_url.rstrip("/")
        self._client = client or httpx.Client(follow_redirects=False, trust_env=False)

    @property
    def key(self) -> str:
        return target_key(self.name, self.model)

    def _body(
        self, system: Sequence[SystemBlock], messages: Sequence[ChatMessage], max_tokens: int
    ) -> dict[str, Any]:
        msgs: list[dict[str, str]] = []
        sys_text = "\n\n".join(b.text for b in system if b.text)
        prompt_chars = len(sys_text) + sum(len(m.text) for m in messages)
        log.debug("Ollama prompt hajmi (taxmin): %d token", (prompt_chars + 3) // 4)
        if sys_text:
            msgs.append({"role": "system", "content": sys_text})
        msgs += [{"role": m.role, "content": m.text} for m in messages]
        return {
            "model": self.model,
            "messages": msgs,
            "stream": True,
            "options": {"num_ctx": self.num_ctx, "num_predict": max_tokens},
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
        # Model diskdan xotiraga yuklanishi sekin bo'lishi mumkin — o'qish vaqti `timeout` gacha.
        to = httpx.Timeout(timeout, connect=3.0)
        try:
            with self._client.stream(
                "POST",
                f"{self._base}/api/chat",
                json=self._body(system, messages, max_tokens),
                timeout=to,
            ) as resp:
                if resp.status_code != 200:
                    raise _error(resp.status_code, resp.read())
                for line in resp.iter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except ValueError:
                        continue
                    if chunk.get("error"):
                        raise ProviderError("transient", detail="ollama")
                    text = (chunk.get("message") or {}).get("content") or ""
                    if text:
                        got_text = True
                        yield text
                    if chunk.get("done"):
                        self.last_usage = Usage(
                            input_tokens=int(chunk.get("prompt_eval_count", 0) or 0),
                            output_tokens=int(chunk.get("eval_count", 0) or 0),
                        )
                        break
        except httpx.TimeoutException:
            raise ProviderError("transient", detail="timeout") from None
        except httpx.TransportError:
            raise ProviderError("network") from None
        if not got_text:
            raise ProviderError("empty")


def installed_models(base_url: str = BASE_URL, timeout: float = 3.0) -> list[str] | None:
    """O'rnatilgan modellar (`/api/tags`). None — Ollama ishlamayapti yoki javob noto'g'ri.

    Sozlamalar oynasi buni fon oqimida chaqiradi: shuning uchun httpx emas, oddiy `http.client`
    (fon oqimida yangi modul importi va SSL konteksti yaratilmaydi — Qt bilan to'qnashmaydi).
    """
    url = urlsplit(base_url)
    conn = http.client.HTTPConnection(
        url.hostname or "127.0.0.1", url.port or 11434, timeout=timeout
    )
    try:
        conn.request("GET", "/api/tags")
        resp = conn.getresponse()
        if resp.status != 200:
            return None
        models = json.loads(resp.read()).get("models", [])
        return sorted(str(m["name"]) for m in models if isinstance(m, dict) and m.get("name"))
    except (OSError, http.client.HTTPException, ValueError, KeyError, TypeError, AttributeError):
        return None
    finally:
        conn.close()
