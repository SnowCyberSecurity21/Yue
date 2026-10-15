import datetime as dt
import os
import random

import pytest

from tests.fakes import FakeClock, FakeProvider
from yue.ai import prompt
from yue.ai.router import Router
from yue.ai.service import AiService
from yue.lines import Lines
from yue.memory.crypto import Cipher
from yue.memory.store import Store
from yue.tasks.scheduler import Scheduler
from yue.tasks.store import TaskBook
from yue.tasks.timeparse import (
    describe_due,
    is_overdue,
    next_daily,
    parse_due,
    parse_hhmm,
    parse_user_time,
)

NOW = dt.datetime(2026, 10, 13, 21, 30)  # seshanba kechqurun


@pytest.fixture
def store():
    s = Store(":memory:", Cipher(os.urandom(32)))
    yield s
    s.close()


# --- vaqt hisoblash -------------------------------------------------------------------------


def test_parse_formats():
    assert parse_due("2026-10-14 09:00") == dt.datetime(2026, 10, 14, 9, 0)
    assert parse_due("ertaga") is None and parse_due(None) is None
    assert parse_hhmm("8:05") == (8, 5) and parse_hhmm("24:00") is None


def test_next_daily():
    assert next_daily("22:00", NOW) == dt.datetime(2026, 10, 13, 22, 0)
    assert next_daily("08:00", NOW) == dt.datetime(2026, 10, 14, 8, 0)


@pytest.mark.parametrize(
    ("due", "repeat", "text"),
    [
        ("2026-10-13 23:00", None, "bugun 23:00"),
        ("2026-10-14 09:00", None, "ertaga 09:00"),
        ("2026-10-12 09:00", None, "kecha 09:00"),
        ("2026-11-02 18:30", None, "2-noyabr 18:30"),
        ("2027-01-05 10:00", None, "5-yanvar 2027-yil 10:00"),
        ("08:00", "har_kuni", "har kuni 08:00"),
        (None, None, ""),
    ],
)
def test_describe_due(due, repeat, text):
    assert describe_due(due, repeat, NOW) == text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", (None, None)),
        ("23:00", ("2026-10-13 23:00", None)),
        ("20:00", ("2026-10-14 20:00", None)),  # o'tib ketgan — ertaga
        ("ertaga 9:00", ("2026-10-14 09:00", None)),
        ("indinga 10:15", ("2026-10-15 10:15", None)),
        ("har kuni 08:00", ("08:00", "har_kuni")),
        ("30 daqiqadan keyin", ("2026-10-13 22:00", None)),
        ("2 soatdan keyin", ("2026-10-13 23:30", None)),
        ("2026-12-31 23:59", ("2026-12-31 23:59", None)),
        ("qachondir", None),
    ],
)
def test_parse_user_time(text, expected):
    assert parse_user_time(text, NOW) == expected


def test_overdue():
    assert is_overdue("2026-10-13 09:00", None, NOW)
    assert not is_overdue("2026-10-14 09:00", None, NOW)
    assert not is_overdue("08:00", "har_kuni", NOW)


# --- rejalashtiruvchi -------------------------------------------------------------------------


def test_timed_task_fires_once_at_due(store):
    book = TaskBook(store, now=lambda: NOW)
    book.add("Dori ichish", "2026-10-14 09:00")
    sch = Scheduler(store)
    assert sch.check(dt.datetime(2026, 10, 14, 8, 59)) == []
    ev = sch.check(dt.datetime(2026, 10, 14, 9, 0, 10))
    assert [(e.kind, e.task.text) for e in ev] == [("due", "Dori ichish")]
    assert sch.check(dt.datetime(2026, 10, 14, 9, 1)) == []  # takror eslatmaydi
    tasks, overdue = sch.open_reminder(dt.datetime(2026, 10, 14, 12, 0))
    assert len(tasks) == 1 and len(overdue) == 1  # bajarilmaguncha ochiq


def test_missed_task_fires_late_on_startup(store):
    store.add_task("Hisobot", "2026-10-13 10:00")
    ev = Scheduler(store).check(NOW)
    assert [e.kind for e in ev] == ["late"]


