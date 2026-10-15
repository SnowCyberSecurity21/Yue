"""Xotira xulosasi: eski suhbatlar qisqa xulosaga aylantiriladi va o'chiriladi.

- Fonda, faqat xabarlar yetarlicha yig'ilganda ishlaydi; chat so'rovi ketayotgan bo'lsa kutadi
  (chat bilan raqobatlashmaydi).
- Zanjirning yarmidan ko'pi cooldown'da bo'lsa — kechiktiriladi.
- Suhbatlarda shaxsiy va sog'liq ma'lumotlari bo'lishi mumkin, shuning uchun xulosa faqat
  `private` maqsadda (Claude yoki pullik Gemini) yoziladi; bunday maqsad bo'lmasa — kutadi.
"""

from __future__ import annotations

import datetime as dt
import logging
import threading

from yue.ai import prompt
from yue.ai.parse import clean_markdown
from yue.ai.providers.base import ChatMessage, SystemBlock
from yue.ai.router import Router
from yue.ai.usage import UsageTracker
from yue.memory.store import Store

log = logging.getLogger(__name__)

KEEP_RECENT = 10  # tarix uchun xom holda qoladi
MIN_BATCH = 20  # shuncha eski xabar yig'ilganda xulosa qilinadi
MAX_SUMMARY = 2000
BUSY_LIMIT = 0.5


class Summarizer:
    def __init__(
        self,
        store: Store,
        router: Router,
        chat_lock: threading.Lock,
        usage: UsageTracker | None = None,
    ) -> None:
        self.store = store
        self.router = router
        self.chat_lock = chat_lock
        self.usage = usage

    def _target(self):
        order = ["claude:claude-haiku-5-5", "gemini:gemini-3.1-flash-lite",
                 "gemini:gemini-3.5-flash-lite", "gemini:gemini-3.6-flash",
                 "gemini:gemini-3.8-flash", "claude:claude-sonnet-5-5"]  # fmt: skip
        usable = {t.key: t for t in self.router.usable() if t.private}
        for key in order:
            if key in usable:
                return usable[key]
        return next(iter(usable.values()), None)

    def maybe_run(self) -> bool:
        """True — xulosa yangilandi."""
        if self.store.count_unsummarized() < KEEP_RECENT + MIN_BATCH:
            return False
        if self.router.busy_ratio() > BUSY_LIMIT:
            return False
        target = self._target()
        if target is None:
            return False
        if not self.chat_lock.acquire(blocking=False):
            return False  # hozir chat ketyapti
        try:
            batch = self.store.unsummarized(KEEP_RECENT)
            if len(batch) < MIN_BATCH:
                return False
            old = self.store.get_summary() or "(hali yo'q)"
            lines = [
                f"{'Foydalanuvchi' if role == 'user' else 'Yue'}: {text}" for _, role, text in batch
            ]
            today = dt.date.today().strftime("%d.%m.%Y")
            user = f"[Hozirgi xulosa]\n{old}\n\n[Yangi suhbatlar — bugun {today}]\n" + "\n".join(
                lines
            )
            ans = self.router.ask(
                lambda _t: ([SystemBlock(prompt.summarizer_text())], [ChatMessage("user", user)]),
                max_tokens=1200,
                targets=[target],
            )
            if ans.outcome != "ok":
                return False
            text = clean_markdown(ans.text)[:MAX_SUMMARY].strip()
            if not text:
                return False
            if self.usage is not None:
                self.usage.add(ans.target, ans.usage)
            self.store.set_summary(text)
            self.store.mark_summarized([mid for mid, _, _ in batch])
            log.info("xotira xulosasi yangilandi (%d xabar)", len(batch))
            return True
        finally:
            self.chat_lock.release()
