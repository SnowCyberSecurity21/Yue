import os
import random
import threading

import pytest

from tests.fakes import FakeClock, FakeProvider, err
from yue.ai.router import OfflineQueue, Router
from yue.ai.usage import UsageTracker
from yue.memory.crypto import Cipher
from yue.memory.store import MAX_FACTS, Store
from yue.memory.summarizer import KEEP_RECENT, MIN_BATCH, Summarizer
from yue.platform import Battery
from yue.reminders import BatteryWatcher, BreakTracker


@pytest.fixture
def store():
    s = Store(":memory:", Cipher(os.urandom(32)))
    yield s
    s.close()


def fill(store, n):
    for i in range(n):
        store.add_message("user" if i % 2 == 0 else "assistant", f"xabar {i}")


def test_history_and_order(store):
    fill(store, 5)
    assert store.recent_messages(3) == [
        ("user", "xabar 2"),
        ("assistant", "xabar 3"),
        ("user", "xabar 4"),
    ]


def test_facts_dedup_and_cap(store):
    assert store.add_fact("Ismi Aziz") and not store.add_fact(" ismi aziz ")
    for i in range(MAX_FACTS + 5):
        store.add_fact(f"fakt {i}")
    facts = store.facts()
    assert len(facts) == MAX_FACTS and facts[-1].text == f"fakt {MAX_FACTS + 4}"


def test_clear_memory_keeps_tasks(store):
    fill(store, 3)
    store.add_fact("f")
    store.add_health("h")
    store.set_summary("s")
    store.add_task("vazifa")
    store.clear_memory()
    assert store.recent_messages() == [] and store.facts() == [] and store.health() == []
    assert store.get_summary() == "" and len(store.tasks()) == 1


def test_export_is_plain(store):
    store.add_fact("Ismi Aziz")
    store.add_task("Dori", "2026-10-14 09:00")
    data = store.export()
    assert data["facts"] == ["Ismi Aziz"] and data["tasks"][0]["text"] == "Dori"
    assert "Ismi Aziz" in store.export_json()


def test_queue_and_usage_persist(store):
    clock = FakeClock()
    q = OfflineQueue(store=store, clock=clock)
    item = q.add("Oflayn savol")
    q2 = OfflineQueue(store=store, clock=clock)  # dastur qayta ochildi
    assert len(q2) == 1 and q2._items[0].text == "Oflayn savol"
    q2.done(q2._items[0])
    assert store.queue_all() == [] and item.id >= 1

    from yue.ai.providers.base import Usage

    u = UsageTracker(store=store)
    u.add("claude:claude-haiku-5-5", Usage(1000, 100))
    u2 = UsageTracker(store=store)
    assert u2.day.requests == 1 and u2.day.cost > 0


# --- xulosa ---------------------------------------------------------------------------------


def make_router(*providers):
    clock = FakeClock()
    return Router(list(providers), clock=clock, sleep=clock.sleep, rng=random.Random(0))


def test_summarizer_waits_for_enough_messages(store):
    haiku = FakeProvider("claude", "claude-haiku-5-5", script=["- Kod haqida gaplashdi"])
    s = Summarizer(store, make_router(haiku), threading.Lock())
    fill(store, KEEP_RECENT + MIN_BATCH - 1)
    assert s.maybe_run() is False and not haiku.calls


def test_summarizer_runs_on_private_target_and_prunes(store):
    gemini_free = FakeProvider("gemini", "gemini-3.1-flash-lite", private=False)
    haiku = FakeProvider(
        "claude", "claude-haiku-5-5", script=["**- 13.10: Python haqida gaplashdi**"]
    )
    s = Summarizer(store, make_router(haiku, gemini_free), threading.Lock())
    fill(store, KEEP_RECENT + MIN_BATCH)
    assert s.maybe_run() is True
    assert not gemini_free.calls  # bepul Gemini'ga suhbatlar yuborilmaydi
    assert "xabar 0" in haiku.calls[0][1][0].text
    assert store.get_summary() == "- 13.10: Python haqida gaplashdi"
    assert store.count_unsummarized() == KEEP_RECENT


def test_summarizer_skips_without_private_target(store):
    gemini_free = FakeProvider("gemini", "gemini-3.1-flash-lite", private=False)
    s = Summarizer(store, make_router(gemini_free), threading.Lock())
    fill(store, KEEP_RECENT + MIN_BATCH)
    assert s.maybe_run() is False and not gemini_free.calls


def test_summarizer_does_not_compete_with_chat(store):
    haiku = FakeProvider("claude", "claude-haiku-5-5")
    lock = threading.Lock()
    s = Summarizer(store, make_router(haiku), lock)
    fill(store, KEEP_RECENT + MIN_BATCH)
    with lock:
        assert s.maybe_run() is False
    assert not haiku.calls


def test_summarizer_delayed_when_chain_busy(store):
    haiku = FakeProvider("claude", "claude-haiku-5-5", script=[err("rate_limit")])
    sonnet = FakeProvider("claude", "claude-sonnet-5-5")
    r = make_router(haiku, sonnet)
    r.ask(lambda t: ([], []))  # haiku cooldown'ga tushdi, sonnet javob berdi
    r.state["claude:claude-sonnet-5-5"].cooldown_until = r.clock() + 100
    s = Summarizer(store, r, threading.Lock())
    fill(store, KEEP_RECENT + MIN_BATCH)
    assert s.maybe_run() is False


# --- tanaffus va batareya --------------------------------------------------------------------


def test_break_after_90_minutes_active():
    b = BreakTracker(90)
    t = 0.0
    hits = []
    for _ in range(200):  # 200 daqiqa uzluksiz ish
        h = b.update(t, idle_seconds=10)
        if h:
            hits.append(round(t / 60))
        t += 60
    assert hits == [90, 180]


def test_break_resets_after_away():
    b = BreakTracker(90)
    for m in range(80):
        assert b.update(m * 60, 5) is None
    b.update(80 * 60, idle_seconds=6 * 60)  # 6 daqiqa yo'q edi
    for m in range(81, 160):
        assert b.update(m * 60, 5) is None


def test_battery_events():
    w = BatteryWatcher()
    seq = [
        (Battery(50, True), None),
        (Battery(50, False), "unplug"),
        (Battery(25, False), None),
        (Battery(20, False), "low"),
        (Battery(18, False), None),
        (Battery(10, False), "critical"),
        (Battery(9, False), None),
        (Battery(9, True), "plug"),
        (Battery(100, True), "full"),
        (Battery(100, True), None),
    ]
    assert [w.update(b) for b, _ in seq] == [e for _, e in seq]
    assert w.update(None) is None