def test_daily_repeats_every_day(store):
    tid = store.add_task("Suv ichish", "08:00", "har_kuni")
    # 07:00 da yaratilgan deb hisoblaymiz
    store._db.execute("UPDATE tasks SET created=?", (dt.datetime(2026, 10, 14, 7, 0).timestamp(),))
    sch = Scheduler(store)
    fired = []
    t = dt.datetime(2026, 10, 14, 7, 59)
    for _ in range(3 * 24 * 4):  # 3 kun, 15 daqiqalik qadam
        fired += [(t.date(), e.kind) for e in sch.check(t)]
        t += dt.timedelta(minutes=15)
    assert fired == [
        (dt.date(2026, 10, 14), "due_daily"),
        (dt.date(2026, 10, 15), "due_daily"),
        (dt.date(2026, 10, 16), "due_daily"),
    ]
    store.complete_task(tid)
    assert sch.check(dt.datetime(2026, 10, 17, 8, 0)) == []


def test_daily_created_after_time_waits_for_tomorrow(store):
    store.add_task("Vitamin", "08:00", "har_kuni")  # hozir (test vaqti) yaratildi
    now = dt.datetime.now()
    occ = now.replace(hour=8, minute=0, second=0, microsecond=0)
    sch = Scheduler(store)
    if now > occ:
        assert sch.check(now) == []


def test_daily_missed_long_ago_is_skipped(store):
    store.add_task("Suv", "08:00", "har_kuni")
    store._db.execute("UPDATE tasks SET created=?", (dt.datetime(2026, 10, 1).timestamp(),))
    assert Scheduler(store).check(dt.datetime(2026, 10, 14, 15, 0)) == []  # 6 soatdan oshgan


def test_done_and_deleted_tasks_do_not_fire(store):
    a = store.add_task("A", "2026-10-14 09:00")
    b = store.add_task("B", "2026-10-14 09:00")
    store.complete_task(a)
    store.delete_task(b)
    assert Scheduler(store).check(dt.datetime(2026, 10, 14, 9, 30)) == []


# --- AI amallari -----------------------------------------------------------------------------


def test_book_applies_whitelisted_actions(store):
    from yue.ai.parse import parse_reply

    book = TaskBook(store, now=lambda: NOW)
    tid = store.add_task("Eski vazifa")
    r = parse_reply(
        "[happy] Bo'ldi.\n"
        '<vazifa vaqt="2026-10-14 09:00">Dori ichish</vazifa>'
        '<vazifa vaqt="08:00" takror="har_kuni">Suv ichish</vazifa>'
        f"<bajarildi>{tid}</bajarildi><bajarildi>999</bajarildi>"
        "<eslab>Ismi Aziz</eslab><salomatlik>Qand kasalligi bor</salomatlik>"
    )
    applied = book.apply(r.actions)
    assert [a.kind for a in applied] == ["task_added", "task_added", "task_done", "fact", "health"]
    assert [t.text for t in store.tasks()] == ["Dori ichish", "Suv ichish"]
    assert store.facts()[0].text == "Ismi Aziz" and store.health()[0].text == "Qand kasalligi bor"
    lines = book.prompt_lines()
    assert lines[0].startswith("#2: Dori ichish — ertaga 09:00")
    assert lines[1].endswith("har kuni 08:00")


def test_duplicate_task_not_added_twice(store):
    book = TaskBook(store, now=lambda: NOW)
    book.add("Dori ichish", "2026-10-14 09:00")
    book.add("dori  ichish", "2026-10-14 09:00")
    assert len(store.tasks()) == 1


def test_end_to_end_remind_tomorrow_9(store):
    """Mezon: "ertaga soat 9 da dori ichishni eslat" → aniq vaqtda eslatma."""
    clock = FakeClock()
    ai = FakeProvider(
        "claude",
        "claude-haiku-5-5",
        script=[
            '[smug] Yozdim. Ertaga soat 09:00 da eslataman. <vazifa vaqt="2026-10-14 09:00">Dori ichish</vazifa>'
        ],
    )
    router = Router([ai], clock=clock, sleep=clock.sleep, rng=random.Random(0))
    book = TaskBook(store, now=lambda: NOW)
    ctx = lambda: prompt.PromptContext(now=NOW, tasks=book.prompt_lines())  # noqa: E731
    svc = AiService(router, Lines.load(), ctx)
    res = svc.chat("ertaga soat 9 da dori ichishni eslat")
    sent_state = ai.calls[0][0][-1].text
    assert "2026-10-13 21:30" in sent_state  # model hozirgi vaqtni biladi
    book.apply(res.reply.actions)
    sch = Scheduler(store)
    assert sch.check(dt.datetime(2026, 10, 14, 8, 59, 45)) == []
    ev = sch.check(dt.datetime(2026, 10, 14, 9, 0, 5))
    assert len(ev) == 1 and ev[0].task.text == "Dori ichish" and ev[0].kind == "due"
