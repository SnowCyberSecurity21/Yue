"""Boshqa foydalanuvchi uchun: birinchi ochilish ustasi, kalitsiz rejim, tez buyruqlar, ovoz va
model standartlari, "Yue haqida" oynasi."""

import datetime as dt
import hashlib
import re

import pytest

from tests.test_i18n import controller  # noqa: F401 — fixture
from yue import paths
from yue.config import Config
from yue.i18n import t
from yue.quick import Quick
from yue.quick import parse as parse_quick

NOW = dt.datetime(2026, 10, 15, 14, 0)
# Nora'ning voice_id si (C:\nora sozlamasidan) — qiymatning o'zi repoga yozilmaydi, faqat xeshi
NORA_VOICE_SHA256 = "2b90a19772ea2ec1b8310a00b1797244e60a2c032269bdc15bd8955f2aa87edb"


def _said(c, monkeypatch):
    said = []
    monkeypatch.setattr(c, "say_text", lambda e, txt, **kw: said.append(txt))
    return said


# --- tez buyruqlar --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("eslat: suv ichish", Quick("add", "suv ichish")),
        ("Eslat 18:00: hisobot", Quick("add", "hisobot", "2026-10-15 18:00")),
        ("eslat ertaga 9:00: dori ichish", Quick("add", "dori ichish", "2026-10-16 09:00")),
        ("eslat 1 daqiqadan keyin: choy", Quick("add", "choy", "2026-10-15 14:01")),
        ("eslat har kuni 08:00: suv", Quick("add", "suv", "08:00", "har_kuni")),
        ("vazifalar", Quick("list")),
        ("eslat qachondir: x", Quick("bad")),
        ("eslat 18:00:", Quick("bad")),
        ("ertaga dori ichishni eslat", None),  # ikki nuqta yo'q — AI'ga
        ("eslatib qo'ysangiz-chi", None),
        ("vazifalar haqida gapir", None),
    ],
)
def test_quick_parse(text, want):
    assert parse_quick(text, NOW) == want


def test_relative_time_never_rounds_down():
    from yue.tasks.timeparse import parse_user_time

    late = dt.datetime(2026, 10, 15, 7, 53, 58)
    assert parse_user_time("1 daqiqadan keyin", late) == ("2026-10-15 07:55", None)
    assert parse_user_time("2 soatdan keyin", NOW) == ("2026-10-15 16:00", None)


def test_quick_commands_work_without_ai(controller, monkeypatch):  # noqa: F811
    c = controller
    asked = []
    monkeypatch.setattr(c.brain, "has_ai", lambda: True)  # kalit bor paytda ham AI'ga ketmaydi
    monkeypatch.setattr(c.brain, "ask", lambda text, enqueue=True: asked.append(text) or True)
    said = _said(c, monkeypatch)
    c.on_submit("eslat 1 daqiqadan keyin: choy damlash")
    assert asked == [] and "choy damlash" in said[-1]
    task = next(x for x in c.brain.store.tasks() if x.text == "choy damlash")
    assert task.due is not None
    c.on_submit("eslat qachondir: x")
    assert said[-1] in [x for _, x in c.lines.options("eslat_xato")]
    told = []
    c.brain.say.connect(lambda e, txt: told.append(txt))
    c.on_submit("vazifalar")
    assert asked == [] and told and "choy damlash" in told[-1]


def test_quick_task_is_reminded_on_time(controller, monkeypatch):  # noqa: F811
    c = controller
    _said(c, monkeypatch)
    c.on_submit("eslat 1 daqiqadan keyin: choy")
    told = []
    c.brain.say.connect(lambda e, txt: told.append(txt))
    c.brain.check_tasks()
    assert told == []  # hali vaqti kelmadi
    late = dt.datetime.now() + dt.timedelta(minutes=2)
    monkeypatch.setattr(c.brain.scheduler, "now", lambda: late)
    c.brain.check_tasks()
    assert len(told) == 1 and "choy" in told[0] and "{" not in told[0]
    c.brain.check_tasks()
    assert len(told) == 1  # bir marta


# --- kalitsiz rejim -------------------------------------------------------------------------------


def test_no_keys_line_once_per_ten_minutes(controller, monkeypatch):  # noqa: F811
    import yue.app

    c = controller
    assert not c.brain.has_ai()
    clock = [1000.0]
    monkeypatch.setattr(yue.app.time, "monotonic", lambda: clock[0])
    said = _said(c, monkeypatch)
    no_keys = [x for _, x in c.lines.options("no_keys")]
    c.on_submit("Salom")
    assert said[-1] in no_keys and c.bubble.action_btn.isVisibleTo(c.bubble)
    assert c.bubble.action_btn.text() == t("bubble.open_settings")
    c.on_submit("Qalaysan?")
    assert said[-1] in [x for _, x in c.lines.options("kalitsiz")]
    clock[0] += 9 * 60
    c.on_submit("Yana")
    assert said[-1] not in no_keys
    clock[0] += 2 * 60
    c.on_submit("Endi-chi?")
    assert said[-1] in no_keys
    assert sum(x in no_keys for x in said) == 2


