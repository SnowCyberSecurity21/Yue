"""Ovozning kunlik chegarasi (kesh o'ynaydi, chegara o'zgarsa qaytadi, bildirishnoma) va gap
bir martalik reaksiyani (land, sayr oxiridagi wave) kesmasligi."""

import logging

from tests.test_behavior import Sim, drop_from, meta  # noqa: F401 — fixture
from tests.test_commands import run_cmd
from tests.test_i18n import controller  # noqa: F401 — fixture
from tests.test_voice import KEY, VID, voice  # noqa: F401 — fixture
from yue.i18n import t
from yue.voice.cache import cache_key
from yue.voice.eleven import VOICE_SETTINGS
from yue.voice.text import tts_text

LONG = "Bu gap kunlik chegaradan albatta oshadi, juda uzun."


def _exhaust(voice, qtbot):  # noqa: F811
    voice.cfg.set("voice.daily_chars", 30)
    voice.speak("Yigirma harfli gap shu.")  # 23 harf
    qtbot.waitUntil(lambda: len(voice.test_client.calls) == 1)
    voice.speak(LONG)
    qtbot.wait(30)
    assert voice.off_today()


# --- A. ovoz chegarasi ---------------------------------------------------------------------------


def test_cached_line_plays_when_limit_off(voice, qtbot):  # noqa: F811
    _exhaust(voice, qtbot)
    tts = tts_text("Keshdagi ibora.")
    voice.cache().put(cache_key(voice.model, VOICE_SETTINGS, tts), b"mp3", {})
    played = len(voice.test_player.played)
    voice.speak("Keshdagi ibora.")
    assert len(voice.test_player.played) == played + 1  # kesh kredit sarflamaydi
    voice.speak("Keshda yo'q yangi gap.")
    voice.speak_ai("AI javobi ham jonli o'qilmaydi.")
    qtbot.wait(30)
    assert len(voice.test_client.calls) == 1  # jonli so'rov yo'q


def test_raising_limit_cancels_off_but_same_limit_keeps_it(voice, qtbot):  # noqa: F811
    _exhaust(voice, qtbot)
    voice.set_daily_limit(30)  # o'zgarmadi
    assert voice.off_today()
    voice.set_daily_limit(10)  # ishlatilganidan kichik — off qoladi
    assert voice.off_today()
    voice.set_daily_limit(1000)
    assert not voice.off_today() and voice.daily_limit == 1000
    _exhaust(voice, qtbot)  # chegara 30 ga qaytdi — yana o'chdi
    voice.set_daily_limit(0)  # cheklovsiz
    assert not voice.off_today()


def test_limit_notifies_once_and_logs(voice, qtbot, caplog):  # noqa: F811
    caplog.set_level(logging.INFO)
    notes, hits = [], []
    voice.notify.connect(lambda title, text: notes.append((title, text)))
    voice.limit_reached.connect(lambda: hits.append(1))
    _exhaust(voice, qtbot)
    assert notes == [(t("voice.notify.title"), t("voice.notify.limit", limit=30))]
    assert "ovoz: kunlik chegara tugadi (23/30)" in caplog.text
    voice.set_daily_limit(1000)  # qaytdi
    voice.set_daily_limit(30)  # va yana tugaydi — bugun ikkinchi bildirishnoma yo'q
    voice.speak(LONG)
    qtbot.wait(30)
    assert voice.off_today() and len(notes) == 1 and len(hits) == 2


def test_startup_log_has_no_secrets(voice, caplog):  # noqa: F811
    caplog.set_level(logging.INFO)
    voice.log_state()
    line = caplog.records[-1].getMessage()
    assert line.startswith("ovoz: yoqilgan=ha") and "ovoz_id=bor" in line and "kalit_bor=ha" in line
    assert KEY not in caplog.text and VID not in caplog.text


def test_menu_marks_voice_off_today(controller, monkeypatch):  # noqa: F811
    from PySide6.QtWidgets import QMenu

    from yue.ui.menu import fill_menu

    c = controller
    m = QMenu()
    fill_menu(c, m, tray=True)
    assert t("menu.voice") in [a.text() for a in m.actions()]
    monkeypatch.setattr(c.voice, "off_today", lambda: True)
    m = QMenu()
    fill_menu(c, m, tray=True)
    assert t("menu.voice.off_today") in [a.text() for a in m.actions()]


# --- B. gap reaksiyani kesmaydi -----------------------------------------------------------------


def _land(meta):  # noqa: F811
    sim = Sim(meta, seed=4, outfit="tee").run(3)
    drop_from(sim)
    while sim.bh.activity != "land":
        sim.run(0.05)
    return sim


def test_land_finishes_then_talk(meta):  # noqa: F811
    sim = _land(meta)
    sim.bh.set_talking(sim.t, True)  # "Otdingizmi?!" darhol
    sim.run(0.3)
    assert sim.visuals[-1].slot == "land"
    sim.run(4)
    n = meta.variant("land", "tee").frames
    lands = [v.frame for v in sim.visuals if v.slot == "land"]
    assert sorted(set(lands)) == list(range(n))  # oxirigacha
    assert sim.visuals[-1].slot == "talk" and sim.bh.activity == "talk"


def test_speech_ending_during_land_never_starts_talk(meta):  # noqa: F811
    sim = _land(meta)
    sim.bh.set_talking(sim.t, True)
    sim.run(0.3)
    sim.bh.set_talking(sim.t, False, "angry")  # gap land davomida tugadi
    sim.visuals.clear()
    sim.run(4)
    slots = [v.slot for v in sim.visuals]
    assert "talk" not in slots and "expressions" in slots  # gapdan keyingi ifoda


def test_sayr_end_wave_not_cut_by_talk(meta):  # noqa: F811
    sim = Sim(meta, outfit="tee").run(3)
    run_cmd(sim, "sayr", seconds=5.0)
    while sim.bh.step is None or sim.bh.step.slot != "wave":
        sim.run(0.05)
    sim.bh.set_talking(sim.t, True)  # sayr oxiridagi gap
    sim.run(0.5)
    assert sim.visuals[-1].slot == "wave"
    sim.run(3)
    assert sim.visuals[-1].slot == "talk"


def test_drag_still_interrupts_reaction(meta):  # noqa: F811
    sim = _land(meta)
    sim.bh.set_talking(sim.t, True)
    sim.bh.start_drag(sim.t)
    sim.bh.drag_to(600, 300)
    sim.run(0.2)
    assert sim.visuals[-1].slot == "dangle" and not sim.bh._talk_wait
