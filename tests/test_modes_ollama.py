"""AI manbasi (Online/Offline) va offline model (Ollama): kalit so'zlar, menyu, zanjir, navbat."""

import datetime as dt
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from tests.fakes import FakeClock, FakeProvider, err
from tests.test_i18n import controller  # noqa: F401 — fixture
from yue.ai import prompt
from yue.ai.factory import build_chain
from yue.ai.parse import Reply
from yue.ai.providers.base import ChatMessage, ProviderError, SystemBlock
from yue.ai.providers.ollama import OllamaProvider, installed_models
from yue.ai.router import Answer, Router
from yue.ai.service import LOCAL_DOWN_WAIT, ChatResult
from yue.i18n import t
from yue.modes import recognize

# --- kalit so'zlar -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "switch"),
    [
        ("/online", "online"),
        ("Online", "online"),
        ("online rejim", "online"),
        ("onlayn rejim", "online"),
        ("онлайн режим", "online"),
        ("/ochiq", "online"),
        ("/offline", "offline"),
        ("Offline!", "offline"),
        ("offline rejim", "offline"),
        ("oflayn rejim", "offline"),
        ("офлайн режим", "offline"),
        ("online rejimga o‘t", "online"),
        ("ОФЛАЙН РЕЖИМ", "offline"),
    ],
)
def test_mode_keywords_latin_and_cyrillic(text, switch):
    assert recognize(text) == switch


@pytest.mark.parametrize(
    "text",
    [
        "yaqin rejim haqida gapir",
        "yaqin",
        "rejim",
        "oddiy",
        "salom",
        "online o'yin",
        "/yaqin",
        "/maxfiy",
        "/oddiy",
        "maxfiy rejim",
        "yaqin rejim",
    ],  # munosabat kalit so'zlari yo'q
)
def test_not_mode_keywords(text):
    assert recognize(text) is None


def _asked(c, monkeypatch):
    calls = []
    monkeypatch.setattr(c.brain, "ask", lambda text, enqueue=True: calls.append(text) or True)
    return calls


def _said(c, monkeypatch):
    said = []
    monkeypatch.setattr(c, "say_text", lambda e, txt, **kw: said.append(txt))
    monkeypatch.setattr(c, "say", lambda e, txt: said.append(txt))
    return said


def test_source_keywords_switch_and_are_not_sent_to_ai(controller, monkeypatch):  # noqa: F811
    c = controller
    calls, said = _asked(c, monkeypatch), _said(c, monkeypatch)
    c.cfg.set("ai.local_model", "qwen2.5:7b")
    c.on_submit("/offline")
    assert calls == [] and c.cfg.get("ai.manba") == "offline" and c._tray_marks is True
    assert said[-1] in [x for _, x in c.lines.options("manba", "offline")]
    assert [x.key for x in c.brain.router.targets] == ["ollama:qwen2.5:7b"]
    c.on_submit("online")
    assert calls == [] and c.cfg.get("ai.manba") == "online" and c._tray_marks is False
    assert said[-1] in [x for _, x in c.lines.options("manba", "online")]
    c.on_submit("Salom")
    assert calls == ["Salom"]  # oddiy xabar — AI'ga


def test_menus_have_source_radio_and_no_relation_items(controller):  # noqa: F811
    from PySide6.QtWidgets import QMenu

    from yue.ui.menu import fill_menu

    c = controller
    for tray in (True, False):  # bitta menyu quruvchi: tray va o'ng tugma
        m = QMenu()
        fill_menu(c, m, tray=tray)
        acts = {a.text(): a for a in m.actions()}
        on, off = acts[t("menu.online")], acts[t("menu.offline")]
        assert on.isCheckable() and on.isChecked() and not off.isChecked()
        assert on.actionGroup() is off.actionGroup() and on.actionGroup().isExclusive()
        assert not any("Yaqin" in x or "Maxfiy" in x for x in acts)  # munosabat menyuda yo'q
    off.trigger()
    assert c.cfg.get("ai.manba") == "offline"


def test_tray_mark_only_for_offline(controller):  # noqa: F811
    c = controller
    plain = c.tray.icon().cacheKey()
    c.set_source("offline", speak=False)
    assert c._tray_marks is True and c.tray.icon().cacheKey() != plain
    c.set_source("online", speak=False)
    assert c._tray_marks is False


def test_untagged_answer_shows_mood_expression(controller, monkeypatch):  # noqa: F811
    c = controller
    shown = []
    monkeypatch.setattr(c, "say_text", lambda e, t, **kw: shown.append(e))
    c.brain.last_mood = "uyalgan"
    c._on_answered(ChatResult("answer", reply=Reply("neutral", "Hmf...", tagged=False)))
    c._on_answered(ChatResult("answer", reply=Reply("angry", "Yo'q!", tagged=True)))
    assert shown == ["shy", "angry"]  # teg bo'lsa — modelniki


# --- zanjir -------------------------------------------------------------------------------------

