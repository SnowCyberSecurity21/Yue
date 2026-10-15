"""AI xizmati: har holatda foydalanuvchi o'zbekcha javob oladi yoki savol navbatga tushadi."""

import datetime as dt
import random
import re

import pytest

from tests.fakes import FakeClock, FakeProvider, chain, err
from yue.ai import prompt
from yue.ai.factory import build_chain
from yue.ai.providers.base import Usage
from yue.ai.router import Router
from yue.ai.service import AiService
from yue.ai.usage import UsageTracker, cost_usd
from yue.lines import Lines

FORBIDDEN = re.compile(
    r"limit|quota|kvota|429|keyinroq yozing|rate|exceeded|resource_exhausted|error|exception",
    re.I,
)


def ctx():
    return prompt.PromptContext(now=dt.datetime(2026, 10, 13, 12, 0))


def make(online=True, **scripts):
    clock = FakeClock()
    p = chain(clock=clock, **scripts)
    order = [p["haiku"], p["g38"], p["g36"], p["g35"], p["g31"], p["sonnet"]]
    router = Router(order, clock=clock, sleep=clock.sleep, rng=random.Random(0))
    svc = AiService(router, Lines.load(), ctx, online=lambda: online)
    svc.queue.clock = clock
    return svc, p, clock


def visible(res):
    parts = []
    if res.line:
        parts.append(res.line[1])
    if res.reply:
        parts.append(res.reply.text)
    return " ".join(parts)


SCENARIOS = {
    "429": {"haiku": [err("rate_limit", status=429)]},
    "kunlik_kvota": {"g38": [err("quota_daily")], "haiku": [err("rate_limit")]},
    "500": {"haiku": [err("transient", status=500), err("transient", status=500)]},
    "timeout": {"haiku": [err("transient", detail="timeout")] * 2},
    "401": {"haiku": [err("auth", status=401)]},
    "internet_yoq": {k: [err("network")] for k in ("haiku", "g38", "g36", "g35", "g31", "sonnet")},
    "hammasi_band": {
        k: [err("rate_limit", retry_after=30)]
        for k in ("haiku", "g38", "g36", "g35", "g31", "sonnet")
    },
    "hammasi_rad": {k: [err("safety")] for k in ("haiku", "g38", "g36", "g35", "g31", "sonnet")},
}


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_user_always_gets_uzbek_and_never_sees_limit(name):
    svc, _, _ = make(**SCENARIOS[name])
    res = svc.chat("Salom, bugun nima qilamiz?")
    assert res.kind in ("answer", "queued", "fallback")
    text = visible(res)
    assert text.strip()
    assert not FORBIDDEN.search(text), text


def test_offline_question_queued_and_answered_later():
    svc, p, clock = make(**SCENARIOS["internet_yoq"])
    res = svc.chat("Ertaga yomg'ir yog'adimi?")
    assert res.kind == "queued" and res.line == res.line and len(svc.queue) == 1
    offline_texts = [t for _, t in svc.lines.options("offline")]
    assert res.line[1] in offline_texts

    svc.online = lambda: False
    clock.advance(61)
    assert svc.process_queue() == []  # hali internet yo'q — navbatda qoladi
    assert len(svc.queue) == 1

    svc.online = lambda: True
    clock.advance(61)
    done = svc.process_queue()
    assert len(done) == 1
    item, answer = done[0]
    assert item.text == "Ertaga yomg'ir yog'adimi?"
    assert answer.kind == "answer" and answer.reply.text
    assert len(svc.queue) == 0


def test_busy_queue_waits_for_cooldown():
    svc, p, clock = make(**SCENARIOS["hammasi_band"])
    res = svc.chat("Savol")
    assert res.kind == "queued"
    assert res.line[1] in [t for _, t in svc.lines.options("busy")]
    assert res.queued.next_try >= clock() + 30


def test_no_keys():
    svc = AiService(Router([]), Lines.load(), ctx)
    res = svc.chat("Salom")
    assert res.kind == "no_keys" and "Sozlamalar" in res.line[1]


def test_reply_parsed_with_actions():
    svc, _, _ = make(
        haiku=[
            '[smug] Yozdim, soat 9 da eslataman. <vazifa vaqt="2026-10-14 09:00">Dori ichish</vazifa>'
        ]
    )
    res = svc.chat("Ertaga soat 9 da dori ichishni eslat")
    assert res.reply.expression == "smug"
    assert res.reply.text == "Yozdim, soat 9 da eslataman."
    assert res.reply.actions[0].when == "2026-10-14 09:00"


