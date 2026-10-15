"""OpenRouter: so'rov shakli, SSE, xatolar, zanjir, Sozlamalarda saqlash (tarmoqsiz)."""

import json

import httpx
import pytest

from tests.fakes import FakeProvider
from tests.test_i18n import controller  # noqa: F401 — fixture
from yue.ai.factory import build_chain
from yue.ai.providers.base import ChatMessage, ProviderError, SystemBlock, Usage
from yue.ai.providers.openrouter import BASE_URL, DEFAULT_MODEL, MODELS, OpenRouterProvider
from yue.ai.usage import cost_usd

KEY = "sk-or-TEST"
LARGE = "mistralai/mistral-large-2407"


def sse(*chunks, comment=True):
    out = ": OPENROUTER PROCESSING\n\n" if comment else ""
    out += "".join(f"data: {json.dumps(c)}\n\n" for c in chunks)
    return (out + "data: [DONE]\n\n").encode()


def delta(text, finish=None):
    return {"choices": [{"delta": {"content": text}, "finish_reason": finish}]}


def provider(handler, model=DEFAULT_MODEL):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenRouterProvider(KEY, model=model, client=client)


def ask(p):
    return "".join(
        p.stream(
            [SystemBlock("Persona"), SystemBlock("Holat")], [ChatMessage("user", "Salom")], 64, 5
        )
    )


def test_models_and_base_url():
    assert BASE_URL == "https://openrouter.ai/api/v1"
    assert MODELS == ("meta-llama/llama-3.3-70b-instruct", LARGE)


