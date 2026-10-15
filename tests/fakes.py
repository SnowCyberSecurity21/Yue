"""Testlar uchun soxta provayderlar va soat (tarmoq yo'q)."""

from __future__ import annotations

from yue.ai.providers.base import ProviderError, Usage, target_key


class FakeClock:
    def __init__(self, start: float = 1_800_000_000.0) -> None:
        self.t = start
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        self.t += s

    def advance(self, s: float) -> None:
        self.t += s


class Partial:
    """Bir qismini chiqarib, keyin xato beradigan javob."""

    def __init__(self, text: str, error: ProviderError) -> None:
        self.text, self.error = text, error


class FakeProvider:
    def __init__(
        self,
        name: str,
        model: str,
        script=(),
        private: bool = True,
        default: str | None = "[happy] Salom! Men shu yerdaman, nima qilamiz?",
        clock: FakeClock | None = None,
        latency: float = 0.0,
    ) -> None:
        self.name, self.model, self.private = name, model, private
        self.script = list(script)
        self.default = default
        self.calls: list[tuple[list, list]] = []
        self.last_usage: Usage | None = None
        self.clock, self.latency = clock, latency

    @property
    def key(self) -> str:
        return target_key(self.name, self.model)

    def stream(self, system, messages, max_tokens, timeout):
        self.calls.append((list(system), list(messages)))
        if self.clock is not None and self.latency:
            self.clock.advance(self.latency)
        item = self.script.pop(0) if self.script else self.default
        if item is None:
            raise ProviderError("empty")
        if isinstance(item, ProviderError):
            raise item
        if isinstance(item, Partial):
            yield item.text
            raise item.error
        for i in range(0, len(item), 7):
            yield item[i : i + 7]
        self.last_usage = Usage(input_tokens=100, output_tokens=20)

    def __repr__(self) -> str:
        return f"Fake({self.key})"


def chain(clock=None, **scripts):
    """Standart zanjir: haiku, 4 ta gemini, sonnet. scripts: haiku=[...], g38=[...] ..."""
    spec = [
        ("haiku", "claude", "claude-haiku-5-5", True),
        ("g38", "gemini", "gemini-3.8-flash", False),
        ("g36", "gemini", "gemini-3.6-flash", False),
        ("g35", "gemini", "gemini-3.5-flash-lite", False),
        ("g31", "gemini", "gemini-3.1-flash-lite", False),
        ("sonnet", "claude", "claude-sonnet-5-5", True),
    ]
    return {
        short: FakeProvider(name, model, scripts.get(short, ()), private=priv, clock=clock)
        for short, name, model, priv in spec
    }


def err(kind, **kw) -> ProviderError:
    return ProviderError(kind, **kw)
