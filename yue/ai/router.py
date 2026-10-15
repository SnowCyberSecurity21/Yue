"""Maqsadlar zanjiri: "Yue hamisha javob beradi".

Standart tartib ("Asosiy: Claude", rejim "Aqlliroq"; boshqa tartiblar — `yue.ai.factory`):
  1. claude-sonnet-5-5
  2. claude-haiku-5-5 (zaxira)
  3. gemini-3.8-flash → gemini-3.6-flash → gemini-3.5-flash-lite → gemini-3.1-flash-lite
Kaliti yo'q provayder zanjirga umuman qo'shilmaydi. Offline model (Ollama) yoqilgan bo'lsa — eng
oxirgi zaxira: internet uzilib, bulut maqsadlari `network` bersa ham, navbatdan oldin u sinaladi.
Lokal maqsadga birinchi token byudjeti tegmaydi (model yuklanishi sekin), o'z vaqt chegarasi bor.

Xatolar (har maqsad uchun holat: cooldown_until, failures, disabled_reason):
- 429: retry-after / RetryInfo bo'yicha cooldown (bo'lmasa 60 s), darhol keyingi maqsad.
  Kunlik kvota — keyingi Tinch okeani yarim tunigacha.
- 5xx/529/timeout: 1 marta qayta urinish (0.8–2 s, jitter), keyin keyingi maqsad.
- ulanish xatosi: keyingi maqsad; hammasi tarmoq xatosi bo'lsa — `Offline` (navbatga).
- 401/403/402: maqsad o'chiriladi, bir marta o'zbekcha bildirishnoma.
- 400 / xavfsizlik / bo'sh javob: logga (matnsiz), keyingi maqsad.
Foydalanuvchi hech qachon xom xato matnini ko'rmaydi — natija turi o'zbekcha iboraga aylanadi.
"""

from __future__ import annotations

import datetime as dt
import logging
import random
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from yue.ai.providers.base import ChatMessage, Provider, ProviderError, SystemBlock, Usage

log = logging.getLogger(__name__)

DEFAULT_COOLDOWN = 60.0
TRANSIENT_COOLDOWN = 30.0
FIRST_TOKEN_BUDGET = 25.0
ATTEMPT_TIMEOUT = 20.0
RETRY_DELAY = (0.8, 2.0)
LOCAL_TIMEOUT = 90.0  # offline model: diskdan yuklanish + CPU da sekin javob

PromptBuilder = Callable[[Provider], tuple[Sequence[SystemBlock], Sequence[ChatMessage]]]


# --- Tinch okeani vaqti (Gemini kunlik kvotasi shu bo'yicha yangilanadi) --------------------


def _nth_sunday(year: int, month: int, n: int) -> dt.date:
    d = dt.date(year, month, 1)
    d += dt.timedelta(days=(6 - d.weekday()) % 7)
    return d + dt.timedelta(weeks=n - 1)


def pacific_offset(utc: dt.datetime) -> dt.timedelta:
    """AQSh qoidasi (2007-yildan): yozgi vaqt mart 2-yakshanba → noyabr 1-yakshanba, 02:00 da."""
    y = utc.year
    start = dt.datetime.combine(_nth_sunday(y, 3, 2), dt.time(10, 0), tzinfo=dt.UTC)  # 02:00 PST
    end = dt.datetime.combine(_nth_sunday(y, 11, 1), dt.time(9, 0), tzinfo=dt.UTC)  # 02:00 PDT
    return dt.timedelta(hours=-7) if start <= utc < end else dt.timedelta(hours=-8)


def next_pacific_midnight(now: float) -> float:
    """Keyingi Tinch okeani yarim tuni (unix vaqt)."""
    utc = dt.datetime.fromtimestamp(now, dt.UTC)
    local = utc + pacific_offset(utc)
    midnight_local = dt.datetime.combine(local.date() + dt.timedelta(days=1), dt.time(0, 0))
    # Yarim tundagi siljish (DST o'tishi yarim tunda bo'lmaydi, lekin baribir qayta hisoblaymiz)
    guess = (midnight_local - pacific_offset(utc)).replace(tzinfo=dt.UTC)
    exact = (midnight_local - pacific_offset(guess)).replace(tzinfo=dt.UTC)
    return exact.timestamp() + 5.0  # bir necha soniya zaxira


# --- holat va natija ------------------------------------------------------------------------


@dataclass
class TargetState:
    cooldown_until: float = 0.0
    failures: int = 0
    disabled_reason: str | None = None
    auth_notified: bool = False


Outcome = Literal["ok", "offline", "busy", "failed", "no_targets"]


@dataclass
class Answer:
    outcome: Outcome
    text: str = ""
    target: str = ""
    private: bool = False
    usage: Usage | None = None
    retry_at: float | None = None  # busy/offline: qachon qayta urinish kerak
    errors: list[str] = field(default_factory=list)  # faqat turlar, matnsiz


