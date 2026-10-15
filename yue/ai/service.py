"""AI xizmati: savol → router → til himoyasi → teglar. Qt'ga bog'liq emas (UI uni oqimda chaqiradi).

Natija har doim foydalanuvchiga ko'rsatsa bo'ladigan o'zbekcha narsa:
- `answer` — AI javobi (Reply);
- `queued` — internet yo'q yoki hamma maqsad band: savol navbatda, Yue `offline`/`busy` iborasi;
- `fallback` — javob olinmadi: xarakterdagi `confused` iborasi;
- `no_keys` — kalit ulanmagan (Offline'da — Ollama modeli tanlanmagan).

Offline'da Ollama ishlamayotgan bo'lsa (ulanib bo'lmadi): savol navbatga, Yue
`ollama_ishlamayapti` iborasini aytadi va navbat `LOCAL_DOWN_WAIT` (5 daqiqa) davomida qayta
urinmaydi. `ChatResult.reason` — navbatga tushish sababi: offline / busy / local_down.
"""

from __future__ import annotations

import logging
import socket
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from yue.ai import guard, prompt
from yue.ai.parse import Reply, parse_reply
from yue.ai.providers.base import ChatMessage, Provider, SystemBlock
from yue.ai.router import Answer, OfflineQueue, QueuedQuestion, Router
from yue.ai.usage import UsageTracker
from yue.i18n import t
from yue.lines import Line, Lines

log = logging.getLogger(__name__)

CHAT_MAX_TOKENS = 1024
TRANSLATE_MAX_TOKENS = 1024
PROBE_HOSTS = (
    ("api.anthropic.com", 443),
    ("generativelanguage.googleapis.com", 443),
    ("openrouter.ai", 443),
)

LOCAL_DOWN_WAIT = 5 * 60.0  # Ollama ishlamasa — navbat keyingi urinishgacha kutadi

ResultKind = Literal["answer", "queued", "fallback", "no_keys", "cancelled", "timeout"]


def _local_down(ans: Answer) -> bool:
    """Zanjirdagi hamma xato — lokal Ollama'ga ulanib bo'lmagani (ilova ishlamayapti)."""
    return bool(ans.errors) and all(
        e.startswith("ollama:") and e.endswith(":network") for e in ans.errors
    )


@dataclass
class ChatResult:
    kind: ResultKind
    reply: Reply | None = None
    line: Line | None = None  # AI'siz ibora (navbat, xato, kalit yo'q)
    target: str = ""
    translated: bool = False
    budget_exceeded: bool = False
    queued: QueuedQuestion | None = None
    reason: str = ""  # queued: offline (internet yo'q) / busy / local_down (Ollama ishlamayapti)


def internet_available(timeout: float = 3.0) -> bool:
    """Tarmoqqa chiqish mumkinmi (faqat TCP ulanish, ma'lumot yuborilmaydi)."""
    for host, port in PROBE_HOSTS:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False


