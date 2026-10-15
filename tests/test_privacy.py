"""private=False maqsadga ketayotgan promptda sog'liq, faktlar va xotira xulosasi yo'q."""

import datetime as dt
import random

from tests.fakes import FakeClock, FakeProvider, chain, err
from yue.ai import prompt
from yue.ai.providers.base import ChatMessage
from yue.ai.router import Router
from yue.ai.service import AiService
from yue.lines import Lines

HEALTH = "Penitsillinga allergiyasi bor"
FACT = "Ismi Aziz, Toshkentda yashaydi"
SUMMARY = "Kecha boshi og'rigan edi, ish joyida stress"


def ctx():
    return prompt.PromptContext(
        now=dt.datetime(2026, 10, 13, 21, 5),
        period="evening",
        outfit="hood_black",
        accessories=("glasses", "phones_head"),
        activity="type",
        battery=(42, False),
        tasks=["#3: Dori ichish — 2026-10-14 09:00"],
        summary=SUMMARY,
        facts=[FACT],
        health=[HEALTH],
        user_name="Aziz",
        history=[
            ChatMessage("assistant", "Salom!"),
            ChatMessage("user", "Qalaysan?"),
            ChatMessage("assistant", "Yaxshi."),
        ],
    )


def flat(system, messages):
    return "\n".join(b.text for b in system) + "\n".join(m.text for m in messages)


def test_private_target_gets_memory():
    system, _ = prompt.build(ctx(), "Savol", private=True)
    text = flat(system, [])
    assert HEALTH in text and FACT in text and SUMMARY in text and "Aziz" in text


def test_non_private_target_gets_no_memory():
    context = ctx()
    system, messages = prompt.build(context, "Savol", private=False)
    text = flat(system, messages)
    for secret in (
        HEALTH,
        FACT,
        SUMMARY,
        "Aziz",
        "Sog'liq daftari",
        "[Faktlar]",
        "Qalaysan?",
        "Yaxshi.",
    ):
        assert secret not in text
    assert "#3: Dori ichish — 2026-10-14 09:00" not in text
    assert [message.text for message in messages] == ["Savol"]


def test_prompt_structure_and_cache_order():
    system, messages = prompt.build(ctx(), "Ertaga nima qilamiz?", private=True)
    assert system[0].cache and "Sen — Yue" in system[0].text
    assert system[1].cache
    assert not system[-1].cache and system[-1].text.startswith("[Holat]")
    state = system[-1].text
    assert "13-oktabr 2026-yil, seshanba" in state and "21:05" in state and "kechqurun" in state
    assert "kapyushon" in state and "42%" in state
    assert messages[0].role == "user"  # tarix assistant bilan boshlansa — kesiladi
    assert messages[-1].text == "Ertaga nima qilamiz?"


def test_local_short_persona_keeps_six_messages_and_fits_prompt():
    ctx_ = ctx()
    ctx_.history = [
        ChatMessage("user" if i % 2 == 0 else "assistant", f"xabar {i}") for i in range(12)
    ]
    system, messages = prompt.build_short_persona(ctx_, "savol", private=True)
    assert "Sen — Yue" in system[0].text
    assert "JAVOB FORMATI" in system[0].text
    assert len(messages) == 7  # 6 ta tarix + joriy savol
    chars = sum(len(block.text) for block in system) + sum(len(m.text) for m in messages)
    assert (chars + 3) // 4 <= 6000


def test_ai_service_selects_short_persona_for_local_provider():
    context = ctx()
    context.history = [
        ChatMessage("user" if i % 2 == 0 else "assistant", f"xabar {i}") for i in range(12)
    ]
    provider = FakeProvider("ollama", "qwen2.5:7b")
    provider.local = True
    service = AiService(Router([provider]), Lines.load(), lambda: context)
    result = service.chat("savol", enqueue=False)
    system, messages = provider.calls[0]
    assert result.kind == "answer"
    assert "JAVOB FORMATI" in system[0].text
    assert len(messages) == 7


def test_router_sends_private_data_only_to_private_targets():
    clock = FakeClock()
    p = chain(clock=clock, haiku=[err("rate_limit", status=429)])
    targets = [p["haiku"], p["g38"], p["sonnet"]]
    router = Router(targets, clock=clock, sleep=clock.sleep, rng=random.Random(0))
    svc = AiService(router, Lines.load(), ctx, online=lambda: True)
    res = svc.chat("Boshim og'riyapti, nima ichsam bo'ladi?")
    assert res.kind == "answer" and res.target == "gemini:gemini-3.8-flash"
    sent = flat(*p["g38"].calls[0])
    assert HEALTH not in sent and FACT not in sent and SUMMARY not in sent
    # Haiku (private) ga yuborilgan prompt esa to'liq edi
    assert HEALTH in flat(*p["haiku"].calls[0])


def test_paid_gemini_is_private():
    from yue.ai.providers.gemini import GeminiProvider

    assert GeminiProvider("k", paid=True).private is True
    assert GeminiProvider("k", paid=False).private is False
