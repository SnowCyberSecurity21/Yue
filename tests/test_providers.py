"""Provayderlar: tarmoqsiz (Claude — soxta SDK mijozi, Gemini — httpx.MockTransport)."""

import json
from contextlib import contextmanager
from types import SimpleNamespace

import anthropic
import httpx
import httpx2
import pytest

from yue.ai.providers.base import ChatMessage, ProviderError, SystemBlock
from yue.ai.providers.claude import ClaudeProvider, map_error
from yue.ai.providers.gemini import GeminiProvider, available_models, classify_error

SYSTEM = [SystemBlock("persona", cache=True), SystemBlock("[Holat] ...")]
MSGS = [ChatMessage("user", "Salom")]


# --- Claude ---------------------------------------------------------------------------------


def _resp(status, headers=None):
    return httpx2.Response(
        status, headers=headers or {}, request=httpx2.Request("POST", "https://api.test/v1")
    )


@pytest.mark.parametrize(
    ("exc", "kind", "retry"),
    [
        (
            anthropic.RateLimitError("x", response=_resp(429, {"retry-after": "12"}), body=None),
            "rate_limit",
            12.0,
        ),
        (anthropic.RateLimitError("x", response=_resp(429), body=None), "rate_limit", None),
        (anthropic.AuthenticationError("x", response=_resp(401), body=None), "auth", None),
        (anthropic.PermissionDeniedError("x", response=_resp(403), body=None), "auth", None),
        (anthropic.BadRequestError("x", response=_resp(400), body=None), "bad_request", None),
        (anthropic.NotFoundError("x", response=_resp(404), body=None), "bad_request", None),
        (anthropic.InternalServerError("x", response=_resp(500), body=None), "transient", None),
        (anthropic.APIStatusError("x", response=_resp(529), body=None), "transient", None),
        (anthropic.APIStatusError("x", response=_resp(402), body=None), "auth", None),
        (anthropic.APITimeoutError(request=httpx2.Request("POST", "https://a")), "transient", None),
        (
            anthropic.APIConnectionError(request=httpx2.Request("POST", "https://a")),
            "network",
            None,
        ),
    ],
)
def test_claude_error_mapping(exc, kind, retry):
    e = map_error(exc)
    assert e.kind == kind and e.retry_after == retry


class FakeStream:
    def __init__(self, chunks, stop_reason="end_turn", error=None):
        self.text_stream = iter(chunks)
        self._stop = stop_reason
        self._error = error

    def get_final_message(self):
        if self._error:
            raise self._error
        usage = SimpleNamespace(
            input_tokens=50,
            output_tokens=10,
            cache_read_input_tokens=900,
            cache_creation_input_tokens=0,
        )
        return SimpleNamespace(stop_reason=self._stop, usage=usage)


class FakeClient:
    def __init__(self, stream):
        self.kwargs = None
        outer = self

        class Messages:
            @contextmanager
            def stream(self, **kwargs):
                outer.kwargs = kwargs
                yield stream

        self.messages = Messages()


