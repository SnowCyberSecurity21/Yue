"""Yuening "miyasi": xotira, AI, vazifalar va eslatmalar. UI bilan signallar orqali gaplashadi.

- AI so'rovlari, oflayn navbat va xulosa — alohida QThread'dagi `AiWorker` da.
- Rejalashtiruvchi har 15 s, tanaffus/batareya/ochiq vazifalar har daqiqada tekshiriladi.
- Kalitlar DPAPI bilan, xotira AES-GCM bilan (`yue.memory`).
- Kayfiyat (`yue.feelings.Mood`) — xotirada.
- AI manbasi (`ai.manba`): Online — faqat bulut API'lar, Offline — faqat Ollama.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from yue import modes, paths
from yue.ai import prompt
from yue.ai.factory import build_chain
from yue.ai.parse import stream_visible
from yue.ai.providers.base import ChatMessage
from yue.ai.providers.gemini import GeminiProvider, available_models
from yue.ai.providers.ollama import OllamaProvider
from yue.ai.router import OfflineQueue, Router
from yue.ai.service import AiService, ChatResult, internet_available
from yue.ai.usage import UsageTracker
from yue.ai.worker import AiWorker
from yue.config import Config
from yue.feelings import Mood
from yue.i18n import t
from yue.lines import Lines
from yue.memory.crypto import Cipher, CryptoError, SecretStore, load_or_create_data_key
from yue.memory.store import Store
from yue.memory.summarizer import Summarizer
from yue.platform import Platform
from yue.reminders import BatteryWatcher, BreakTracker
from yue.tasks.scheduler import Scheduler
from yue.tasks.store import TaskBook

log = logging.getLogger(__name__)

TASK_CHECK_MS = 15_000
MINUTE_MS = 60_000
QUEUE_CHECK_MS = 30_000
SUMMARY_MS = 5 * 60_000
ACTIVE_IDLE = 60.0  # foydalanuvchi shundan kam harakatsiz — "kompyuter yonida"
ASK_TIMEOUT_S = 60.0  # savolga umumiy vaqt; o'tib ketsa — zaxira ibora, maydon ochiladi
LOCAL_ASK_TIMEOUT_S = 120.0  # offline model zanjirda bo'lsa (CPU da sekin javob)
OFFER_MS = 5000  # "Offline rejimga o'tamizmi?" — navbat iborasidan keyin


@dataclass
class PetState:
    period: str = "day"
    outfit: str = "tee"
    overlays: tuple[str, ...] = ()
    activity: str = "idle"


@dataclass
class Conversation:
    """Joriy savol (UI oqimida)."""

    question: str = ""
    partial: list[str] = field(default_factory=list)
    started: float = 0.0
    rid: int = 0


def _backup_db(reason: str) -> None:
    """Ochib bo'lmaydigan bazani o'chirmasdan chetga olib qo'yish."""
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    for suffix in ("", "-wal", "-shm"):
        src = paths.db_path().with_name(paths.db_path().name + suffix)
        if src.exists():
            try:
                os.replace(src, src.with_name(f"{src.name}.eski-{stamp}"))
            except OSError:
                log.warning("eski baza chetga olinmadi")
    log.warning("xotira bazasi yangidan boshlandi (%s)", reason)


def open_memory(cfg: Config, platform: Platform) -> tuple[SecretStore, Store, bool]:
    """(sirlar, ombor, xotira_yangilandimi). Kalit ochilmasa — eski baza chetga olinadi."""
    secrets = SecretStore(cfg, platform)
    reset = False
    try:
        key, _new = load_or_create_data_key(secrets)
    except CryptoError:
        _backup_db("kalit ochilmadi")
        secrets.set_bytes("data_key", None)
        key, _new = load_or_create_data_key(secrets)
        reset = True
    store = Store(paths.db_path(), Cipher(key))
    if not store.verify_key():
        store.close()
        _backup_db("kalit mos emas")
        store = Store(paths.db_path(), Cipher(key))
        reset = True
    return secrets, store, reset


