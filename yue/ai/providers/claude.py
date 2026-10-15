"""Claude (Anthropic Messages API) — rasmiy `anthropic` SDK, streaming, prompt keshi.

- `cache_control` o'zgarmas system bloklarga qo'yiladi (persona va h.k.).
- `output_config.effort = "low"` — gap pufagi uchun tez va qisqa javob.
- SDK'ning o'z qayta urinishlari o'chirilgan (`max_retries=0`): aks holda 429 da SDK
  `retry-after` gacha kutib qoladi va zanjir keyingi maqsadga o'z vaqtida o'tolmaydi.
  Qayta urinishni router boshqaradi.
- Anthropic API ma'lumotlari standart holatda modelni o'qitishga ishlatilmaydi → `private=True`.
- SDK (~65 MB xotira) birinchi so'rovda, AI ishchi oqimida yuklanadi — UI ochilishi sekinlashmaydi.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING, Any

from yue.ai.providers.base import (
    ChatMessage,
    ProviderError,
    SystemBlock,
    Usage,
    target_key,
)

if TYPE_CHECKING:
    import anthropic

HAIKU = "claude-haiku-5-5"
SONNET = "claude-sonnet-5-5"


def _retry_after(err: Any) -> float | None:
    try:
        value = err.response.headers.get("retry-after")
        return float(value) if value is not None else None
    except (TypeError, ValueError, AttributeError):
        return None


def map_error(err: Exception) -> ProviderError:
    """SDK xatosini router turiga o'tkazish (eng aniq klassdan boshlab)."""
    import anthropic

    if isinstance(err, anthropic.APITimeoutError):
        return ProviderError("transient", detail="timeout")
    if isinstance(err, anthropic.APIConnectionError):
        return ProviderError("network")
    if isinstance(err, anthropic.RateLimitError):
        return ProviderError("rate_limit", status=429, retry_after=_retry_after(err))
    if isinstance(err, anthropic.AuthenticationError | anthropic.PermissionDeniedError):
        return ProviderError("auth", status=err.status_code)
    if isinstance(err, anthropic.APIStatusError):
        code = err.status_code
        if code == 402:
            return ProviderError("auth", status=code, detail="billing")
        if code in (400, 404, 413, 422):
            return ProviderError("bad_request", status=code)
        if code >= 500 or code in (408, 409):
            return ProviderError("transient", status=code)
        return ProviderError("bad_request", status=code)
    return ProviderError("transient", detail=type(err).__name__)


class ClaudeProvider:
    name = "claude"

    def __init__(
        self,
        api_key: str,
        model: str = HAIKU,
        effort: str = "low",
        client: Any | None = None,
    ) -> None:
        self.model = model
        self.effort = effort
        self.private = True
        self.last_usage: Usage | None = None
        self._api_key = api_key
        self._client_obj = client

    @property
    def _client(self) -> anthropic.Anthropic:
        if self._client_obj is None:
            import anthropic

            self._client_obj = anthropic.Anthropic(api_key=self._api_key, max_retries=0)
        return self._client_obj

    @property
    def key(self) -> str:
        return target_key(self.name, self.model)

    @staticmethod
    def _system(blocks: Sequence[SystemBlock]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for b in blocks:
            block: dict[str, Any] = {"type": "text", "text": b.text}
            if b.cache:
                block["cache_control"] = {"type": "ephemeral"}
            out.append(block)
        return out

    def stream(
        self,
        system: Sequence[SystemBlock],
        messages: Sequence[ChatMessage],
        max_tokens: int,
        timeout: float,
    ) -> Iterator[str]:
        import anthropic

        self.last_usage = None
        got_text = False
        try:
            with self._client.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                system=self._system(system),
                messages=[{"role": m.role, "content": m.text} for m in messages],
                output_config={"effort": self.effort},
                timeout=anthropic.Timeout(timeout, connect=min(8.0, timeout)),
            ) as stream:
                for text in stream.text_stream:
                    if text:
                        got_text = True
                        yield text
                final = stream.get_final_message()
        except anthropic.AnthropicError as exc:
            raise map_error(exc) from None
        u = final.usage
        self.last_usage = Usage(
            input_tokens=u.input_tokens or 0,
            output_tokens=u.output_tokens or 0,
            cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
            cache_write_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
        )
        if final.stop_reason == "refusal":
            raise ProviderError("safety", detail="refusal")
        if not got_text:
            raise ProviderError("empty")
