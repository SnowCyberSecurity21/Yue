"""Log tozaligi: xabar matni, oyna sarlavhalari va kalitlar logga tushmaydi."""

import ast
import logging
import random

from tests.fakes import FakeClock, FakeProvider, err
from yue import paths
from yue.ai import prompt
from yue.ai.router import Router
from yue.ai.service import AiService
from yue.lines import Lines
from yue.logsetup import QUIET_LOGGERS, RedactFilter, redact, setup_logging

SECRET_Q = "Mening parolim Qovun123 va boshim og'riyapti"
SECRET_A = "[sad] Qovun123 juda zaif parol, uni almashtiring."


def test_redact_keys():
    assert "sk-ant" not in redact("kalit sk-ant-api03-AbCdEf0123456789xyz ishlamadi")
    assert "AIza" not in redact("key=AIzaSyA1234567890abcdefghijklmnop")
    assert "secret" not in redact("x-api-key: secret-value")


def test_redact_filter_on_records_and_exceptions():
    f = RedactFilter()
    rec = logging.LogRecord(
        "t", logging.INFO, __file__, 1, "kalit %s", ("sk-ant-api03-ZZZZZZZZZZZZ",), None
    )
    f.filter(rec)
    assert "sk-ant" not in rec.getMessage()
    try:
        raise ValueError("AIzaSyA1234567890abcdefghijklmnop")
    except ValueError:
        import sys

        rec2 = logging.LogRecord("t", logging.ERROR, __file__, 1, "xato", (), sys.exc_info())
    f.filter(rec2)
    assert "AIza" not in (rec2.exc_text or "")


def test_chat_does_not_log_text(caplog):
    caplog.set_level(logging.DEBUG)
    clock = FakeClock()
    p1 = FakeProvider("claude", "claude-haiku-5-5", script=[err("rate_limit", status=429)])
    p2 = FakeProvider("gemini", "gemini-3.8-flash", script=[SECRET_A], private=False)
    router = Router([p1, p2], clock=clock, sleep=clock.sleep, rng=random.Random(0))
    svc = AiService(
        router,
        Lines.load(),
        lambda: prompt.PromptContext(now=__import__("datetime").datetime.now()),
    )
    res = svc.chat(SECRET_Q)
    assert res.kind == "answer"
    assert "rate_limit" in caplog.text  # xato turi yoziladi
    assert "Qovun123" not in caplog.text and "parolim" not in caplog.text


def test_third_party_loggers_quiet(monkeypatch, tmp_path):
    monkeypatch.setenv("YUE_DATA", str(tmp_path))
    monkeypatch.setenv("YUE_DEBUG", "1")
    root = logging.getLogger()
    before = list(root.handlers)
    try:
        setup_logging()
        for name in QUIET_LOGGERS:
            assert logging.getLogger(name).getEffectiveLevel() >= logging.WARNING
    finally:
        for h in list(root.handlers):
            if h not in before:
                root.removeHandler(h)
                h.close()


SENSITIVE_NAMES = {
    "text",
    "question",
    "reply",
    "answer",
    "user_text",
    "content",
    "title",
    "key",
    "api_key",
    "piece",
    "partial",
    "line",
}


def test_log_calls_never_pass_text_variables():
    """Kodda log.*(...) chaqiruvlariga matn o'zgaruvchilari uzatilmaydi."""
    bad = []
    for path in (paths.RES / "yue").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in ("log", "logging", "logger")
            ):
                for arg in node.args[1:]:
                    names = {n.id for n in ast.walk(arg) if isinstance(n, ast.Name)}
                    # `target.key` — maqsad nomi ("claude:claude-haiku-5-5"), API kalit emas
                    names |= {
                        n.attr
                        for n in ast.walk(arg)
                        if isinstance(n, ast.Attribute) and n.attr != "key"
                    }
                    if names & SENSITIVE_NAMES:
                        bad.append(f"{path.name}:{node.lineno}")
    assert not bad