mk = lambda key, model, **kw: FakeProvider("claude", model)  # noqa: E731
mg = lambda key, model, paid=False: FakeProvider("gemini", model, private=paid)  # noqa: E731
mo = lambda key, model: FakeProvider("openrouter", model)  # noqa: E731


def keys(chain):
    return [x.key for x in chain]


def test_online_chain_is_cloud_only_even_with_local_model():
    local = FakeProvider("ollama", "qwen2.5:7b")
    for kw in ({"smart": True}, {"smart": False}, {"primary": "gemini"}, {"primary": "openrouter"}):
        ch = build_chain(
            "c", "g", make_claude=mk, make_gemini=mg, make_openrouter=mo, openrouter_key="o",
            local=local, **kw,
        )  # fmt: skip
        assert "ollama:qwen2.5:7b" not in keys(ch) and len(ch) == 7
    assert build_chain(None, None, local=local) == []  # kalit yo'q — Ollama'ga o'tmaydi


def test_offline_chain_is_only_ollama():
    local = FakeProvider("ollama", "qwen2.5:7b")
    ch = build_chain("c", "g", make_claude=mk, make_gemini=mg, local=local, offline=True)
    assert keys(ch) == ["ollama:qwen2.5:7b"]
    assert build_chain("c", "g", make_claude=mk, make_gemini=mg, offline=True) == []


def test_offline_without_model_explains_setup(controller):  # noqa: F811
    c = controller
    c.set_source("offline", speak=False)
    result = c.brain.service.chat("Salom", enqueue=False)
    assert result.kind == "no_keys" and result.line == ("thinking", t("notify.local_missing"))


# --- Ollama ishlamayapti va internet yo'q ---------------------------------------------------------


def _offline_service(c, script):
    clock = FakeClock()
    local = FakeProvider("ollama", "qwen2.5:7b", script)
    local.local = True
    c.cfg.set("ai.manba", "offline")
    svc = c.brain.service
    svc.clock = svc.queue.clock = clock
    svc.router.clock = clock
    svc.router.set_targets([local])
    svc.online = lambda: True
    return svc, clock, local


def test_ollama_down_says_once_and_waits_five_minutes(controller):  # noqa: F811
    c = controller
    svc, clock, local = _offline_service(c, [err("network")] * 3)
    res = svc.chat("Salom")
    assert res.kind == "queued" and res.reason == "local_down"
    assert res.line in c.lines.options("ollama_ishlamayapti")
    assert res.queued.next_try >= clock() + LOCAL_DOWN_WAIT - 1
    calls = len(local.calls)
    for _ in range(9):  # 30 s lik tekshiruvlar 4.5 daqiqa davomida — urinish yo'q
        clock.advance(30)
        assert svc.process_queue() == []
    assert len(local.calls) == calls
    clock.advance(40)  # 5 daqiqa o'tdi — bitta urinish, yana 5 daqiqaga qoldiriladi
    assert svc.process_queue() == [] and len(local.calls) == calls + 1
    assert svc.queue.due() == [] and svc.local_down_until >= clock() + LOCAL_DOWN_WAIT - 1


def test_online_no_internet_offers_offline_once(controller, monkeypatch, qtbot):  # noqa: F811
    import yue.core

    c = controller
    monkeypatch.setattr(yue.core, "OFFER_MS", 0)
    said = []
    c.brain.say.connect(lambda e, txt: said.append(txt))
    offline = ChatResult("queued", line=("sad", "x"), reason="offline")
    c.brain._maybe_offer_offline(offline)  # Ollama modeli tanlanmagan — taklif yo'q
    qtbot.wait(50)
    assert said == []
    c.cfg.set("ai.local_model", "qwen2.5:7b")
    c.brain._maybe_offer_offline(offline)
    c.brain._maybe_offer_offline(offline)  # ikkinchi marta — aytilmaydi
    qtbot.waitUntil(lambda: len(said) >= 1)
    qtbot.wait(50)
    assert len(said) == 1 and said[0] in [x for _, x in c.lines.options("offline_taklif")]
    assert "/offline" in said[0]
    c.brain._maybe_offer_offline(ChatResult("answer", reply=Reply("happy", "ok")))
    c.brain._maybe_offer_offline(offline)  # internet qaytib, yana uzildi — yana bir marta
    qtbot.waitUntil(lambda: len(said) == 2)


# --- Offline prompt hajmi ------------------------------------------------------------------------


def test_offline_prompt_fits_6000_tokens():
    ctx = prompt.PromptContext(
        now=dt.datetime(2026, 10, 14, 21, 30),
        tasks=[f"#{i}: Hisobotni tugatish va jamoaga yuborish — 2026-10-1{i} 09:00" for i in range(8)],
        summary="Foydalanuvchi dasturchi, Python va Linux bilan ishlaydi. " * 12,
        facts=[f"Foydalanuvchi haqida muhim fakt raqami {i}, choyni yaxshi ko'radi" for i in range(15)],
        health=["Bosh og'rig'i tez-tez bo'ladi, ko'p ekranga qaraydi"] * 3,
        user_name="Anvar",
        history=[ChatMessage("user" if i % 2 == 0 else "assistant", "Salom, bugun qanday? " * 15)
                 for i in range(10)],
    )  # fmt: skip
    system, messages = prompt.build_short_persona(ctx, "Menga Python'da sort haqida ayt", True)
    chars = sum(len(b.text) for b in system) + sum(len(m.text) for m in messages)
    assert chars / 3 <= 6000  # o'zbekcha matn: ~3 belgi/token (ehtiyotkor baho)