class Brain(QObject):
    say = Signal(str, str)  # ifoda, matn — Yue aytadi
    notify = Signal(str, str)  # Windows bildirishnomasi: sarlavha, matn
    stream_text = Signal(str)  # javobning ko'rinadigan qismi (streaming)
    answered = Signal(object)  # ChatResult (joriy savolga)
    thinking = Signal(bool)  # so'rov ketyapti / tugadi
    tasks_changed = Signal()

    _ask = Signal(int, str, bool)
    _process_queue = Signal()
    _summarize = Signal()

    def __init__(
        self,
        cfg: Config,
        platform: Platform,
        pet_state: Callable[[], PetState],
        lines: Lines | None = None,
    ) -> None:
        super().__init__()
        self.cfg = cfg
        self.platform = platform
        self.pet_state = pet_state
        self.lines = lines or Lines.load()
        self.lines.name_fn = lambda: str(cfg.get("user.name", "") or "")
        self._offline_offered = False  # Online'da internet yo'q: Offline taklifi aytildimi
        self.secrets, self.store, self.memory_reset = open_memory(cfg, platform)
        self.book = TaskBook(self.store)
        self.scheduler = Scheduler(self.store)
        self.break_tracker = BreakTracker(float(cfg.get("reminders.break_min", 90)))
        self.battery = BatteryWatcher()
        self.conv = Conversation()
        self._rid = 0
        self.ask_timeout = ASK_TIMEOUT_S
        self._ask_timer = QTimer(self)
        self._ask_timer.setSingleShot(True)
        self._ask_timer.timeout.connect(self._on_ask_timeout)
        self._last_task_remind = time.time()
        self.mood = Mood()
        self.last_mood = self.mood.current(dt.datetime.now(), active=False)

        self.router = Router([], notify=self._on_provider_failed)
        self.usage = UsageTracker(float(cfg.get("ai.daily_budget_usd", 0) or 0), store=self.store)
        self.service = AiService(
            self.router,
            self.lines,
            self.prompt_context,
            queue=OfflineQueue(store=self.store),
            usage=self.usage,
            online=lambda: self.offline or internet_available(),
            offline_mode=lambda: self.offline,
        )
        self.summarizer = Summarizer(self.store, self.router, self.service._lock, self.usage)
        self.reload_ai()

        self.thread = QThread()
        self.thread.setObjectName("yue-ai")
        self.worker = AiWorker(self.service, self.summarizer)
        self.worker.moveToThread(self.thread)
        self._ask.connect(self.worker.ask)
        self._process_queue.connect(self.worker.process_queue)
        self._summarize.connect(self.worker.summarize)
        self.worker.token.connect(self._on_token)
        self.worker.reset.connect(self._on_reset)
        self.worker.finished.connect(self._on_finished)
        self.worker.queue_answered.connect(self._on_queue_answered)
        self.worker.provider_failed.connect(self._show_provider_failed)
        self.thread.start()

        self._timers: list[QTimer] = []
        self._every(TASK_CHECK_MS, self.check_tasks)
        self._every(MINUTE_MS, self.check_minute)
        self._every(QUEUE_CHECK_MS, self._process_queue.emit)
        self._every(SUMMARY_MS, self._summarize.emit)

    def _every(self, ms: int, fn: Callable[[], None]) -> None:
        timer = QTimer(self)
        timer.timeout.connect(fn)
        timer.start(ms)
        self._timers.append(timer)

    def shutdown(self) -> None:
        for timer in self._timers:
            timer.stop()
        self.worker.cancel()
        self.thread.quit()
        self.thread.wait(3000)
        self.store.close()

    # --- AI sozlash ----------------------------------------------------------------------

    def keys(self) -> tuple[str | None, str | None, str | None]:
        """(Claude, Gemini, OpenRouter) kalitlari."""
        try:
            return (
                self.secrets.get("claude_key"),
                self.secrets.get("gemini_key"),
                self.secrets.get("openrouter_key"),
            )
        except CryptoError:
            log.warning("API kalitlari ochilmadi (DPAPI)")
            return None, None, None

    def has_ai(self) -> bool:
        """Zanjirda kamida bitta maqsad bor (kalit yoki Offline model)."""
        return bool(self.router.targets)

    @property
    def offline(self) -> bool:
        """AI manbasi Offline (faqat Ollama)."""
        return modes.source(self.cfg) == "offline"

    def local_provider(self) -> OllamaProvider | None:
        model = str(self.cfg.get("ai.local_model", "") or "")
        if not model or not self.offline:
            return None
        return OllamaProvider(model)

    def reload_ai(self) -> None:
        """Sozlamalar (kalit, asosiy provayder, rejim) o'zgarganda zanjirni qayta qurish."""
        claude_key, gemini_key, openrouter_key = self.keys()
        local = self.local_provider()
        offline = self.offline
        self.ask_timeout = LOCAL_ASK_TIMEOUT_S if offline else ASK_TIMEOUT_S
        self.service.local_down_until = 0.0  # sozlama o'zgardi — Ollama'ni darhol qayta sinaymiz
        if offline:
            # Offline: bulutga hech narsa ketmaydi
            claude_key = gemini_key = openrouter_key = None
        available = None
        if gemini_key:
            cache = paths.data_dir() / "gemini_models.json"
            try:
                cached = cache.read_text(encoding="utf-8")
                available = set(json.loads(cached).get("models", [])) or None
            except (OSError, ValueError):
                available = None
            threading.Thread(
                target=self._refresh_gemini_models, args=(gemini_key,), daemon=True
            ).start()
        chain = build_chain(
            claude_key,
            gemini_key,
            gemini_paid=bool(self.cfg.get("ai.gemini_paid", False)),
            primary=str(self.cfg.get("ai.primary", "claude")),
            smart=self.cfg.get("ai.mode", "fast") == "smart",
            available_gemini=available,
            offline=offline,
            local=local,
            openrouter_key=openrouter_key,
            openrouter_model=str(self.cfg.get("ai.openrouter_model", "") or ""),
        )
        self.router.set_targets(chain)
        self.router.enable_all()
        log.info("AI zanjiri: %s", ", ".join(t_.key for t_ in chain) or "bo'sh")

    def _refresh_gemini_models(self, key: str) -> None:
        names = available_models(GeminiProvider(key), paths.data_dir() / "gemini_models.json")
        if names is not None:
            missing = [
                t_.key
                for t_ in self.router.targets
                if t_.name == "gemini" and t_.model not in names
            ]
            for k in missing:
                self.router.state[k].disabled_reason = "model"

    def _on_provider_failed(self, provider: str, reason: str) -> None:
        # router ishchi oqimidan chaqiradi → signal orqali UI oqimiga
        self.worker.provider_failed.emit(provider, reason)

    def _show_provider_failed(self, provider: str, reason: str) -> None:
        key = f"notify.{provider}_{'billing' if reason == 'billing' else 'key'}"
        self.notify.emit(t("app.name"), t(key))

    # --- prompt konteksti (ishchi oqimida chaqiriladi) -----------------------------------------

    def prompt_context(self) -> prompt.PromptContext:
        st = self.pet_state()
        battery = self.platform.battery()
        rows = self.store.recent_messages(prompt.HISTORY_LIMIT)
        history = [ChatMessage(r, txt) for r, txt in rows]  # type: ignore[arg-type]
        now = dt.datetime.now()
        self.last_mood = self.mood.current(now, active=True)  # savol hozir yozildi — faol
        return prompt.PromptContext(
            now=now,
            period=st.period,
            outfit=st.outfit,
            accessories=st.overlays,
            activity=st.activity,
            battery=(battery.percent, battery.plugged) if battery else None,
            tasks=self.book.prompt_lines(),
            summary=self.store.get_summary(),
            facts=[f.text for f in self.store.facts()],
            health=[h.text for h in self.store.health()],
            user_name=str(self.cfg.get("user.name", "") or ""),
            humor=str(self.cfg.get("pet.humor", "medium") or "medium"),
            mood=self.last_mood,
            history=history,
        )

    # --- suhbat --------------------------------------------------------------------------

    @property
    def busy(self) -> bool:
        return bool(self.conv.question)

    def ask(self, text: str, enqueue: bool = True) -> bool:
        """Savol yuborish. Har qabul qilingan savol albatta bitta `answered` bilan tugaydi.

        `enqueue=False` — javob olinmasa navbatga qo'yilmaydi (buyruqqa tayyor ibora javob beradi).
        """
        text = text.strip()
        if not text or self.busy:
            return False
        self._rid += 1
        self.conv = Conversation(question=text, started=time.monotonic(), rid=self._rid)
        self.mood.on_user_message(text)
        self.thinking.emit(True)
        self._ask_timer.start(int(self.ask_timeout * 1000))
        self._ask.emit(self._rid, text, enqueue)
        return True

    def cancel(self) -> None:
        """Joriy savolni bekor qilish: UI darhol bo'shaydi (`answered` — "cancelled")."""
        if self.busy:
            self.worker.cancel(self.conv.rid)
            self._end(ChatResult("cancelled"))

    def _on_ask_timeout(self) -> None:
        if not self.busy:
            return
        log.warning("AI so'rovi %.0f s ichida tugamadi — bekor qilindi", self.ask_timeout)
        self.worker.cancel(self.conv.rid)
        self._end(ChatResult("timeout", line=self.lines.pick("timeout")))

    def _end(self, res: ChatResult, question: str = "") -> None:
        """Savol yakuni: holat tozalanadi va UI ga xabar beriladi (xato bo'lsa ham)."""
        self._ask_timer.stop()
        self.conv = Conversation()
        self.thinking.emit(False)
        try:
            if question:
                self._record(question, res)
        except Exception:  # noqa: BLE001 — xotiraga yozilmasa ham suhbat to'xtamasin
            log.exception("javob xotiraga yozilmadi")
        self.answered.emit(res)
        self._maybe_offer_offline(res)

    def _maybe_offer_offline(self, res: ChatResult) -> None:
        """Online'da internet yo'q, Ollama modeli tanlangan — bir marta Offline'ni taklif qiladi."""
        if res.kind == "answer":
            self._offline_offered = False  # internet qaytdi — keyingi uzilishda yana taklif
            return
        if res.kind != "queued" or res.reason != "offline" or self.offline:
            return
        if self._offline_offered or not self.cfg.get("ai.local_model"):
            return
        self._offline_offered = True
        QTimer.singleShot(OFFER_MS, lambda: self.say.emit(*self.lines.pick("offline_taklif")))

    def _on_token(self, piece: str) -> None:
        if not self.busy:
            return
        self.conv.partial.append(piece)
        visible = stream_visible("".join(self.conv.partial))
        if visible:
            self.stream_text.emit(visible)

    def _on_reset(self) -> None:
        self.conv.partial.clear()
        self.stream_text.emit("")

    def _on_finished(self, rid: int, question: str, res: ChatResult) -> None:
        if not self.busy or rid != self.conv.rid:
            return  # bekor qilingan yoki vaqti o'tgan savol — UI allaqachon bo'shatilgan
        self._end(res, question)
        if res.budget_exceeded:
            QTimer.singleShot(8000, lambda: self.say.emit(*self.lines.pick("budget")))

    def _on_queue_answered(self, question: str, res: ChatResult) -> None:
        self._record(question, res)
        if res.kind != "answer" or res.reply is None:
            return
        expr, intro = self.lines.pick("offline_answered")
        text = f"{intro}\n«{question[:80]}»\n{res.reply.text}"
        self.say.emit(res.reply.expression or expr, text)
        self.notify.emit(t("notify.answer_title"), res.reply.text[:200])

    def _record(self, question: str, res: ChatResult) -> None:
        """Javobni xotiraga yozish va AI amallarini (oq ro'yxat) bajarish."""
        if res.kind != "answer" or res.reply is None:
            return
        self.store.add_message("user", question)
        if res.reply.text:
            self.store.add_message("assistant", res.reply.text)
        if res.reply.actions:
            applied = self.book.apply(res.reply.actions)
            if any(a.kind.startswith("task") for a in applied):
                self.tasks_changed.emit()
            if any(a.kind == "done" for a in applied):
                self.mood.on_success()

    # --- kayfiyat ------------------------------------------------------------------------------

    def current_mood(self) -> str:
        active = self.platform.idle_seconds() < ACTIVE_IDLE
        return self.mood.current(dt.datetime.now(), active)

    # --- vazifalar va eslatmalar -------------------------------------------------------------

    def check_tasks(self) -> None:
        for ev in self.scheduler.check():
            task = ev.task.text
            if ev.kind == "due_daily":
                expr, text = self.lines.pick("task_due_daily", task=task)
            elif ev.kind == "late":
                expr, text = self.lines.pick("task_overdue", count=1, list=f"- {task}")
            else:
                expr, text = self.lines.pick("task_due", task=task)
            self.say.emit(expr, text)
            self.notify.emit(t("notify.task_title"), task)

    def remind_open_tasks(self, force: bool = False) -> None:
        tasks, overdue = self.scheduler.open_reminder()
        if not tasks:
            if force:
                self.say.emit(*self.lines.pick("tasks_empty"))
            return
        show = overdue or tasks
        listing = "\n".join(f"- {x.text}" for x in show[:5])
        key = "task_overdue" if overdue else "task_remind"
        self.say.emit(*self.lines.pick(key, count=len(show), list=listing))

    def check_minute(self) -> None:
        now = time.time()
        idle = self.platform.idle_seconds()
        hours = self.break_tracker.update(now, idle)
        if hours is not None:
            h = round(hours * 2) / 2
            self.say.emit(*self.lines.pick("break", hours=f"{h:g}".replace(".", ",")))
        b = self.platform.battery() if self.cfg.get("reminders.battery", True) else None
        event = self.battery.update(b)
        if event and b is not None:
            self.say.emit(*self.lines.pick("battery", event, percent=b.percent))
        every = float(self.cfg.get("reminders.tasks_every_min", 120) or 0) * 60
        if every > 0 and now - self._last_task_remind >= every and idle < ACTIVE_IDLE:
            self._last_task_remind = now
            self.remind_open_tasks()

    # --- xotira boshqaruvi ---------------------------------------------------------------------

    def clear_memory(self) -> None:
        self.store.clear_memory()
        self.say.emit(*self.lines.pick("memory_cleared"))
