import datetime as dt
import random

import pytest

from tests.fakes import FakeClock, Partial, chain, err
from yue.ai.router import (
    DEFAULT_COOLDOWN,
    OfflineQueue,
    Router,
    next_pacific_midnight,
    pacific_offset,
)


def build_prompt(target):
    return ([], [])


def make(clock=None, notify=None, **scripts):
    clock = clock or FakeClock()
    p = chain(clock=clock, **scripts)
    order = [p["haiku"], p["g38"], p["g36"], p["g35"], p["g31"], p["sonnet"]]
    r = Router(order, clock=clock, sleep=clock.sleep, rng=random.Random(0), notify=notify)
    return r, p, clock


def used(p):
    return [k for k, v in p.items() if v.calls]


def utc(*a):
    return dt.datetime(*a, tzinfo=dt.UTC).timestamp()


# --- zanjir tartibi ---------------------------------------------------------------------------


def test_first_target_answers():
    r, p, _ = make()
    ans = r.ask(build_prompt)
    assert ans.outcome == "ok" and ans.target == "claude:claude-haiku-5-5"
    assert used(p) == ["haiku"]


def test_chain_order_on_failures():
    r, p, _ = make(
        haiku=[err("rate_limit", status=429)],
        g38=[err("rate_limit", status=429)],
        g36=[err("quota_daily", status=429)],
        g35=[err("bad_request", status=400)],
    )
    ans = r.ask(build_prompt)
    assert ans.outcome == "ok" and ans.target == "gemini:gemini-3.1-flash-lite"
    assert used(p) == ["haiku", "g38", "g36", "g35", "g31"]


def test_tokens_streamed_to_callback():
    r, _, _ = make()
    got = []
    ans = r.ask(build_prompt, on_token=got.append)
    assert "".join(got) == ans.text and len(got) > 1


# --- 429 va cooldown ----------------------------------------------------------------------------


def test_429_uses_retry_after_then_recovers():
    r, p, clock = make(haiku=[err("rate_limit", status=429, retry_after=30)])
    assert r.ask(build_prompt).target == "gemini:gemini-3.8-flash"
    assert r.state["claude:claude-haiku-5-5"].cooldown_until == pytest.approx(clock() + 30)
    clock.advance(10)
    assert r.ask(build_prompt).target == "gemini:gemini-3.8-flash"  # haiku hali cooldown'da
    assert len(p["haiku"].calls) == 1
    clock.advance(21)
    assert r.ask(build_prompt).target == "claude:claude-haiku-5-5"


def test_429_without_retry_after_defaults_to_60s():
    r, _, clock = make(haiku=[err("rate_limit", status=429)])
    r.ask(build_prompt)
    assert r.state["claude:claude-haiku-5-5"].cooldown_until == pytest.approx(
        clock() + DEFAULT_COOLDOWN
    )


def test_daily_quota_until_pacific_midnight():
    clock = FakeClock(utc(2026, 10, 13, 10, 0))  # 03:00 PDT
    r, _, _ = make(clock=clock, g38=[err("quota_daily", status=429, retry_after=14)])
    r.state["claude:claude-haiku-5-5"].cooldown_until = clock() + 999
    ans = r.ask(build_prompt)
    assert ans.target == "gemini:gemini-3.6-flash"
    until = r.state["gemini:gemini-3.8-flash"].cooldown_until
    assert until == pytest.approx(utc(2026, 10, 14, 7, 0) + 5)  # 00:00 PDT = 12:00 Toshkent


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (utc(2026, 10, 13, 10, 0), utc(2026, 10, 14, 7, 0)),  # PDT (-7)
        (utc(2026, 12, 1, 12, 0), utc(2026, 12, 2, 8, 0)),  # PST (-8)
        (utc(2026, 3, 8, 9, 0), utc(2026, 3, 9, 7, 0)),  # 01:00 PST, kechasi yozgi vaqtga o'tadi
        (utc(2026, 11, 1, 7, 30), utc(2026, 11, 2, 8, 0)),  # 00:30 PDT, kechasi qishkiga
        (utc(2026, 10, 13, 6, 59), utc(2026, 10, 13, 7, 0)),  # yarim tunga 1 daqiqa
    ],
)
def test_next_pacific_midnight(now, expected):
    assert next_pacific_midnight(now) == pytest.approx(expected + 5)


def test_pacific_offset_dst():
    assert pacific_offset(dt.datetime(2026, 7, 1, tzinfo=dt.UTC)) == dt.timedelta(hours=-7)
    assert pacific_offset(dt.datetime(2026, 1, 15, tzinfo=dt.UTC)) == dt.timedelta(hours=-8)


# --- 5xx, timeout ------------------------------------------------------------------------------


def test_transient_retried_once_on_same_target():
    r, p, clock = make(haiku=[err("transient", status=503)])
    ans = r.ask(build_prompt)
    assert ans.target == "claude:claude-haiku-5-5"
    assert len(p["haiku"].calls) == 2
    assert len(clock.sleeps) == 1 and 0.8 <= clock.sleeps[0] <= 2.0


@pytest.mark.parametrize("kind", ["transient"])
def test_transient_twice_moves_on(kind):
    r, p, _ = make(haiku=[err(kind, status=529), err(kind, detail="timeout")])
    ans = r.ask(build_prompt)
    assert ans.target == "gemini:gemini-3.8-flash"
    assert len(p["haiku"].calls) == 2