def test_english_answer_translated_by_cheapest():
    svc, p, _ = make(
        g38=["[happy] Sure! I can help you with that, what do you want to do first?"],
        haiku=[err("rate_limit")],
        g31=["[happy] Albatta! Yordam beraman, avval nima qilamiz?"],
    )
    res = svc.chat("Yordam berasanmi?")
    assert res.translated and res.reply.text == "Albatta! Yordam beraman, avval nima qilamiz?"
    assert "o'zbek tiliga" in p["g31"].calls[0][0][0].text


def test_translation_of_private_answer_stays_private():
    svc, p, _ = make(
        haiku=[
            "[neutral] Your allergy to penicillin means you should avoid it, okay?",
            "[neutral] Penitsillinga allergiyangiz bor, undan saqlaning.",
        ],
    )
    res = svc.chat("Qaysi dori mumkin emas?")
    assert res.translated and res.target == "claude:claude-haiku-5-5"
    assert not p["g31"].calls and not p["g35"].calls  # bepul Gemini'ga yuborilmadi
    assert len(p["haiku"].calls) == 2


def test_translation_skipped_when_user_asked_other_language():
    svc, p, _ = make(haiku=["[happy] Hello, how are you doing today, my friend?"])
    res = svc.chat("Buni inglizchaga tarjima qil: salom, qalaysan")
    assert not res.translated and res.reply.text.startswith("Hello")


def test_empty_after_parse_is_fallback():
    svc, _, _ = make(haiku=["[happy]   "])
    res = svc.chat("?")
    assert res.kind == "fallback" and res.line[1] in [t for _, t in svc.lines.options("confused")]


def test_usage_and_budget_warning_once():
    u = UsageTracker(budget_usd=0.0001)
    assert u.add("claude:claude-haiku-5-5", Usage(1000, 100)) is True
    assert u.add("claude:claude-haiku-5-5", Usage(1000, 100)) is False
    assert u.day.requests == 2
    assert cost_usd("claude:claude-haiku-5-5", Usage(1_000_000, 0)) == pytest.approx(0.10)
    assert cost_usd("gemini:gemini-3.8-flash", Usage(1_000_000, 1_000_000)) == 0


def test_build_chain_orders():
    mk = lambda key, model, **kw: FakeProvider("claude", model)  # noqa: E731
    mg = lambda key, model, paid=False: FakeProvider("gemini", model, private=paid)  # noqa: E731
    keys = lambda ch: [t.model for t in ch]  # noqa: E731
    assert keys(build_chain("c", "g", make_claude=mk, make_gemini=mg)) == [
        "claude-haiku-5-5", "gemini-3.8-flash", "gemini-3.6-flash",
        "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "claude-sonnet-5-5",
    ]  # fmt: skip
    assert (
        keys(build_chain("c", "g", primary="gemini", make_claude=mk, make_gemini=mg))[0]
        == "gemini-3.8-flash"
    )
    # "Aqlliroq" (standart): Sonnet, uning orqasida Haiku, keyin Gemini
    assert keys(build_chain("c", "g", smart=True, make_claude=mk, make_gemini=mg)) == [
        "claude-sonnet-5-5", "claude-haiku-5-5", "gemini-3.8-flash", "gemini-3.6-flash",
        "gemini-3.5-flash-lite", "gemini-3.1-flash-lite",
    ]  # fmt: skip
    assert keys(build_chain(None, "g", smart=True, make_claude=mk, make_gemini=mg))[0] == (
        "gemini-3.8-flash"
    )
    assert keys(build_chain(None, "g", make_claude=mk, make_gemini=mg)) == [
        "gemini-3.8-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
    ]
    assert keys(build_chain("c", None, make_claude=mk, make_gemini=mg)) == [
        "claude-haiku-5-5",
        "claude-sonnet-5-5",
    ]
    assert keys(
        build_chain(
            None, "g", available_gemini={"gemini-3.6-flash"}, make_claude=mk, make_gemini=mg
        )
    ) == ["gemini-3.6-flash"]
    assert build_chain(None, None, make_claude=mk, make_gemini=mg) == []


def test_canned_lines_never_mention_limits():
    for text in Lines.load().all_texts():
        assert not FORBIDDEN.search(text), text
