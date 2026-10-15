"""System bloklari va xabarlarni yig'ish.

Tartib (o'zgarmas qismlar oldinda — prompt keshi ishlashi uchun):
  1. persona_uz.txt                        [kesh]
  2. [Xotira xulosasi] + [Faktlar] + [Sog'liq daftari] — faqat private  [kesh]
  3. [Vazifalar]
  4. [Holat] — sana, soat, kun qismi, kiyim, faoliyat, batareya, hazil darajasi, kayfiyat
     (o'zgaradi)
Xabarlar: oxirgi 8–10 suhbat + joriy savol.

Maxfiylik: `private=False` maqsadga (bepul Gemini) sog'liq daftari, shaxsiy faktlar va
suhbatlardan olingan xotira xulosasi **umuman** qo'shilmaydi. Faqat joriy suhbat yuboriladi.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import cache

from yue import paths
from yue.ai.providers.base import ChatMessage, SystemBlock

HISTORY_LIMIT = 10
LOCAL_HISTORY_LIMIT = 6

WEEKDAYS_UZ = ("dushanba", "seshanba", "chorshanba", "payshanba", "juma", "shanba", "yakshanba")
MONTHS_UZ = (
    "yanvar", "fevral", "mart", "aprel", "may", "iyun",
    "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
)  # fmt: skip
PERIODS_UZ = {"morning": "ertalab", "day": "kunduzi", "evening": "kechqurun", "night": "tun"}
OUTFITS_UZ = {
    "tee": "oq futbolka",
    "hoodie_black": "qora xudi",
    "hoodie_silver": "kumushrang xudi",
    "hood_black": "qora xudi (kapyushon boshda)",
    "hood_silver": "kumushrang xudi (kapyushon boshda)",
}
ACTIVITIES_UZ = {
    "idle": "shunchaki turibsan",
    "walk": "aylanib yuribsan",
    "walk_music": "quloqchinda musiqa tinglab yuribsan",
    "walk_pocket": "qo'llaring cho'ntakda, o'ylanib yuribsan",
    "type": "noutbukda kod yozyapsan",
    "sit": "o'tiribsan",
    "music": "musiqa tinglayapsan",
    "look_around": "atrofga alanglayapsan",
    "butterfly": "kapalakni kuzatyapsan",
    "flower": "gul hidlayapsan",
    "ponder": "o'ylanib qolgansan",
    "tea": "choy ichyapsan",
    "stretch": "kerishyapsan",
    "train": "boks mashq qilyapsan",
    "sleep": "uxlayotgan eding",
    "listen": "foydalanuvchini tinglayapsan",
    "talk": "gapiryapsan",
    "wave": "qo'l silkityapsan",
    "excited_jump": "xursand bo'lib sakrayapsan",
    "angry_stomp": "jahl bilan depsinyapsan",
    "sayr": "foydalanuvchi bilan birga sayr qilyapsan",
}
HUMOR_UZ = {"low": "kam", "medium": "o'rtacha", "high": "ko'p"}


@cache
def persona_text() -> str:
    return (paths.PERSONA_DIR / "persona_uz.txt").read_text(encoding="utf-8").strip()


@cache
def summarizer_text() -> str:
    return (paths.PERSONA_DIR / "summarizer_uz.txt").read_text(encoding="utf-8").strip()


@dataclass
class PromptContext:
    now: dt.datetime
    period: str = "day"
    outfit: str = "tee"
    accessories: tuple[str, ...] = ()
    activity: str = "idle"
    battery: tuple[int, bool] | None = None  # (foiz, zaryadda)
    tasks: Sequence[str] = ()  # "#3: matn — 2026-10-14 09:00"
    summary: str = ""
    facts: Sequence[str] = ()
    health: Sequence[str] = ()
    user_name: str = ""
    humor: str = "medium"  # hazil darajasi: low / medium / high (Sozlamalar → Yue)
    mood: str = "xursand"  # `yue.feelings.Mood`
    history: Sequence[ChatMessage] = field(default_factory=list)


def describe_time(now: dt.datetime, period: str) -> str:
    return (
        f"{now.day}-{MONTHS_UZ[now.month - 1]} {now.year}-yil, {WEEKDAYS_UZ[now.weekday()]}, "
        f"soat {now:%H:%M} ({PERIODS_UZ.get(period, period)})"
    )


def _state_block(ctx: PromptContext) -> str:
    lines = [f"Hozir: {describe_time(ctx.now, ctx.period)}. ISO: {ctx.now:%Y-%m-%d %H:%M}."]
    wear = OUTFITS_UZ.get(ctx.outfit, ctx.outfit)
    acc = []
    if "glasses" in ctx.accessories:
        acc.append("ko'zoynak")
    if "phones_head" in ctx.accessories:
        acc.append("quloqchin boshda")
    elif "phones_neck" in ctx.accessories:
        acc.append("quloqchin bo'yinda")
    lines.append(f"Ustingda: {wear}" + (f", {', '.join(acc)}" if acc else "") + ".")
    lines.append(f"Hozir {ACTIVITIES_UZ.get(ctx.activity, 'shu yerdasan')}.")
    if ctx.battery is not None:
        pct, plugged = ctx.battery
        lines.append(f"Noutbuk batareyasi: {pct}%" + (" (zaryadlanmoqda)." if plugged else "."))
    lines.append(f"Hazil darajasi: {HUMOR_UZ.get(ctx.humor, HUMOR_UZ['medium'])}.")
    lines.append(f"Kayfiyat: {ctx.mood}.")
    return "[Holat]\n" + "\n".join(lines)


def build(
    ctx: PromptContext, user_text: str, private: bool, *, local: bool = False
) -> tuple[list[SystemBlock], list[ChatMessage]]:
    persona = short_persona_text() if local else persona_text()
    blocks = [SystemBlock(persona, cache=True)]

    memory: list[str] = []
    if private:
        if ctx.summary:
            memory.append("[Xotira xulosasi]\n" + ctx.summary.strip())
        if ctx.user_name:
            memory.append(f"[Foydalanuvchi]\nIsmi: {ctx.user_name}")
        if ctx.facts:
            memory.append("[Faktlar]\n" + "\n".join(f"- {f}" for f in ctx.facts))
        if ctx.health:
            memory.append("[Sog'liq daftari]\n" + "\n".join(f"- {h}" for h in ctx.health))
    else:
        memory.append(
            "[Eslatma]\nBu safar foydalanuvchi haqidagi xotira, faktlar va sog'liq daftari "
            "maxfiylik sababli berilmagan. Ular so'ralsa, hozir eslay olmasligingni ayt."
        )
    if memory:
        blocks.append(SystemBlock("\n\n".join(memory), cache=True))

    if private:
        if ctx.tasks:
            blocks.append(SystemBlock("[Vazifalar]\n" + "\n".join(ctx.tasks)))
        else:
            blocks.append(SystemBlock("[Vazifalar]\nOchiq vazifa yo'q."))
    else:
        blocks.append(SystemBlock("[Vazifalar]\nMaxfiylik sabab bu safar berilmagan."))
    blocks.append(SystemBlock(_state_block(ctx)))

    limit = LOCAL_HISTORY_LIMIT if local else HISTORY_LIMIT
    messages = list(ctx.history)[-limit:] if private else []
    # API birinchi xabar foydalanuvchidan bo'lishini talab qiladi
    while messages and messages[0].role != "user":
        messages.pop(0)
    messages.append(ChatMessage("user", user_text))
    return blocks, messages


@cache
def short_persona_text() -> str:
    return (paths.PERSONA_DIR / "persona_qisqa_uz.txt").read_text(encoding="utf-8").strip()


def build_short_persona(
    ctx: PromptContext, user_text: str, private: bool
) -> tuple[list[SystemBlock], list[ChatMessage]]:
    """Ollama uchun ixcham persona; xotira, holat va buyruqlar umumiy quruvchidan olinadi."""
    return build(ctx, user_text, private, local=True)
