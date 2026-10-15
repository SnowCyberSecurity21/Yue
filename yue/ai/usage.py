"""Kunlik token va taxminiy xarajat hisobi (lokal).

Byudjet faqat ogohlantiradi — javobni to'xtatmaydi.

Narxlar (1 mln token, USD) rasmiy narxlar sahifasidan; Haiku 5.5 — 100 ming tokengacha so'rovlar.
Gemini bepul tarifda — 0; pullik Gemini narxi hisoblanmaydi (faqat tokenlar).
OpenRouter javobida aniq narx keladi (`Usage.cost`) — jadval o'rniga shu ishlatiladi.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass, field

from yue.ai.providers.base import Usage

# input, output, cache_read, cache_write (5 daqiqalik yozish = 1.25 × input)
PRICES: dict[str, tuple[float, float, float, float]] = {
    "claude:claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
    "claude:claude-sonnet-5-5": (2.00, 10.00, 0.20, 2.50),
}


def cost_usd(target: str, u: Usage) -> float:
    if u.cost is not None:
        return u.cost  # OpenRouter narxni o'zi aytadi (model va provayderga qarab o'zgaradi)
    p = PRICES.get(target)
    if p is None:
        return 0.0
    return (
        u.input_tokens * p[0]
        + u.output_tokens * p[1]
        + u.cache_read_tokens * p[2]
        + u.cache_write_tokens * p[3]
    ) / 1_000_000


@dataclass
class DayUsage:
    day: str
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cost: float = 0.0
    by_target: dict[str, int] = field(default_factory=dict)


class UsageTracker:
    """`store` (ixtiyoriy, 3-bosqich): `usage_add(day, target, usage, cost)`, `usage_day(day)`."""

    def __init__(
        self,
        budget_usd: float = 0.0,
        store=None,
        today: Callable[[], dt.date] = dt.date.today,
    ) -> None:
        self.budget_usd = budget_usd
        self.store = store
        self.today = today
        self._day = DayUsage(self.today().isoformat())
        self._warned_day = ""
        if store is not None:
            loaded = store.usage_day(self._day.day)
            if loaded is not None:
                self._day = loaded

    @property
    def day(self) -> DayUsage:
        d = self.today().isoformat()
        if self._day.day != d:
            self._day = DayUsage(d)
        return self._day

    def add(self, target: str, u: Usage | None) -> bool:
        """Hisobga qo'shish. True — kunlik byudjet hozirgina oshdi (bir marta ogohlantirish)."""
        day = self.day
        day.requests += 1
        day.by_target[target] = day.by_target.get(target, 0) + 1
        cost = 0.0
        if u is not None:
            day.input_tokens += u.input_tokens
            day.output_tokens += u.output_tokens
            day.cache_read_tokens += u.cache_read_tokens
            cost = cost_usd(target, u)
            day.cost += cost
        if self.store is not None:
            self.store.usage_add(day.day, target, u or Usage(), cost)
        if self.budget_usd > 0 and day.cost >= self.budget_usd and self._warned_day != day.day:
            self._warned_day = day.day
            return True
        return False
