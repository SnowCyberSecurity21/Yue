"""AI javobini ajratish: boshdagi [ifoda] tegi, oxiridagi buyruq teglari, markdown tozalash.

Faqat oq ro'yxatdagi teglar amalga aylanadi: <vazifa>, <bajarildi>, <ochir>, <eslab>,
<salomatlik> (inglizcha taxalluslar: task, done, delete, remember, health) va <harakat>nom</harakat>
— faqat `persona/harakatlar.json` dagi nomlar, javobda ko'pi bilan bitta. Qolgan hamma narsa —
oddiy matn. Model kompyuterda boshqa hech narsa qila olmaydi. Teglar foydalanuvchiga ko'rinmaydi.
"""

from __future__ import annotations

import re
from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Literal

from yue.commands import default_names

EXPRESSIONS = (
    "neutral",
    "happy",
    "excited",
    "angry",
    "sad",
    "surprised",
    "sleepy",
    "smug",
    "curious",
    "disgusted",
    "thinking",
    "shy",
)
# Yue'da yo'q ifodalar (romantika) — model qaytarsa, shunga almashadi
EXPRESSION_ALIASES = {"love": "happy"}
TAG_ALIASES = {
    "vazifa": "task",
    "task": "task",
    "bajarildi": "done",
    "done": "done",
    "ochir": "delete",
    "o'chir": "delete",
    "delete": "delete",
    "eslab": "remember",
    "remember": "remember",
    "salomatlik": "health",
    "health": "health",
}
COMMAND_TAGS = ("harakat",)  # ish stolidagi harakat (buyruq) — `Reply.command`
MAX_TAG_TEXT = 300
MAX_ACTIONS = 8

ActionKind = Literal["task", "done", "delete", "remember", "health"]

_EXPR_RE = re.compile(r"^\s*\[([a-zA-Z_]+)\]\s*")
_TAG_RE = re.compile(
    r"<\s*(?P<name>[a-zA-Z'_]+)(?P<attrs>[^<>]*)>(?P<body>.*?)<\s*/\s*(?P=name)\s*>", re.S
)
_ATTR_RE = re.compile(r"""(\w+)\s*=\s*["“”']([^"“”']*)["“”']""")
_ALL_TAGS = (*TAG_ALIASES, *COMMAND_TAGS)
_STRAY_TAG_RE = re.compile(
    r"<\s*/?\s*(?:" + "|".join(re.escape(k) for k in _ALL_TAGS) + r")\b[^<>]*>?", re.I
)
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
_TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    text: str = ""
    when: str | None = None  # "YYYY-MM-DD HH:MM" yoki har kunlik "HH:MM"
    repeat: str | None = None  # "har_kuni"
    task_id: int | None = None


@dataclass
class Reply:
    expression: str = "neutral"
    text: str = ""
    actions: list[Action] = field(default_factory=list)
    command: str | None = None  # <harakat> — harakatlar.json dagi nom
    tagged: bool = False  # javob [ifoda] tegi bilan boshlandi (yo'q bo'lsa — kayfiyat ifodasi)


