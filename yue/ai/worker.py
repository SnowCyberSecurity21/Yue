"""AI so'rovlarini UI oqimidan tashqarida bajaruvchi QObject (alohida QThread'da yashaydi).

UI → ishchi: `request_*` signallari (navbatli ulanish). Ishchi → UI: natija signallari.
UI oqimi hech qachon tarmoqni kutmaydi.

Har savolning raqami (`rid`) bor va har biri albatta bitta `finished` bilan tugaydi — bekor
qilinganda ham (`ChatResult("cancelled")`). Bekor qilingan savol navbatda turgan bo'lsa,
tarmoqqa umuman chiqmaydi.
"""

from __future__ import annotations

import logging
import sys
import threading

from PySide6.QtCore import QObject, Signal, Slot

from yue.ai.service import AiService, ChatResult
from yue.memory.summarizer import Summarizer

log = logging.getLogger(__name__)


class AiWorker(QObject):
    token = Signal(str)
    reset = Signal()
    finished = Signal(int, str, object)  # rid, savol, ChatResult
    queue_answered = Signal(str, object)  # savol, ChatResult
    provider_failed = Signal(str, str)  # provayder, sabab (auth / billing)

    def __init__(self, service: AiService, summarizer: Summarizer | None = None) -> None:
        super().__init__()
        self.service = service
        self.summarizer = summarizer
        self._lock = threading.Lock()
        self._cancel_upto = 0  # shu raqamgacha bo'lgan savollar bekor qilingan
        self._current: tuple[int, threading.Event] | None = None

    def cancel(self, rid: int | None = None) -> None:
        """UI oqimidan: `rid` gacha bo'lgan savollarni bekor qilish (None — hammasini)."""
        with self._lock:
            self._cancel_upto = max(self._cancel_upto, sys.maxsize if rid is None else rid)
            if self._current is not None and self._current[0] <= self._cancel_upto:
                self._current[1].set()

    @Slot(int, str, bool)
    def ask(self, rid: int, text: str, enqueue: bool = True) -> None:
        from yue.ai.router import Cancelled

        event = threading.Event()
        with self._lock:
            if rid <= self._cancel_upto:
                event.set()
            self._current = (rid, event)
        try:
            if event.is_set():
                raise Cancelled
            res = self.service.chat(
                text,
                on_token=self.token.emit,
                on_reset=self.reset.emit,
                cancel=event,
                enqueue=enqueue,
            )
        except Cancelled:
            res = ChatResult("cancelled")
        except Exception:  # noqa: BLE001
            log.exception("AI so'rovida kutilmagan xato")
            res = ChatResult("fallback", line=self.service.lines.pick("confused"))
        finally:
            with self._lock:
                self._current = None
        self.finished.emit(rid, text, res)

    @Slot()
    def process_queue(self) -> None:
        try:
            for item, res in self.service.process_queue():
                self.queue_answered.emit(item.text, res)
        except Exception:  # noqa: BLE001
            log.exception("oflayn navbatni qayta ishlashda xato")

    @Slot()
    def summarize(self) -> None:
        if self.summarizer is None:
            return
        try:
            self.summarizer.maybe_run()
        except Exception:  # noqa: BLE001
            log.exception("xulosa yozishda xato")
