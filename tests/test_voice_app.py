"""Ovoz ilovada: pufak + ovoz, AI javobi gap-gap, to'xtatish holatlari, menyu, Sozlamalar."""

import pytest

from tests.test_i18n import controller  # noqa: F401 — fixture
from tests.test_voice import KEY, VID, FakeClient, FakePlayer
from yue.ai.parse import Reply
from yue.ai.service import ChatResult
from yue.voice.cache import cache_key
from yue.voice.eleven import VOICE_SETTINGS
from yue.voice.service import SECRET
from yue.voice.text import tts_text


@pytest.fixture
def vc(controller):  # noqa: F811
    c = controller
    player, client = FakePlayer(), FakeClient()
    c.voice._player_factory = lambda: player
    c.voice._client_factory = lambda key: client
    c.voice.test_player, c.voice.test_client = player, client
    return c


def _with_key(c):
    c.brain.secrets.set(SECRET, KEY)
    c.cfg.set("voice.voice_id", VID)


def test_no_key_text_only(vc, qtbot):
    vc.say_text("happy", "Salom! Bugun nima qilamiz?")
    qtbot.wait(50)
    assert vc.bubble.text.text() or vc.bubble.isVisible()
    assert vc.voice.test_client.calls == [] and vc.voice.test_player.played == []
    assert not vc.voice.is_playing


def test_cached_line_plays_with_talk_animation(vc, qtbot):
    text = "Xayrli tong! Bugun ajoyib kun bo'ladi."
    vc.voice.cache().put(cache_key(vc.voice.model, VOICE_SETTINGS, tts_text(text)), b"mp3", {})
    vc.say_text("happy", text)
    assert len(vc.voice.test_player.played) == 1 and vc.voice.is_playing
    assert vc.behavior.talking
    vc._on_typing(False)  # pufak yozib bo'ldi, ovoz hali davom etyapti
    assert vc.behavior.talking
    vc.voice.test_player.finished.emit()
    assert not vc.voice.is_playing and not vc.behavior.talking


def test_live_line_and_name_pronunciation(vc, qtbot):
    _with_key(vc)
    vc.cfg.set("user.name", "Akmal")
    vc.say_text("happy", "Xayrli tong, Yue!")
    qtbot.waitUntil(lambda: bool(vc.voice.test_player.played))
    assert vc.voice.test_client.calls[0][1] == "Xayrli tong, Yu-e!"
    assert "Yue" in vc.bubble.text.text() or "Yue" in vc.bubble._full


def test_ai_answer_streamed_sentence_by_sentence(vc, qtbot):
    _with_key(vc)
    vc._on_stream("Ha, albatta yordam beraman. Avval")
    qtbot.waitUntil(lambda: len(vc.voice.test_client.calls) == 1)
    final = "Ha, albatta yordam beraman. Avval vazifani yozib qo'yamiz, keyin boshlaymiz."
    vc._on_answered(ChatResult("answer", reply=Reply("happy", final)))
    qtbot.waitUntil(lambda: len(vc.voice.test_client.calls) == 2)
    assert [x[1] for x in vc.voice.test_client.calls] == [
        "Ha, albatta yordam beraman.",
        "Avval vazifani yozib qo'yamiz, keyin boshlaymiz.",
    ]
    assert not vc.voice.cache().dir.exists() or not any(vc.voice.cache().dir.glob("*.mp3"))


def test_ai_answer_not_read_when_disabled(vc, qtbot):
    _with_key(vc)
    vc.cfg.set("voice.read_ai", False)
    vc._on_answered(
        ChatResult("answer", reply=Reply("happy", "Bu javob o'qilmaydi, faqat yoziladi."))
    )
    qtbot.wait(50)
    assert vc.voice.test_client.calls == []


def test_offline_no_tts(vc, qtbot):
    _with_key(vc)
    vc.cfg.set("ai.manba", "offline")
    vc.say_text("happy", "Offline rejimda ovoz so'rovi yo'q.")
    vc._on_answered(ChatResult("answer", reply=Reply("happy", "Lokal model javobi shu yerda.")))
    qtbot.wait(50)
    assert vc.voice.test_client.calls == []