# --- Ollama: soxta HTTP server ------------------------------------------------------------------


class _Handler(BaseHTTPRequestHandler):
    mode = "ok"
    seen: list = []

    def log_message(self, *a):  # jim
        pass

    def do_GET(self):  # noqa: N802
        body = json.dumps({"models": [{"name": "qwen2.5:7b"}, {"name": "gemma3:4b"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length", 0))
        _Handler.seen.append(json.loads(self.rfile.read(n)))
        if _Handler.mode == "missing":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error":"model not found"}')
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()
        for piece in ("[happy] Sa", "lom! ", "Men shu yerdaman."):
            line = {"message": {"role": "assistant", "content": piece}, "done": False}
            self.wfile.write((json.dumps(line) + "\n").encode())
            self.wfile.flush()
        done = {"message": {"content": ""}, "done": True, "prompt_eval_count": 50, "eval_count": 9}
        self.wfile.write((json.dumps(done) + "\n").encode())


@pytest.fixture
def ollama_server():
    _Handler.mode, _Handler.seen = "ok", []
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def _free_port_url():
    import socket

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return f"http://127.0.0.1:{port}"


def test_ollama_streams_ndjson(ollama_server):
    p = OllamaProvider("qwen2.5:7b", base_url=ollama_server)
    assert p.private and p.key == "ollama:qwen2.5:7b"
    out = list(
        p.stream(
            [SystemBlock("persona"), SystemBlock("[Holat]")],
            [ChatMessage("user", "Salom")],
            300,
            10,
        )
    )
    assert "".join(out) == "[happy] Salom! Men shu yerdaman." and len(out) == 3
    body = _Handler.seen[-1]
    assert body["stream"] is True and body["options"]["num_ctx"] == 16384
    assert body["options"]["num_predict"] == 300
    assert body["messages"][0] == {"role": "system", "content": "persona\n\n[Holat]"}
    assert p.last_usage.input_tokens == 50 and p.last_usage.output_tokens == 9
    assert installed_models(ollama_server) == ["gemma3:4b", "qwen2.5:7b"]


def test_ollama_errors(ollama_server):
    _Handler.mode = "missing"
    with pytest.raises(ProviderError) as e:
        list(
            OllamaProvider("yoq", base_url=ollama_server).stream(
                [], [ChatMessage("user", "x")], 10, 5
            )
        )
    assert e.value.kind == "bad_request" and e.value.status == 404
    down = _free_port_url()
    with pytest.raises(ProviderError) as e:
        list(OllamaProvider("m", base_url=down).stream([], [ChatMessage("user", "x")], 10, 5))
    assert e.value.kind == "network"  # Ollama ishlamayapti
    assert installed_models(down) is None


def _router(local_script):
    clock = FakeClock()
    cloud = [
        FakeProvider("claude", "claude-sonnet-5-5", [err("network")]),
        FakeProvider("gemini", "gemini-3.8-flash", [err("network")], private=False),
    ]
    local = FakeProvider("ollama", "qwen2.5:7b", local_script)
    local.local = True
    return Router([*cloud, local], clock=clock, sleep=clock.sleep), local


def test_router_still_handles_local_target_after_cloud():
    # Router o'zi zanjir tartibini bilmaydi (zanjirni factory quradi) — lokal maqsad ishlaydi
    router, local = _router(["[happy] Men shu yerdaman."])
    ans = router.ask(
        lambda t: prompt.build(
            prompt.PromptContext(now=dt.datetime(2026, 10, 13)),
            "salom",
            t.private,
        )
    )
    assert ans.outcome == "ok" and ans.target == "ollama:qwen2.5:7b" and ans.private
    assert local.calls


def test_internet_down_and_ollama_missing_goes_to_queue():
    router, _ = _router([err("bad_request", status=404)])
    ans = router.ask(lambda t: ([SystemBlock("x")], [ChatMessage("user", "salom")]))
    assert ans.outcome == "offline"  # lokal xatosi natijani "failed" ga aylantirmaydi
    router, _ = _router([err("network")])
    assert (
        router.ask(lambda t: ([SystemBlock("x")], [ChatMessage("user", "s")])).outcome == "offline"
    )


def test_local_down_detection():
    from yue.ai.service import _local_down

    assert _local_down(Answer("offline", errors=["ollama:qwen2.5:7b:network"]))
    assert not _local_down(Answer("offline", errors=["claude:claude-sonnet-5-5:network"]))
    assert not _local_down(Answer("offline"))
