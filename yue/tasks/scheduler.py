"""Vazifalar rejalashtiruvchisi: har 15 s tekshiriladi (Qt taymer `app.py` da).

- bir martalik vazifa: muddati kelganda bir marta eslatiladi (`fired` = muddat); bajarilmaguncha
  ochiq va "muddati o'tgan" bo'lib qoladi;
- har kunlik: har kuni HH:MM da bir marta (`fired` = shu kungi vaqt). Dastur yopiq bo'lib, vaqt
  o'tib ketgan bo'lsa — `DAILY_GRACE` ichida ochilsa, kech bo'lsa ham eslatiladi;
- ochiq vazifalar har N daqiqada eslatiladi (`open_reminder`).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from yue.memory.store import Store, TaskRow
from yue.tasks.timeparse import DAILY, fmt_due, is_overdue, occurrence_on, parse_due

DAILY_GRACE = dt.timedelta(hours=6)
LATE = dt.timedelta(minutes=10)


@dataclass(frozen=True)
class DueEvent:
    kind: Literal["due", "due_daily", "late"]
    task: TaskRow


class Scheduler:
    def __init__(self, store: Store, now: Callable[[], dt.datetime] = dt.datetime.now) -> None:
        self.store = store
        self.now = now

    def check(self, now: dt.datetime | None = None) -> list[DueEvent]:
        now = now or self.now()
        events: list[DueEvent] = []
        for t in self.store.tasks():
            if t.repeat == DAILY:
                occ = occurrence_on(now.date(), t.due or "")
                if occ is None:
                    continue
                key = fmt_due(occ)
                if now >= occ and t.fired != key:
                    self.store.set_task_fired(t.id, key)
                    # Vazifa qo'shilishidan oldingi vaqt (08:00 ga 10:00 da) — bugun emas
                    created = dt.datetime.fromtimestamp(t.created)
                    if now - occ <= DAILY_GRACE and created <= occ:
                        events.append(DueEvent("due_daily", t))
                continue
            due = parse_due(t.due)
            if due is None or now < due or t.fired == t.due:
                continue
            self.store.set_task_fired(t.id, t.due or "")
            events.append(DueEvent("late" if now - due > LATE else "due", t))
        return events

    def open_reminder(self, now: dt.datetime | None = None) -> tuple[list[TaskRow], list[TaskRow]]:
        """(ochiq vazifalar, ulardan muddati o'tganlari)."""
        now = now or self.now()
        tasks = self.store.tasks()
        overdue = [t for t in tasks if is_overdue(t.due, t.repeat, now)]
        return tasks, overdue