def clean_markdown(text: str) -> str:
    text = re.sub(r"```[a-zA-Z0-9_+-]*\n?", "", text)  # kod bloklari: ichi qoladi
    text = re.sub(r"`([^`\n]*)`", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), text)
    text = re.sub(r"^\s{0,3}#{1,6}\s+", "", text, flags=re.M)
    text = re.sub(r"^\s*[*•]\s+", "- ", text, flags=re.M)
    text = re.sub(r"^\s*>\s?", "", text, flags=re.M)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1 (\2)", text)
    text = re.sub(r"^\s*\|?(\s*:?-{3,}:?\s*\|)+\s*$", "", text, flags=re.M)  # jadval chiziqlari
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _action(name: str, attrs: str, body: str) -> Action | None:
    kind = TAG_ALIASES.get(name.lower().replace("ʻ", "'").replace("’", "'"))
    if kind is None:
        return None
    body = " ".join(body.split())[:MAX_TAG_TEXT]
    if kind in ("done", "delete"):
        m = re.search(r"\d+", body)
        return Action(kind, task_id=int(m.group())) if m else None
    if not body:
        return None
    if kind == "task":
        a = {k.lower(): v.strip() for k, v in _ATTR_RE.findall(attrs)}
        when = a.get("vaqt") or a.get("time") or a.get("when")
        repeat = a.get("takror") or a.get("repeat")
        if repeat in ("har_kuni", "daily", "har kuni"):
            repeat = "har_kuni"
            if when and not _TIME_RE.match(when):
                # "2026-10-14 09:00" berilgan bo'lsa — faqat soati olinadi
                m = re.search(r"(\d{1,2}:\d{2})$", when)
                when = m.group(1) if m else None
            if not when:
                return Action("task", body)  # vaqtsiz "har kuni" — oddiy vazifa
        else:
            repeat = None
            if when and not _DATETIME_RE.match(when):
                when = None  # noto'g'ri format — muddatsiz vazifa
        return Action("task", body, when=when, repeat=repeat)
    return Action(kind, body)


def parse_reply(raw: str, commands: Collection[str] | None = None) -> Reply:
    """`commands` — ruxsat etilgan harakat nomlari (standart: harakatlar.json)."""
    allowed = default_names() if commands is None else commands
    reply = Reply()
    text = raw or ""
    m = _EXPR_RE.match(text)
    if m:
        name = m.group(1).lower()
        name = EXPRESSION_ALIASES.get(name, name)
        reply.expression = name if name in EXPRESSIONS else "neutral"
        reply.tagged = name in EXPRESSIONS
        text = text[m.end() :]
    # Model ba'zan ifoda tegini yana takrorlaydi — matn ichidagi bunday teglarni olib tashlash
    text = re.sub(r"\[(?:" + "|".join((*EXPRESSIONS, *EXPRESSION_ALIASES)) + r")\]\s*", "", text)

    def take(match: re.Match[str]) -> str:
        name = match.group("name").lower()
        if name in COMMAND_TAGS:
            cmd = " ".join(match.group("body").split()).lower()
            if reply.command is None and cmd in allowed:
                reply.command = cmd  # birinchisi; noma'lum nom va ortiqchalari e'tiborsiz
            return " "
        act = _action(match.group("name"), match.group("attrs"), match.group("body"))
        if act is not None and len(reply.actions) < MAX_ACTIONS:
            reply.actions.append(act)
        return " " if TAG_ALIASES.get(name) else match.group(0)

    text = _TAG_RE.sub(take, text)
    text = _STRAY_TAG_RE.sub("", text)  # yopilmagan / buzilgan teglar bajarilmaydi
    reply.text = clean_markdown(text)
    reply.text = re.sub(r"[ \t]{2,}", " ", reply.text).strip()
    return reply


def stream_visible(partial: str) -> str:
    """Streaming paytida ko'rsatiladigan qism: ifoda tegi va boshlangan teglar yashiriladi."""
    text = partial.lstrip()
    if text.startswith("["):
        end = text.find("]")
        if end == -1:
            return ""
        text = text[end + 1 :].lstrip()
    cut = _tag_start(text)
    if cut is not None:
        text = text[:cut]
    return clean_markdown(text) if text.strip() else ""


def _tag_start(text: str) -> int | None:
    """Bizning teglarimizdan biri boshlanadigan (yoki boshlanishi mumkin bo'lgan) birinchi '<'."""
    for m in re.finditer("<", text):
        rest = text[m.end() : m.end() + 16]
        word = re.match(r"\s*/?\s*([A-Za-z'_]*)", rest).group(1).lower()  # type: ignore[union-attr]
        if not word:
            if m.end() + len(rest.strip()) >= len(text) and not rest.strip(" /"):
                return m.start()  # matn oxiridagi "<" — davomi hali kelmagan
            continue
        complete = len(word) < len(rest.strip(" /"))
        for alias in _ALL_TAGS:
            if alias == word or (not complete and alias.startswith(word)):
                return m.start()
    return None
