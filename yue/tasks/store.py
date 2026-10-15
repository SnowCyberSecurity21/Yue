"""Vazifalar va xotira amallari: AI teglarini (oq ro'yxat) omborga qo'llash, prompt uchun ro'yxat.

Model faqat shu amallarni so'ray oladi: vazifa qo'shish/bajarildi/o'chirish, fakt va sog'liq
yozuvi. Boshqa hech narsa bajarilmaydi.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from yue.ai.parse import Action
from yue.memory.store import Store, TaskRow
from yue.tasks.timeparse import DAILY, describe_due, is_overdue, parse_due, parse_hhmm

log = logging.getLogger(__name__)

MAX_OPEN_TASKS = 200


@dataclass(frozen=True)
class Applied:
    kind: str  # task_added / task_done / task_deleted / fact / health
    task: TaskRow | None = None
    text: str = ""


class TaskBook:
    def __init__(self, store: Store, now: Callable[[], dt.datetime] = dt.datetime.now) -> None:
        self.store = store
        self.now = now

    # --- AI amallari -------------------------------------------------------------------------

    def apply(self, actions: Sequence[Action]) -> list[Applied]:
        out: list[Applied] = []
        for a in actions:
            try:
                res = self._apply_one(a)
            except Exception:  # noqa: BLE001 — bitta amal xatosi qolganlarini to'xtatmasin
                log.exception("AI amali bajarilmadi: %s", a.kind)
                continue
            if res is not None:
                out.append(res)
        return out

    def _apply_one(self, a: Action) -> Applied | None:
        if a.kind == "task":
            return self.add(a.text, a.when, a.repeat)
        if a.kind == "done" and a.task_id is not None:
            t = self.store.task(a.task_id)
            if t and self.store.complete_task(a.task_id):
                return Applied("task_done", t)
            return None
        if a.kind == "delete" and a.task_id is not None:
            t = self.store.task(a.task_id)
            if t and self.store.delete_task(a.task_id):
                return Applied("task_deleted", t)
            return None
        if a.kind == "remember":
            return Applied("fact", text=a.text) if self.store.add_fact(a.text) else None
        if a.kind == "health":
            return Applied("health", text=a.text) if self.store.add_health(a.text) else None
        return None

    def add(self, text: str, due: str | None = None, repeat: str | None = None) -> Applied | None:
        text = " ".join(text.split())[:300]
        if not text or len(self.store.tasks()) >= MAX_OPEN_TASKS:
            return None
        if repeat == DAILY:
            hm = parse_hhmm(due)
            due = f"{hm[0]:02d}:{hm[1]:02d}" if hm else None
            if due is None:
                repeat = None
        elif due is not None and parse_due(due) is None:
            due = None
        # Bir xil ochiq vazifa ikki marta qo'shilmasin
        for t in self.store.tasks():
            if t.text.casefold() == text.casefold() and t.due == due and t.repeat == repeat:
                return Applied("task_added", t)
        tid = self.store.add_task(text, due, repeat)
        return Applied("task_added", self.store.task(tid))

    # --- ko'rinish ---------------------------------------------------------------------------

    def describe(self, t: TaskRow, now: dt.datetime | None = None) -> str:
        now = now or self.now()
        when = describe_due(t.due, t.repeat, now)
        line = f"#{t.id}: {t.text}"
        if when:
            line += f" — {when}"
        if is_overdue(t.due, t.repeat, now):
            line += " (muddati o'tgan)"
        return line

    def prompt_lines(self, limit: int = 30) -> list[str]:
        now = self.now()
        return [self.describe(t, now) for t in self.store.tasks()[:limit]]