def test_repeated_transient_failures_cool_down():
    r, _, clock = make(haiku=[err("transient")] * 4)
    r.ask(build_prompt)
    r.ask(build_prompt)
    assert r.state["claude:claude-haiku-5-5"].cooldown_until > clock()


# --- 401/403 ----------------------------------------------------------------------------------


def test_auth_error_disables_provider_and_notifies_once():
    notes = []
    r, p, _ = make(
        notify=lambda prov, reason: notes.append((prov, reason)),
        haiku=[err("auth", status=401)],
    )
    assert r.ask(build_prompt).target == "gemini:gemini-3.8-flash"
    assert notes == [("claude", "auth")]
    assert r.state["claude:claude-sonnet-5-5"].disabled_reason == "auth"
    for name in ("g38", "g36", "g35", "g31"):
        p[name].script = [err("rate_limit", status=429)]
    ans = r.ask(build_prompt)
    assert ans.outcome == "busy"
    assert not p["sonnet"].calls  # o'chirilgan maqsad chaqirilmaydi
    assert notes == [("claude", "auth")]
    r.enable_all()
    assert r.state["claude:claude-haiku-5-5"].disabled_reason is None


def test_billing_error():
    notes = []
    r, _, _ = make(
        notify=lambda a, b: notes.append((a, b)), haiku=[err("auth", status=402, detail="billing")]
    )
    r.ask(build_prompt)
    assert notes == [("claude", "billing")]


def test_model_not_found_disables_only_that_model():
    r, _, _ = make(g38=[err("bad_request", status=404)], haiku=[err("rate_limit")])
    assert r.ask(build_prompt).target == "gemini:gemini-3.6-flash"
    assert r.state["gemini:gemini-3.8-flash"].disabled_reason == "model"
    assert r.state["gemini:gemini-3.6-flash"].disabled_reason is None


# --- 400, xavfsizlik, bo'sh javob ---------------------------------------------------------------


@pytest.mark.parametrize("kind", ["bad_request", "safety", "empty"])
def test_bad_answers_move_to_next(kind):
    r, _, _ = make(haiku=[err(kind, status=400 if kind == "bad_request" else None)])
    ans = r.ask(build_prompt)
    assert ans.outcome == "ok" and ans.target == "gemini:gemini-3.8-flash"


def test_all_fail_with_bad_answers_is_failed():
    r, p, _ = make()
    for v in p.values():
        v.script = [err("safety")]
    assert r.ask(build_prompt).outcome == "failed"


def test_partial_stream_resets_bubble_and_falls_back():
    resets = []
    r, _, _ = make(haiku=[Partial("[happy] Sal", err("network"))])
    got = []
    ans = r.ask(build_prompt, on_token=got.append, on_reset=lambda: resets.append(1))
    assert resets == [1]
    assert ans.target == "gemini:gemini-3.8-flash"
    assert got[0] == "[happy] Sal"


# --- internet yo'q, hamma band --------------------------------------------------------------


def test_no_internet_is_offline():
    r, p, _ = make()
    for v in p.values():
        v.script = [err("network")]
    assert r.ask(build_prompt).outcome == "offline"


def test_network_plus_rate_limit_is_offline():
    r, p, _ = make(haiku=[err("network")])
    for k in ("g38", "g36", "g35", "g31", "sonnet"):
        p[k].script = [err("rate_limit", retry_after=20)]
    assert r.ask(build_prompt).outcome == "offline"


def test_everything_rate_limited_is_busy_with_retry_time():
    r, p, clock = make()
    for i, v in enumerate(p.values()):
        v.script = [err("rate_limit", retry_after=10 + i)]
    ans = r.ask(build_prompt)
    assert ans.outcome == "busy"
    assert ans.retry_at == pytest.approx(clock() + 10)
    # cooldown paytida hech kim chaqirilmaydi, natija yana "busy"
    ans2 = r.ask(build_prompt)
    assert ans2.outcome == "busy" and all(len(v.calls) == 1 for v in p.values())


def test_no_targets():
    r = Router([])
    assert r.ask(build_prompt).outcome == "no_targets"


def test_first_token_budget_stops_chain():
    clock = FakeClock()
    r, p, _ = make(clock=clock)
    for v in p.values():
        v.latency = 13.0
        v.script = [err("transient", detail="timeout"), err("transient", detail="timeout")]
    ans = r.ask(build_prompt)
    assert ans.outcome == "busy"
    assert len([v for v in p.values() if v.calls]) <= 2


def test_cheapest_prefers_flash_lite():
    r, _, _ = make()
    assert r.cheapest().key == "gemini:gemini-3.1-flash-lite"
    r.state["gemini:gemini-3.1-flash-lite"].cooldown_until = r.clock() + 100
    assert r.cheapest().key == "gemini:gemini-3.5-flash-lite"


# --- oflayn navbat ------------------------------------------------------------------------------


def test_offline_queue_cycle():
    clock = FakeClock()
    q = OfflineQueue(clock=clock, rng=random.Random(1))
    item = q.add("Ertaga ob-havo qanday?")
    assert len(q) == 1 and not q.due()
    clock.advance(61)
    assert q.due() == [item]
    q.postpone(item)
    assert not q.due()
    clock.advance(61)
    q.done(item)
    assert len(q) == 0


def test_offline_queue_respects_retry_at():
    clock = FakeClock()
    q = OfflineQueue(clock=clock)
    item = q.add("savol", retry_at=clock() + 600)
    clock.advance(100)
    assert not q.due()
    clock.advance(501)
    assert q.due() == [item]
