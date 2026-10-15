"""Suhbat oqimi: kiritish maydoni hech qachon qulflanmaydi, har savol bitta yakun bilan tugaydi."""

import threading

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from tests.fakes import FakeProvider
from yue import paths

REPLY = "[happy] Salom! Men shu yerdaman, nima qilamiz?"


class SlowProvider(FakeProvider):
    """`release` kelguncha (ko'pi bilan `wait` s) kutadigan provayder — sekin internet."""

    def __init__(self, wait: float = 20.0, error: Exception | None = None) -> None:
        super().__init__("claude", "claude-haiku-5-5", default=REPLY)
        self.release = threading.Event()
        self.wait = wait
        self.error = error

    def stream(self, system, messages, max_tokens, timeout):
        self.release.wait(self.wait)
        if self.error is not None:
            raise self.error
        yield from super().stream(system, messages, max_tokens, timeout)


@pytest.fixture
def ctl(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("YUE_DATA", str(tmp_path))
    from yue.app import Controller
    from yue.config import Config
    from yue.pet.pack import load_pack
    from yue.platform import NullPlatform

    class FakeDpapi(NullPlatform):
        def protect(self, data):
            return data[::-1]

        def unprotect(self, blob):
            return blob[::-1]

    cfg = Config(path=tmp_path / "config.json")
    cfg.set("welcome_done", True)
    c = Controller(QApplication.instance(), cfg, load_pack(paths.DEFAULT_PACK), FakeDpapi())
    c.brain.service.online = lambda: True
    yield c
    for p in getattr(c, "_fakes", []):  # sekin provayderlar ishchi oqimini ushlab qolmasin
        if isinstance(p, SlowProvider):
            p.release.set()
    c.shutdown()
    c.pet.close()
    c.bubble.close()


def use(c, provider):
    c.brain.router.set_targets([provider])
    c.brain.router.enable_all()
    c._fakes = [*getattr(c, "_fakes", []), provider]
    return provider


def send(qtbot, c, text):
    edit = c.bubble.edit
    edit.setFocus()
    qtbot.keyClicks(edit, text)
    qtbot.keyClick(edit, Qt.Key.Key_Return)


def test_can_type_while_waiting_and_enter_keeps_text(qtbot, ctl):
    slow = use(ctl, SlowProvider())
    ctl.open_chat()
    send(qtbot, ctl, "Birinchi savol")
    assert ctl.brain.busy and ctl.bubble.busy
    edit = ctl.bubble.edit
    assert not edit.isReadOnly() and edit.toPlainText() == ""
    assert ctl.bubble.status.isVisibleTo(ctl.bubble)  # "Yue o'ylayapti…"
    assert not ctl.bubble.send_btn.isEnabled()
    send(qtbot, ctl, "Ikkinchi")  # javob hali yo'q — Enter matnni yo'qotmaydi
    assert edit.toPlainText() == "Ikkinchi"
    with qtbot.waitSignal(ctl.brain.answered, timeout=10_000):
        slow.release.set()
    assert not ctl.brain.busy and not ctl.bubble.busy
    assert edit.toPlainText() == "Ikkinchi" and not edit.isReadOnly()
    assert ctl.bubble.send_btn.isEnabled() and not ctl.bubble.status.isVisibleTo(ctl.bubble)


def test_cancel_frees_input(qtbot, ctl):
    use(ctl, SlowProvider())
    ctl.open_chat()
    send(qtbot, ctl, "Savol")
    with qtbot.waitSignal(ctl.brain.answered, timeout=2000) as sig:
        ctl.brain.cancel()
    assert sig.args[0].kind == "cancelled"
    assert not ctl.brain.busy and not ctl.bubble.busy
    assert not ctl.bubble.edit.isReadOnly()


def test_error_frees_input(qtbot, ctl):
    slow = use(ctl, SlowProvider(error=RuntimeError("kutilmagan")))
    slow.release.set()
    ctl.open_chat()
    with qtbot.waitSignal(ctl.brain.answered, timeout=10_000) as sig:
        send(qtbot, ctl, "Savol")
    assert sig.args[0].kind == "fallback"
    assert not ctl.brain.busy and not ctl.bubble.busy and not ctl.bubble.edit.isReadOnly()


def test_timeout_shows_line_and_frees_input(qtbot, ctl):
    slow = use(ctl, SlowProvider())
    ctl.brain.ask_timeout = 0.3
    ctl.open_chat()
    with qtbot.waitSignal(ctl.brain.answered, timeout=5000) as sig:
        send(qtbot, ctl, "Savol")
    res = sig.args[0]
    assert res.kind == "timeout" and res.line in ctl.lines.options("timeout")
    assert not ctl.brain.busy and not ctl.bubble.busy and not ctl.bubble.edit.isReadOnly()
    # Kech kelgan javob e'tiborsiz qoladi — ikkinchi yakun bo'lmaydi.
    late = []
    ctl.brain.answered.connect(late.append)
    slow.release.set()
    qtbot.wait(500)
    assert late == []


def test_after_answer_input_open_and_focused(qtbot, ctl):
    use(ctl, FakeProvider("claude", "claude-haiku-5-5", default=REPLY))
    ctl.open_chat()
    with qtbot.waitSignal(ctl.brain.answered, timeout=10_000):
        send(qtbot, ctl, "Salom")
    edit = ctl.bubble.edit
    assert not edit.isReadOnly()
    assert ctl.bubble.focusWidget() is edit


def test_five_messages_in_a_row(qtbot, ctl):
    use(ctl, FakeProvider("claude", "claude-haiku-5-5", default=REPLY))
    ctl.open_chat()
    for i in range(5):
        with qtbot.waitSignal(ctl.brain.answered, timeout=10_000) as sig:
            send(qtbot, ctl, f"Xabar {i + 1}")
        assert sig.args[0].kind == "answer"
    assert len(ctl.brain.store.recent_messages(20)) == 10


def test_long_text_grows_field_and_resets_after_send(qtbot, ctl):
    use(ctl, FakeProvider("claude", "claude-haiku-5-5", default=REPLY))
    ctl.open_chat()
    b = ctl.bubble
    edit = b.edit
    one_line = edit.height()
    long = "Bu juda uzun xabar, bir necha qatorga o'raladi va boshi ko'rinib turishi kerak. " * 2
    edit.setPlainText(long)
    assert b.edit_lines() >= 2
    assert edit.height() > one_line
    assert edit.verticalScrollBar().value() == 0  # hammasi sig'adi — boshidan ko'rinadi
    with qtbot.waitSignal(ctl.brain.answered, timeout=10_000):
        qtbot.keyClick(edit, Qt.Key.Key_Return)
    assert edit.toPlainText() == "" and edit.height() == one_line
    assert edit.verticalScrollBar().value() == 0
    edit.setPlainText(long * 6)  # juda uzun — maydon chegarada, ichida aylanadi
    assert edit.height() < one_line * 6