def test_action_button_opens_settings(controller, monkeypatch):  # noqa: F811
    c = controller
    opened = []
    monkeypatch.setattr(c, "show_settings", lambda tab="ai": opened.append(tab))
    c.on_submit("Salom")
    c.bubble.action_btn.click()
    assert opened == ["ai"] and not c.bubble.action_btn.isVisibleTo(c.bubble)
    c.say_text("happy", "Boshqa gap")
    assert not c.bubble.action_btn.isVisibleTo(c.bubble)


def test_no_technical_words_in_canned_lines():
    from yue.lines import Lines

    bad = re.compile(r"\b(limit|quota|429|error|exception|traceback)\b", re.I)
    assert not [x for x in Lines.load().all_texts() if bad.search(x)]


# --- birinchi ochilish ustasi ------------------------------------------------------------------


def _wizard(c):
    from yue.ui.welcome import WelcomeDialog

    c.cfg.set("welcome_done", False)
    return WelcomeDialog(c)


@pytest.mark.parametrize(
    ("choice", "field", "primary", "mode", "manba"),
    [
        ("gemini", "gemini", "gemini", None, "online"),
        ("claude", "claude", "claude", "fast", "online"),
        ("openrouter", "openrouter", "openrouter", None, "online"),
        ("ollama", None, None, None, "offline"),
        ("none", None, None, None, "online"),
    ],
)
def test_wizard_ai_choice_sets_config(controller, monkeypatch, choice, field, primary, mode, manba):  # noqa: F811
    c = controller
    monkeypatch.setattr(c, "create_shortcut", lambda: True)
    monkeypatch.setattr(c, "apply_settings", lambda **kw: None)
    c.cfg.set("ai.primary", "unset")
    c.cfg.set("ai.mode", "smart")
    dlg = _wizard(c)
    dlg.ai_radio[choice].setChecked(True)
    assert dlg.ai_stack.currentIndex() == list(dlg.ai_radio).index(choice)
    if field:
        getattr(dlg, field).edit.setText("test-kalit-123")
    dlg.name.setText("  Akmal  ")
    dlg._finish()
    assert c.cfg.get("welcome_done") and c.cfg.get("user.name") == "Akmal"
    assert c.cfg.get("ai.primary") == (primary or "unset")
    assert c.cfg.get("ai.mode") == (mode or "smart")
    assert c.cfg.get("ai.manba") == manba
    if field:
        assert c.brain.secrets.get(f"{field}_key") == "test-kalit-123"


def test_wizard_pages_and_hotkey_text(controller):  # noqa: F811
    c = controller
    c.toggle_hotkey = "Ctrl+Alt+Shift+Y"
    dlg = _wizard(c)
    assert dlg.pages.count() == 4 and dlg.ai_radio["gemini"].isChecked()  # tavsiya
    dlg._go(1)
    dlg._go(1)
    assert dlg.skip.isVisibleTo(dlg)  # ovoz — ixtiyoriy
    dlg._go(1)
    assert "Ctrl+Alt+Shift+Y" in dlg.hotkey_note.text() and not dlg.skip.isVisibleTo(dlg)
    assert dlg.next.text() == t("btn.finish")


def test_wizard_voice_list_and_preview(controller, qtbot, monkeypatch):  # noqa: F811
    from tests.test_voice import VID

    c = controller
    dlg = _wizard(c)
    dlg._on_account({"used": 0, "limit": 10000, "voices": [("x1", "Boshqa"), (VID, "Ovoz")]})
    dlg.v_voices.setCurrentIndex(2)
    assert dlg.v_voice_id.text() == VID
    calls = []

    class Client:
        def synth(self, voice_id, text, model):
            calls.append((voice_id, text))
            return b"mp3"

    monkeypatch.setattr(c.voice, "_client_factory", lambda key: Client())
    monkeypatch.setattr(c.voice, "_push", lambda data: None)
    dlg.v_key.edit.setText("sk_kalit_123")
    dlg._preview()
    qtbot.waitUntil(lambda: dlg.v_preview.isEnabled())
    n = len(t("voice.preview.text"))
    assert calls == [(VID, t("voice.preview.text"))] and c.voice.used_today() == n
    assert dlg.v_status.text() == t("voice.preview.ok", n=n)