class AiService:
    def __init__(
        self,
        router: Router,
        lines: Lines,
        context: Callable[[], prompt.PromptContext],
        queue: OfflineQueue | None = None,
        usage: UsageTracker | None = None,
        online: Callable[[], bool] = internet_available,
        offline_mode: Callable[[], bool] = lambda: False,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.router = router
        self.lines = lines
        self.context = context
        self.queue = queue or OfflineQueue()
        self.usage = usage or UsageTracker()
        self.online = online
        self.offline_mode = offline_mode  # Offline (faqat Ollama) tanlanganmi
        self.clock = clock
        self.local_down_until = 0.0  # Ollama ishlamayapti: navbat shu vaqtgacha urinmaydi
        self._lock = threading.Lock()  # bir vaqtda bitta so'rov (chat va navbat raqobatlashmaydi)

    # --- suhbat ----------------------------------------------------------------------------

    def chat(
        self,
        user_text: str,
        on_token: Callable[[str], None] | None = None,
        on_reset: Callable[[], None] | None = None,
        cancel: threading.Event | None = None,
        enqueue: bool = True,
    ) -> ChatResult:
        with self._lock:
            ctx = self.context()
            ans = self.router.ask(
                lambda t: (
                    prompt.build_short_persona(ctx, user_text, t.private)
                    if getattr(t, "local", False)
                    else prompt.build(ctx, user_text, t.private)
                ),
                on_token=on_token,
                on_reset=on_reset,
                max_tokens=CHAT_MAX_TOKENS,
                cancel=cancel,
            )
            return self._finish(user_text, ans, enqueue)

    def _finish(self, user_text: str, ans: Answer, enqueue: bool) -> ChatResult:
        if ans.outcome == "ok":
            self.local_down_until = 0.0
            over = self.usage.add(ans.target, ans.usage)
            text, translated = ans.text, False
            if guard.needs_translation(user_text, text):
                fixed = self._translate(user_text, text, private_only=ans.private)
                if fixed:
                    text, translated = fixed, True
            reply = parse_reply(text)
            if not reply.text and not reply.actions and reply.command is None:
                return ChatResult("fallback", line=self.lines.pick("confused"), target=ans.target)
            return ChatResult(
                "answer",
                reply=reply,
                target=ans.target,
                translated=translated,
                budget_exceeded=over,
            )
        if ans.outcome == "no_targets":
            if self.offline_mode():
                return ChatResult("no_keys", line=("thinking", t("notify.local_missing")))
            return ChatResult("no_keys", line=self.lines.pick("no_keys"))
        if ans.outcome == "offline" and _local_down(ans):
            self.local_down_until = self.clock() + LOCAL_DOWN_WAIT
            item = self.queue.add(user_text, self.local_down_until) if enqueue else None
            line = self.lines.pick("ollama_ishlamayapti")
            return ChatResult("queued", line=line, queued=item, reason="local_down")
        if ans.outcome in ("offline", "busy"):
            item = self.queue.add(user_text, ans.retry_at) if enqueue else None
            key = "offline" if ans.outcome == "offline" else "busy"
            return ChatResult("queued", line=self.lines.pick(key), queued=item, reason=key)
        return ChatResult("fallback", line=self.lines.pick("confused"))

    def _translate(self, user_text: str, text: str, private_only: bool) -> str | None:
        """Eng arzon maqsadda bir marta o'zbekchaga o'girish. Ishlamasa — None (asl javob)."""
        candidates = [t for t in self.router.usable() if t.private or not private_only]
        target = self._cheapest(candidates)
        if target is None:
            return None
        instr = guard.translate_instruction(user_text)
        ans = self.router.ask(
            lambda _t: ([SystemBlock(instr)], [ChatMessage("user", text)]),
            max_tokens=TRANSLATE_MAX_TOKENS,
            targets=[target],
        )
        if ans.outcome != "ok" or not ans.text.strip():
            return None
        self.usage.add(ans.target, ans.usage)
        return ans.text

    def _cheapest(self, candidates: list[Provider]) -> Provider | None:
        cheapest = self.router.cheapest()
        if cheapest is not None and cheapest in candidates:
            return cheapest
        order = [c for c in self.router.targets if c in candidates]
        # Zanjirda oxirgi zaxira (Sonnet) eng qimmat — undan oldingilarni afzal ko'ramiz
        return order[0] if order else None

    # --- oflayn navbat ---------------------------------------------------------------------

    def process_queue(self) -> list[tuple[QueuedQuestion, ChatResult]]:
        """Vaqti kelgan navbatdagi savollarga javob olish (30–60 s oralig'ida chaqiriladi)."""
        due = self.queue.due()
        if not due:
            return []
        if self.clock() < self.local_down_until:
            for item in due:  # Ollama ishlamayapti — 5 daqiqa tinch turamiz
                self.queue.postpone(item, self.local_down_until)
            return []
        if not self.online():
            for item in due:
                self.queue.postpone(item)
            return []
        out: list[tuple[QueuedQuestion, ChatResult]] = []
        for item in due:
            res = self.chat(item.text, enqueue=False)
            if res.kind == "queued":
                retry = self.local_down_until if res.reason == "local_down" else None
                self.queue.postpone(item, retry or self.router.earliest_ready())
                continue
            self.queue.done(item)
            out.append((item, res))
        return out