def test_stream_request_headers_body_and_usage():
    seen = {}

    def handler(req):
        seen["url"] = str(req.url)
        seen["auth"] = req.headers["authorization"]
        seen["body"] = json.loads(req.content)
        usage = {"prompt_tokens": 50, "completion_tokens": 7, "cost": 0.00012}
        body = sse(delta("Sa"), delta("lom!", "stop"), {"choices": [], "usage": usage})
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    p = provider(handler, model=LARGE)
    assert ask(p) == "Salom!"
    assert seen["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert seen["auth"] == f"Bearer {KEY}"
    body = seen["body"]
    assert body["model"] == LARGE and body["stream"] is True and body["max_tokens"] == 64
    assert body["provider"] == {"data_collection": "deny"}
    assert body["messages"][0] == {"role": "system", "content": "Persona\n\nHolat"}
    assert body["messages"][1] == {"role": "user", "content": "Salom"}
    assert p.key == f"openrouter:{LARGE}" and p.private is True
    assert p.last_usage == Usage(input_tokens=50, output_tokens=7, cost=0.00012)


@pytest.mark.parametrize(
    ("status", "kind", "detail"),
    [
        (401, "auth", ""),
        (403, "auth", ""),
        (402, "auth", "billing"),
        (400, "bad_request", ""),
        (404, "bad_request", ""),
        (408, "transient", ""),
        (502, "transient", ""),
        (503, "transient", ""),
    ],
)
def test_http_errors(status, kind, detail):
    p = provider(lambda req: httpx.Response(status, json={"error": {"code": status}}))
    with pytest.raises(ProviderError) as e:
        ask(p)
    assert e.value.kind == kind and e.value.detail == detail and e.value.status == status


def test_rate_limit_retry_after():
    p = provider(lambda req: httpx.Response(429, headers={"retry-after": "12"}, json={}))
    with pytest.raises(ProviderError) as e:
        ask(p)
    assert e.value.kind == "rate_limit" and e.value.retry_after == 12.0


def test_mid_stream_error_and_empty():
    err = {
        "error": {"code": 502, "message": "x"},
        "choices": [{"delta": {}, "finish_reason": "error"}],
    }
    p = provider(lambda req: httpx.Response(200, content=sse(err)))
    with pytest.raises(ProviderError) as e:
        ask(p)
    assert e.value.kind == "transient"
    p = provider(lambda req: httpx.Response(200, content=sse(delta("", "stop"))))
    with pytest.raises(ProviderError) as e:
        ask(p)
    assert e.value.kind == "empty"


def test_network_and_timeout():
    def down(req):
        raise httpx.ConnectError("yo'q")

    def slow(req):
        raise httpx.ReadTimeout("sekin")

    for handler, kind in ((down, "network"), (slow, "transient")):
        with pytest.raises(ProviderError) as e:
            ask(provider(handler))
        assert e.value.kind == kind


def test_cost_from_provider_overrides_price_table():
    assert cost_usd(f"openrouter:{LARGE}", Usage(1000, 100, cost=0.0042)) == 0.0042
    assert cost_usd(f"openrouter:{LARGE}", Usage(1000, 100)) == 0.0


# --- zanjir --------------------------------------------------------------------------------


def _fake_or(key, model):
    return FakeProvider("openrouter", model, [])


def chain(**kw):
    local = FakeProvider("ollama", "gemma3:4b", [])
    kw.setdefault("local", local)
    return [
        p.key
        for p in build_chain(
            "sk-ant",
            "AIza",
            available_gemini={"gemini-3.8-flash"},
            make_claude=lambda k, model: FakeProvider("claude", model, []),
            make_gemini=lambda k, model, paid: FakeProvider("gemini", model, []),
            make_openrouter=_fake_or,
            **kw,
        )
    ]


def test_primary_openrouter_uses_selected_model_first():
    keys = chain(openrouter_key=KEY, openrouter_model=LARGE, primary="openrouter", smart=True)
    assert keys == [
        f"openrouter:{LARGE}",
        "claude:claude-sonnet-5-5",
        "claude:claude-haiku-5-5",
        "gemini:gemini-3.8-flash",
    ]  # Online — Ollama hech qachon qo'shilmaydi


def test_openrouter_not_primary_is_extra_cloud_model_last():
    keys = chain(openrouter_key=KEY, primary="claude", smart=True)
    assert keys[-1] == f"openrouter:{DEFAULT_MODEL}" and keys[0] == "claude:claude-sonnet-5-5"
    assert not any(k.startswith("ollama:") for k in keys)


def test_offline_sends_nothing_to_openrouter():
    assert chain(openrouter_key=KEY, primary="openrouter", offline=True) == ["ollama:gemma3:4b"]


def test_without_key_primary_openrouter_falls_back_to_cloud():
    keys = chain(primary="openrouter", smart=True, local=None)
    assert keys[0] == "claude:claude-sonnet-5-5" and not any("openrouter" in k for k in keys)


# --- nomlar --------------------------------------------------------------------------------


def test_menu_and_settings_use_new_names():
    from yue.i18n import t

    assert t("menu.online") == "Online" and t("menu.offline") == "Offline"
    assert t("settings.tab.local") == "Offline"
    assert "qo'shimcha bulut model" in t("ai.openrouter.hint")
    assert "asosiy model" not in t("ai.openrouter.hint")


# --- Sozlamalar → config.json → zanjir ------------------------------------------------------


def test_settings_save_openrouter_key_and_model(controller):  # noqa: F811
    from yue.ui.settings import SettingsDialog

    c = controller
    dlg = SettingsDialog(c)
    dlg.openrouter.edit.setText(f"  {KEY}  ")
    dlg.openrouter_model.setCurrentIndex(dlg.openrouter_model.findData(LARGE))
    dlg.primary.setCurrentIndex(dlg.primary.findData("openrouter"))
    dlg._save()

    saved = json.loads(c.cfg.path.read_text(encoding="utf-8"))
    assert saved["ai"]["primary"] == "openrouter"
    assert saved["ai"]["openrouter_model"] == LARGE
    assert saved["secrets"]["openrouter_key"] and KEY not in json.dumps(saved)  # DPAPI
    assert c.brain.keys()[2] == KEY
    first = c.brain.router.targets[0]
    assert first.key == f"openrouter:{LARGE}" and first.model == LARGE
    assert first._key == KEY

    dlg = SettingsDialog(c)  # qayta ochilganda saqlangan model tanlangan
    assert dlg.openrouter_model.currentData() == LARGE and dlg.openrouter.saved