# --- ovoz va model standartlari ---------------------------------------------------------------


def test_defaults_voice_empty_and_fast_mode():
    cfg = Config()
    assert cfg.get("voice.voice_id") == "" and cfg.get("ai.mode") == "fast"


def test_no_voice_no_key_is_silent(controller, qtbot):  # noqa: F811
    c = controller
    notes = []
    c.voice.notify.connect(lambda *a: notes.append(a))
    c.voice.speak("Salom!")
    qtbot.wait(30)
    assert notes == [] and not c.voice.is_playing


def test_nora_voice_id_nowhere():
    files = [
        p
        for p in paths.RES.rglob("*")
        if p.is_file()
        and p.suffix in (".py", ".json", ".txt", ".toml", ".md", ".iss", ".spec")
        and not set(p.relative_to(paths.RES).parts) & {".venv", ".git", "build", "dist"}
    ]
    for p in files:
        for token in re.findall(r"[A-Za-z0-9]{20}", p.read_text(encoding="utf-8", errors="ignore")):
            assert hashlib.sha256(token.encode()).hexdigest() != NORA_VOICE_SHA256, p


# --- "Yue haqida" va sinov menyusi ---------------------------------------------------------------


def test_about_dialog_has_docs_and_privacy(controller):  # noqa: F811
    from yue import __version__
    from yue.ui.about import AboutDialog

    dlg = AboutDialog()
    texts = " ".join(w.text() for w in dlg.findChildren(type(dlg.doc_buttons["LICENSE.txt"])))
    assert set(dlg.doc_buttons) == {"README.html", "LICENSE.txt", "THIRD_PARTY_LICENSES.txt"}
    assert t("about.readme") in texts
    from PySide6.QtWidgets import QLabel

    labels = " ".join(x.text() for x in dlg.findChildren(QLabel))
    assert __version__ in labels and "Telemetriya yo'q" in labels


def test_debug_menu_only_with_env(controller, monkeypatch):  # noqa: F811
    from PySide6.QtWidgets import QMenu

    from yue.ui.menu import fill_menu

    def titles():
        m = QMenu()
        fill_menu(controller, m)
        return [a.text() for a in m.actions()]

    monkeypatch.delenv("YUE_DEBUG", raising=False)
    assert t("menu.debug") not in titles()
    monkeypatch.setenv("YUE_DEBUG", "1")
    assert t("menu.debug") in titles()


# --- hujjatlar har qanday kompyuterda ochiladi ----------------------------------------------------


def test_readme_html_keeps_text_and_image(qapp):
    from yue import docs

    md = (paths.RES / "README.md").read_text(encoding="utf-8")
    page = docs.markdown_to_html(md)
    assert page.startswith("<!DOCTYPE html>") and "max-width: 800px" in page
    assert 'src="docs/yue.png"' in page  # xom <img> qatori o'rniga o'z rasmimiz
    for text in ("Windows 10 yoki 11", "Tez-tez uchraydigan muammolar", "Ctrl+Alt+Shift+U"):
        assert text in page, text


def test_docs_built_in_source_mode(qapp, tmp_path, monkeypatch):
    from yue import docs

    monkeypatch.setattr(paths, "APP_DIR", tmp_path / "yoq")  # o'rnatilmagan
    monkeypatch.setattr(docs.tempfile, "gettempdir", lambda: str(tmp_path))
    for name in (docs.README_HTML, docs.LICENSE_TXT, docs.THIRD_PARTY):
        p = docs.doc_file(name)
        assert p is not None and p.is_file() and p.parent == tmp_path / "yue-docs", name
    assert (tmp_path / "yue-docs" / "docs" / "yue.png").is_file()


def test_about_buttons_open_html_and_txt(controller, monkeypatch, tmp_path):  # noqa: F811
    from yue import docs
    from yue.ui import about

    monkeypatch.setattr(docs.tempfile, "gettempdir", lambda: str(tmp_path))
    opened = []
    monkeypatch.setattr(about.QDesktopServices, "openUrl", lambda url: opened.append(url) or True)
    dlg = about.AboutDialog()
    for b in dlg.doc_buttons.values():
        b.click()
    names = sorted(u.toLocalFile().rsplit("/", 1)[-1] for u in opened)
    assert names == ["LICENSE.txt", "README.html", "THIRD_PARTY_LICENSES.txt"]


def test_installer_ships_html_and_txt():
    iss = (paths.RES / "build" / "yue.iss").read_text(encoding="utf-8")
    assert r'Filename: "{app}\README.html"' in iss and 'README.md"; DestDir' not in iss
    assert "LICENSE.txt" in iss and "THIRD_PARTY_LICENSES.txt" in iss