class Cancelled(Exception):
    pass


class Router:
    def __init__(
        self,
        targets: Sequence[Provider],
        *,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        rng: random.Random | None = None,
        notify: Callable[[str, str], None] | None = None,
        first_token_budget: float = FIRST_TOKEN_BUDGET,
        attempt_timeout: float = ATTEMPT_TIMEOUT,
    ) -> None:
        self.targets: list[Provider] = list(targets)
        self.state: dict[str, TargetState] = {t.key: TargetState() for t in self.targets}
        self.clock = clock
        self.sleep = sleep
        self.rng = rng or random.Random()
        self.notify = notify or (lambda provider, reason: None)
        self.first_token_budget = first_token_budget
        self.attempt_timeout = attempt_timeout
        self._lock = threading.Lock()

    # --- holat ---------------------------------------------------------------------------

    def set_targets(self, targets: Sequence[Provider]) -> None:
        with self._lock:
            old = self.state
            self.targets = list(targets)
            self.state = {t.key: old.get(t.key, TargetState()) for t in self.targets}

    def usable(self, now: float | None = None) -> list[Provider]:
        now = self.clock() if now is None else now
        return [
            t
            for t in self.targets
            if self.state[t.key].disabled_reason is None and self.state[t.key].cooldown_until <= now
        ]

    def earliest_ready(self) -> float | None:
        times = [s.cooldown_until for s in self.state.values() if s.disabled_reason is None]
        return min(times) if times else None

    def cheapest(self) -> Provider | None:
        """Xulosa va tarjima uchun: eng arzon ishlayotgan maqsad (Gemini flash-lite → Haiku)."""
        order = [
            "gemini:gemini-3.1-flash-lite",
            "gemini:gemini-3.5-flash-lite",
            "claude:claude-haiku-5-5",
            "gemini:gemini-3.6-flash",
            "gemini:gemini-3.8-flash",
        ]
        usable = {t.key: t for t in self.usable()}
        for key in order:
            if key in usable:
                return usable[key]
        return next(iter(usable.values()), None)

    def busy_ratio(self) -> float:
        """Zanjirning qancha qismi cooldown'da (xulosa fon ishini kechiktirish uchun)."""
        live = [s for s in self.state.values() if s.disabled_reason is None]
        if not live:
            return 1.0
        now = self.clock()
        return sum(1 for s in live if s.cooldown_until > now) / len(live)

    def enable_all(self) -> None:
        """Sozlamalarda kalit yangilanganda o'chirilgan maqsadlarni qayta yoqish."""
        for s in self.state.values():
            s.disabled_reason = None
            s.auth_notified = False
            s.failures = 0

    # --- so'rov ----------------------------------------------------------------------------

    def ask(
        self,
        build: PromptBuilder,
        on_token: Callable[[str], None] | None = None,
        on_reset: Callable[[], None] | None = None,
        max_tokens: int = 1024,
        targets: Sequence[Provider] | None = None,
        cancel: threading.Event | None = None,
    ) -> Answer:
        """Zanjir bo'ylab birinchi muvaffaqiyatli javobni olish."""
        on_token = on_token or (lambda s: None)
        on_reset = on_reset or (lambda: None)
        chain = list(targets) if targets is not None else list(self.targets)
        if not chain:
            return Answer("no_targets")

        started = self.clock()
        errors: list[str] = []
        tried = 0

        for target in chain:
            if cancel is not None and cancel.is_set():
                raise Cancelled
            st = self.state.setdefault(target.key, TargetState())
            now = self.clock()
            if st.disabled_reason is not None or st.cooldown_until > now:
                continue
            local = bool(getattr(target, "local", False))
            remaining = self.first_token_budget - (now - started)
            if remaining <= 1.0 and tried > 0 and not local:
                if "budget" not in errors:
                    errors.append("budget")
                continue  # bulut maqsadlari o'tkaziladi, lokal zaxira baribir sinaladi
            tried += 1
            for attempt in (1, 2):
                emitted: list[str] = []
                try:
                    if local:
                        timeout = LOCAL_TIMEOUT
                    else:
                        timeout = max(3.0, min(self.attempt_timeout, remaining))
                    system, messages = build(target)
                    for piece in target.stream(system, messages, max_tokens, timeout):
                        if cancel is not None and cancel.is_set():
                            raise Cancelled
                        emitted.append(piece)
                        on_token(piece)
                    st.failures = 0
                    return Answer(
                        "ok",
                        text="".join(emitted),
                        target=target.key,
                        private=target.private,
                        usage=target.last_usage,
                        errors=errors,
                    )
                except ProviderError as exc:
                    errors.append(f"{target.key}:{exc.kind}")
                    log.info(
                        "AI maqsad xatosi: %s %s (status=%s)", target.key, exc.kind, exc.status
                    )
                    if emitted:
                        on_reset()  # yarim chiqqan javobni pufakdan tozalash
                    if exc.kind == "transient" and attempt == 1 and not local:
                        delay = self.rng.uniform(*RETRY_DELAY)
                        if (self.clock() - started) + delay < self.first_token_budget:
                            self.sleep(delay)
                            remaining = self.first_token_budget - (self.clock() - started)
                            continue
                    self._penalize(target, exc)
                    break
        if all(self.state[t.key].disabled_reason for t in chain):
            return Answer("no_targets", errors=errors)
        # Lokal zaxira (o'rnatilmagan model va h.k.) bulut natijasini o'zgartirmaydi: internet
        # yo'q bo'lsa — baribir navbatga. Zanjirda faqat lokal bo'lsa — uning xatolari hisobga.
        has_cloud = any(not getattr(t, "local", False) for t in chain)
        counted = [e for e in errors if not (has_cloud and e.startswith("ollama:"))]
        kinds = {e.rsplit(":", 1)[-1] for e in counted}
        if kinds & {"bad_request", "safety", "empty"}:
            return Answer("failed", errors=errors)
        if "network" in kinds:
            return Answer("offline", errors=errors)
        # Hamma maqsad limit/cooldown'da yoki vaqtincha ishlamayapti — navbatga, keyinroq javob
        return Answer("busy", retry_at=self.earliest_ready(), errors=errors)

    def _penalize(self, target: Provider, exc: ProviderError) -> None:
        st = self.state[target.key]
        now = self.clock()
        if exc.kind == "rate_limit":
            st.cooldown_until = now + (exc.retry_after or DEFAULT_COOLDOWN)
        elif exc.kind == "quota_daily":
            st.cooldown_until = next_pacific_midnight(now)
        elif exc.kind == "transient":
            st.failures += 1
            if st.failures >= 2:
                st.cooldown_until = now + TRANSIENT_COOLDOWN
        elif exc.kind == "auth":
            st.disabled_reason = "billing" if exc.detail == "billing" else "auth"
            # Bir provayderning hamma modellari uchun bitta bildirishnoma
            same = [self.state[t.key] for t in self.targets if t.name == target.name]
            if not any(s.auth_notified for s in same):
                self.notify(target.name, st.disabled_reason)
            for t in self.targets:
                if t.name == target.name:
                    self.state[t.key].disabled_reason = st.disabled_reason
                    self.state[t.key].auth_notified = True
        elif exc.kind == "bad_request" and exc.status == 404:
            st.disabled_reason = "model"