@pytest.mark.parametrize("state", ["drag", "sleep", "fullscreen"])
def test_voice_stops(vc, qtbot, state):
    text = "Uzunroq gap, uni o'ynatib turamiz."
    vc.voice.cache().put(cache_key(vc.voice.model, VOICE_SETTINGS, tts_text(text)), b"mp3", {})
    vc.say_text("happy", text)
    assert vc.voice.is_playing
    if state == "drag":
        vc.on_pet_event("drag", None)
    elif state == "sleep":
        vc.sleep()
    else:
        vc.hidden_by_fullscreen = True
        vc.voice.stop()
    assert not vc.voice.is_playing and vc.voice.test_player.stopped >= 1
    if state == "fullscreen":
        vc.say_text("happy", text)  # to'liq ekranda ovoz chiqmaydi
        assert len(vc.voice.test_player.played) == 1


def test_mute_hotkey_and_menu(vc, qtbot):
    from PySide6.QtWidgets import QMenu

    from yue.i18n import t
    from yue.ui.menu import fill_menu

    assert vc.voice.enabled
    vc.toggle_voice()  # Ctrl+Alt+M
    assert not vc.voice.enabled and vc.cfg.get("voice.enabled") is False
    m = QMenu()
    fill_menu(vc, m)
    act = next(a for a in m.actions() if a.text() == t("menu.voice"))
    assert act.isCheckable() and not act.isChecked()
    act.trigger()
    assert vc.voice.enabled


def test_settings_voice_tab_saves_key_protected(vc, qtbot):
    from yue.ui.settings import SettingsDialog

    dlg = SettingsDialog(vc, tab="voice")
    qtbot.addWidget(dlg)
    assert dlg.tabs.tabText(dlg.tabs.currentIndex()) == "Ovoz"
    dlg.v_key.edit.setText(KEY)
    dlg.v_voice_id.setText(VID)
    dlg.v_daily.setValue(5000)
    dlg.v_model.setCurrentIndex(1)
    dlg._save()
    assert vc.brain.secrets.get(SECRET) == KEY
    raw = vc.cfg.path.read_text(encoding="utf-8")
    assert KEY not in raw
    assert vc.cfg.get("voice.voice_id") == VID and vc.cfg.get("voice.daily_chars") == 5000
    assert vc.voice.model == "eleven_v4_turbo"


def test_settings_check_lists_voices_and_choice_fills_id(vc, qtbot):
    """Avtomatik tanlov yo'q: ro'yxat to'ladi, foydalanuvchi tanlasa — Voice ID maydoniga."""
    from yue.ui.settings import SettingsDialog

    vc.cfg.set("voice.voice_id", "")
    dlg = SettingsDialog(vc, tab="voice")
    qtbot.addWidget(dlg)
    dlg._on_account({"used": 1000, "limit": 30000, "voices": [("x1", "Boshqa"), ("n1", "Yue")]})
    assert dlg.v_voice_id.text() == ""
    assert [dlg.v_voices.itemData(i) for i in range(dlg.v_voices.count())] == ["", "x1", "n1"]
    assert "29000" in dlg.v_key.status.text()
    dlg.v_voices.setCurrentIndex(2)
    assert dlg.v_voice_id.text() == "n1"


def test_stage_button_confirms_then_prepares(vc, qtbot, monkeypatch):
    import yue.ui.settings as st
    from yue.ui.settings import SettingsDialog

    _with_key(vc)
    asked = []
    monkeypatch.setattr(st, "ask", lambda parent, title, text: asked.append(text) or True)
    dlg = SettingsDialog(vc, tab="voice")
    qtbot.addWidget(dlg)
    dlg.v_voice_id.setText(VID)
    dlg._prepare_stage(1)
    assert asked and "harf" in asked[0]
    # fon oqimi tugagach `prepare_done` signali asosiy oqimga keyinroq yetadi — o'shani kutamiz
    qtbot.waitUntil(lambda: "1-bosqich tayyor" in dlg.v_status.text(), timeout=20_000)
    assert not vc.voice.preparing and len(vc.voice.test_client.calls) > 50
    asked.clear()
    dlg._prepare_stage(1)  # hammasi keshda — so'ralmaydi
    assert not asked