def test_claude_stream_request_shape_and_usage():
    client = FakeClient(FakeStream(["[happy] ", "Salom!"]))
    p = ClaudeProvider("k", client=client)
    out = "".join(p.stream(SYSTEM, MSGS, 512, 20))
    assert out == "[happy] Salom!"
    kw = client.kwargs
    assert kw["model"] == "claude-haiku-5-5"
    assert kw["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in kw["system"][1]
    assert kw["output_config"] == {"effort": "low"}
    assert kw["messages"] == [{"role": "user", "content": "Salom"}]
    assert p.last_usage.cache_read_tokens == 900
    assert p.private is True


def test_claude_refusal_and_empty():
    p = ClaudeProvider("k", client=FakeClient(FakeStream([], stop_reason="refusal")))
    with pytest.raises(ProviderError) as e:
        list(p.stream(SYSTEM, MSGS, 512, 20))
    assert e.value.kind == "safety"
    p = ClaudeProvider("k", client=FakeClient(FakeStream([])))
    with pytest.raises(ProviderError) as e:
        list(p.stream(SYSTEM, MSGS, 512, 20))
    assert e.value.kind == "empty"


def test_claude_sdk_retries_disabled():
    p = ClaudeProvider("sk-ant-test")
    assert p._client.max_retries == 0


# --- Gemini ---------------------------------------------------------------------------------


def sse(*chunks):
    return "".join(f"data: {json.dumps(c)}\r\n\r\n" for c in chunks).encode()


def text_chunk(t, finish=None):
    cand = {"content": {"role": "model", "parts": [{"text": t}]}}
    if finish:
        cand["finishReason"] = finish
    return {"candidates": [cand]}


def gemini(handler, **kw):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return GeminiProvider("AIzaTEST", client=client, base_url="https://gl.test/v1beta", **kw)


def test_gemini_stream_request_and_text():
    seen = {}

    def handler(req: httpx.Request):
        seen["url"] = str(req.url)
        seen["key"] = req.headers.get("x-goog-api-key")
        seen["body"] = json.loads(req.content)
        body = sse(
            {"candidates": [{"content": {"parts": [{"text": "o'ylash", "thought": True}]}}]},
            text_chunk("[happy] Sa"),
            text_chunk("lom!", finish="STOP")
            | {
                "usageMetadata": {
                    "promptTokenCount": 30,
                    "candidatesTokenCount": 5,
                    "thoughtsTokenCount": 7,
                }
            },
        )
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    p = gemini(handler)
    out = "".join(p.stream(SYSTEM, MSGS + [ChatMessage("assistant", "x")], 256, 10))
    assert out == "[happy] Salom!"
    assert seen["url"].endswith("/models/gemini-3.8-flash:streamGenerateContent?alt=sse")
    assert seen["key"] == "AIzaTEST" and "key=" not in seen["url"]
    body = seen["body"]
    assert body["systemInstruction"]["parts"][0]["text"].startswith("persona")
    assert [c["role"] for c in body["contents"]] == ["user", "model"]
    assert body["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "low"}
    assert body["generationConfig"]["maxOutputTokens"] == 256
    assert p.last_usage.output_tokens == 12


def err_body(code, status, details):
    return json.dumps(
        {"error": {"code": code, "message": "x", "status": status, "details": details}}
    )


RETRY = {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "14s"}


def quota(qid):
    return {
        "@type": "type.googleapis.com/google.rpc.QuotaFailure",
        "violations": [
            {
                "quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_requests",
                "quotaId": qid,
            }
        ],
    }


def test_gemini_429_per_minute():
    e = classify_error(
        429,
        err_body(
            429,
            "RESOURCE_EXHAUSTED",
            [quota("GenerateRequestsPerMinutePerProjectPerModel-FreeTier"), RETRY],
        ),
    )
    assert e.kind == "rate_limit" and e.retry_after == 14.0


def test_gemini_429_per_day():
    e = classify_error(
        429,
        err_body(
            429,
            "RESOURCE_EXHAUSTED",
            [quota("GenerateRequestsPerDayPerProjectPerModel-FreeTier"), RETRY],
        ),
    )
    assert e.kind == "quota_daily"


def test_gemini_429_without_details():
    e = classify_error(429, err_body(429, "RESOURCE_EXHAUSTED", []))
    assert e.kind == "rate_limit" and e.retry_after is None
    assert classify_error(429, b"not json").kind == "rate_limit"


@pytest.mark.parametrize(
    ("status", "details", "kind"),
    [
        (
            400,
            [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "API_KEY_INVALID"}],
            "auth",
        ),
        (403, [], "auth"),
        (400, [], "bad_request"),
        (404, [], "bad_request"),
        (500, [], "transient"),
        (503, [], "transient"),
        (504, [], "transient"),
    ],
)
def test_gemini_error_kinds(status, details, kind):
    assert classify_error(status, err_body(status, "X", details)).kind == kind


def test_gemini_http_errors_raise():
    p = gemini(
        lambda req: httpx.Response(429, content=err_body(429, "RESOURCE_EXHAUSTED", [RETRY]))
    )
    with pytest.raises(ProviderError) as e:
        list(p.stream(SYSTEM, MSGS, 256, 10))
    assert e.value.kind == "rate_limit" and e.value.retry_after == 14


def test_gemini_network_and_timeout():
    def boom(req):
        raise httpx.ConnectError("no route")

    with pytest.raises(ProviderError) as e:
        list(gemini(boom).stream(SYSTEM, MSGS, 256, 10))
    assert e.value.kind == "network"

    def slow(req):
        raise httpx.ReadTimeout("slow")

    with pytest.raises(ProviderError) as e:
        list(gemini(slow).stream(SYSTEM, MSGS, 256, 10))
    assert e.value.kind == "transient"


def test_gemini_safety_block():
    p = gemini(
        lambda req: httpx.Response(200, content=sse({"promptFeedback": {"blockReason": "SAFETY"}}))
    )
    with pytest.raises(ProviderError) as e:
        list(p.stream(SYSTEM, MSGS, 256, 10))
    assert e.value.kind == "safety"
    p = gemini(lambda req: httpx.Response(200, content=sse(text_chunk("", finish="SAFETY"))))
    with pytest.raises(ProviderError) as e:
        list(p.stream(SYSTEM, MSGS, 256, 10))
    assert e.value.kind == "safety"


def test_gemini_retries_without_thinking_config_on_400():
    bodies = []

    def handler(req):
        body = json.loads(req.content)
        bodies.append(body)
        if "thinkingConfig" in body["generationConfig"]:
            return httpx.Response(400, content=err_body(400, "INVALID_ARGUMENT", []))
        return httpx.Response(200, content=sse(text_chunk("[neutral] Ha.")))

    p = gemini(handler)
    assert "".join(p.stream(SYSTEM, MSGS, 256, 10)) == "[neutral] Ha."
    assert len(bodies) == 2 and p.thinking_level is None


def test_gemini_models_list_cached(tmp_path):
    calls = []

    def handler(req):
        calls.append(str(req.url))
        return httpx.Response(
            200,
            json={
                "models": [
                    {"name": "models/gemini-3.8-flash"},
                    {"name": "models/gemini-3.1-flash-lite"},
                ]
            },
        )

    p = gemini(handler)
    cache = tmp_path / "gemini_models.json"
    assert available_models(p, cache, now=1000.0) == {"gemini-3.8-flash", "gemini-3.1-flash-lite"}
    assert available_models(p, cache, now=1000.0 + 3600) == {
        "gemini-3.8-flash",
        "gemini-3.1-flash-lite",
    }
    assert len(calls) == 1
    available_models(p, cache, now=1000.0 + 25 * 3600)
    assert len(calls) == 2


def test_gemini_models_list_offline_returns_none(tmp_path):
    def boom(req):
        raise httpx.ConnectError("x")

    assert available_models(gemini(boom), tmp_path / "m.json") is None
