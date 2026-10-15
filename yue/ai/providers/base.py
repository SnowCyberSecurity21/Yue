"""Provayder interfeysi. Har bir provayder bitta modelga bog'langan "maqsad" (target).

Provayder faqat matn qaytaradi. Xatolar `ProviderError(kind=...)` ga aylantiriladi — router
ularni turiga qarab boshqaradi; xom xato matni foydalanuvchiga hech qachon ko'rsatilmaydi.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

ErrorKind = Literal[
    "rate_limit",  # 429 — qisqa muddatli limit
    "quota_daily",  # kunlik kvota tugadi (Gemini PerDay)
    "transient",  # 5xx, 529, timeout — bir marta qayta urinish mumkin
    "network",  # ulanish yo'q
    "auth",  # 401/403/402, noto'g'ri kalit
    "bad_request",  # 400/404 — so'rov yoki model noto'g'ri
    "safety",  # xavfsizlik bloki / rad etish
    "empty",  # bo'sh javob
]


class ProviderError(Exception):
    def __init__(
        self,
        kind: ErrorKind,
        *,
        status: int | None = None,
        retry_after: float | None = None,
        detail: str = "",
    ) -> None:
        # `detail` faqat texnik qisqa kod (masalan "PerDay"), hech qachon xabar matni emas.
        super().__init__(f"{kind} status={status} {detail}".strip())
        self.kind: ErrorKind = kind
        self.status = status
        self.retry_after = retry_after
        self.detail = detail


@dataclass(frozen=True)
class SystemBlock:
    text: str
    cache: bool = False  # True — o'zgarmas qism, prompt keshi uchun belgilanadi


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    text: str


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost: float | None = None  # provayder aytgan aniq narx, USD (OpenRouter `usage.cost`)


class Provider(Protocol):
    name: str  # "claude" / "gemini" / "openrouter" / "ollama"
    model: str
    # True — ma'lumotlar o'qitishga ishlatilmaydi (sog'liq va faktlar yuborilishi mumkin)
    private: bool
    last_usage: Usage | None

    @property
    def key(self) -> str:
        """Maqsad identifikatori: "claude:claude-haiku-5-5"."""
        ...

    def stream(
        self,
        system: Sequence[SystemBlock],
        messages: Sequence[ChatMessage],
        max_tokens: int,
        timeout: float,
    ) -> Iterator[str]:
        """Javobni bo'laklab qaytaradi. Xatoda `ProviderError` ko'taradi."""
        ...


def target_key(name: str, model: str) -> str:
    return f"{name}:{model}"