# --- oflayn navbat ----------------------------------------------------------------------------


@dataclass
class QueuedQuestion:
    id: int
    text: str
    created: float
    attempts: int = 0
    next_try: float = 0.0


class OfflineQueue:
    """Javob ololmagan savollar. Saqlash (shifrlangan SQLite) 3-bosqichda `store` orqali ulanadi.

    `store` — ixtiyoriy obyekt: `queue_add(text, created) -> id`, `queue_all() -> list`,
    `queue_remove(id)`.
    """

    CHECK_MIN, CHECK_MAX = 30.0, 60.0

    def __init__(self, store=None, clock: Callable[[], float] = time.time, rng=None) -> None:
        self.store = store
        self.clock = clock
        self.rng = rng or random.Random()
        self._items: list[QueuedQuestion] = []
        self._next_id = 1
        if store is not None:
            for qid, text, created in store.queue_all():
                self._items.append(QueuedQuestion(qid, text, created))
                self._next_id = max(self._next_id, qid + 1)

    def __len__(self) -> int:
        return len(self._items)

    def add(self, text: str, retry_at: float | None = None) -> QueuedQuestion:
        now = self.clock()
        if self.store is not None:
            qid = self.store.queue_add(text, now)
        else:
            qid = self._next_id
        self._next_id = max(self._next_id, qid + 1)
        item = QueuedQuestion(qid, text, now, next_try=retry_at or now + self._interval())
        self._items.append(item)
        return item

    def _interval(self) -> float:
        return self.rng.uniform(self.CHECK_MIN, self.CHECK_MAX)

    def due(self) -> list[QueuedQuestion]:
        now = self.clock()
        return [q for q in self._items if q.next_try <= now]

    def postpone(self, item: QueuedQuestion, retry_at: float | None = None) -> None:
        item.attempts += 1
        item.next_try = max(retry_at or 0.0, self.clock() + self._interval())

    def done(self, item: QueuedQuestion) -> None:
        self._items = [q for q in self._items if q.id != item.id]
        if self.store is not None:
            self.store.queue_remove(item.id)
