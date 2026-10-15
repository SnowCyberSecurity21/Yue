"""Sozlamalardan maqsadlar zanjirini qurish (suhbat uchun).

Online (`ai.manba = "online"`) — faqat bulut API'lar, `ai.primary` bo'yicha:
Asosiy: Claude, "Aqlliroq" (standart): sonnet → haiku → gemini 3.8 → 3.6 → 3.5-lite → 3.1-lite
Asosiy: Claude, "Tez":                 haiku → gemini 3.8 → … → 3.1-lite → sonnet (oxirgi zaxira)
Asosiy: Gemini:                        gemini 3.8 → … → 3.1-lite → sonnet/haiku (rejim bo'yicha)
Asosiy: OpenRouter:                    tanlangan OpenRouter modeli → Claude/Gemini (yuqoridagicha)
OpenRouter kaliti bor, lekin asosiy emas — qo'shimcha bulut model sifatida oxirida.
Faqat Gemini kaliti bo'lsa — gemini-3.8-flash birinchi. Haiku xotira xulosasi va fon ishlari
uchun ham ishlatiladi (`Router.cheapest`). Ollama Online zanjiriga hech qachon qo'shilmaydi.

Offline (`offline=True`) — faqat Ollama (`local`); model tanlanmagan bo'lsa zanjir bo'sh.
Tarjima va xotira xulosasi ham shu zanjirda — kompyuterdan tashqariga hech narsa chiqmaydi.

Kaliti yo'q provayder qo'shilmaydi.
`available_gemini` berilsa (models.list), unda yo'q Gemini modellari chiqarib tashlanadi.
"""

from __future__ import annotations

from collections.abc import Callable

from yue.ai.providers.base import Provider
from yue.ai.providers.claude import HAIKU, SONNET, ClaudeProvider
from yue.ai.providers.gemini import MODELS as GEMINI_MODELS
from yue.ai.providers.gemini import GeminiProvider
from yue.ai.providers.openrouter import DEFAULT_MODEL as OPENROUTER_DEFAULT
from yue.ai.providers.openrouter import OpenRouterProvider


def build_chain(
    claude_key: str | None,
    gemini_key: str | None,
    *,
    gemini_paid: bool = False,
    primary: str = "claude",
    smart: bool = False,
    available_gemini: set[str] | None = None,
    offline: bool = False,
    local: Provider | None = None,
    openrouter_key: str | None = None,
    openrouter_model: str = OPENROUTER_DEFAULT,
    make_claude: Callable[..., Provider] = ClaudeProvider,
    make_gemini: Callable[..., Provider] = GeminiProvider,
    make_openrouter: Callable[..., Provider] = OpenRouterProvider,
) -> list[Provider]:
    if offline:
        return [local] if local is not None else []
    router: list[Provider] = []
    if openrouter_key:
        router = [make_openrouter(openrouter_key, model=openrouter_model or OPENROUTER_DEFAULT)]
    first_claude, last_claude = (SONNET, HAIKU) if smart else (HAIKU, SONNET)
    claude: list[Provider] = []
    if claude_key:
        claude = [
            make_claude(claude_key, model=first_claude),
            make_claude(claude_key, model=last_claude),
        ]
    gemini: list[Provider] = []
    if gemini_key:
        for model in GEMINI_MODELS:
            if available_gemini is not None and model not in available_gemini:
                continue
            gemini.append(make_gemini(gemini_key, model=model, paid=gemini_paid))

    if primary == "gemini":
        cloud = [*gemini, *claude]
    elif claude and smart:
        cloud = [*claude, *gemini]  # Sonnet, uning orqasida Haiku — keyin Gemini
    elif claude:
        cloud = [claude[0], *gemini, claude[1]]
    else:
        cloud = [*gemini]
    if primary == "openrouter":
        return [*router, *cloud]
    return [*cloud, *router]
