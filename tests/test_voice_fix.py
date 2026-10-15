"""v1.2.1 ovoz tuzatishlari: qurilma almashishi, voice_id himoyasi, ruxsat xatosi, kunlik hisob,
log niqoblash, jim qilish tugmasi."""

import logging

import httpx
import pytest
from PySide6.QtCore import QObject, Signal

from tests.test_i18n import controller  # noqa: F401 — fixture
from tests.test_voice import (
    KEY,
    VID,
    FakeClient,
    FakeDpapi,
    FakePlayer,
    voice,  # noqa: F401 — fixture
)
from yue import hotkey
from yue.config import Config
from yue.logsetup import redact
from yue.memory.crypto import SecretStore
from yue.voice.eleven import ElevenLabs, VoiceError, classify, looks_like_key, valid_voice_id
from yue.voice.service import SECRET, Voice

EL_KEY = "sk_" + "0123456789abcdef" * 3  # ElevenLabs kaliti ko'rinishida (soxta)

# --- 1. Naushnik: standart qurilmaga ergashish ---------------------------------------------------


class FakeDevice:
    def __init__(self, name: str = "") -> None:
        self.name = name

    def isNull(self) -> bool:  # noqa: N802 — Qt nomi
        return not self.name

    def __eq__(self, other: object) -> bool:
        return isinstance(other, FakeDevice) and other.name == self.name

    def __hash__(self) -> int:
        return hash(self.name)


class FakeDevices(QObject):
    audioOutputsChanged = Signal()  # noqa: N815 — Qt nomi
    default = FakeDevice()  # boshida qurilma yo'q

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        FakeDevices.last = self

    def defaultAudioOutput(self) -> FakeDevice:  # noqa: N802
        return FakeDevices.default


class FakeOutput:
    def __init__(self, device: FakeDevice) -> None:
        self.current = device
        self.set_calls: list[str] = []

    def device(self) -> FakeDevice:
        return self.current

    def setDevice(self, dev: FakeDevice) -> None:  # noqa: N802
        self.set_calls.append(dev.name)
        self.current = dev

    def setVolume(self, v: float) -> None:  # noqa: N802
        pass


@pytest.fixture
def qt_player(qapp, monkeypatch):
    import PySide6.QtMultimedia as qm

    from yue.voice.player import QtPlayer

    monkeypatch.setattr(qm, "QMediaDevices", FakeDevices)
    FakeDevices.default = FakeDevice()
    p = QtPlayer()
    p.output = FakeOutput(FakeDevice("kalonka"))
    yield p
    p.stop()


def test_player_follows_default_device(qt_player, qtbot, tmp_path):
    p = qt_player
    FakeDevices.default = FakeDevice("kalonka")
    FakeDevices.last.audioOutputsChanged.emit()
    assert p.output.set_calls == []  # o'zgarmagan — qayta ulanmaydi
    FakeDevices.default = FakeDevice("naushnik")  # naushnik ulandi
    FakeDevices.last.audioOutputsChanged.emit()
    assert p.output.set_calls == ["naushnik"]
    FakeDevices.default = FakeDevice("kalonka")  # uzildi; signal kelmadi — o'ynatishda tekshiriladi
    p.play_file(tmp_path / "yoq.mp3")
    assert p.output.set_calls == ["naushnik", "kalonka"]


def test_player_without_device_stays_silent(qt_player, qtbot):
    p = qt_player
    FakeDevices.default = FakeDevice()  # ovoz qurilmasi yo'q
    with qtbot.waitSignal(p.finished, timeout=2000):
        p.play_bytes(b"ID3mp3")
    assert p.output.set_calls == []


# --- 2. Ovoz ID: kalit yozilib qolmasin ----------------------------------------------------------


def test_voice_id_format():
    assert valid_voice_id(VID) and valid_voice_id("21m00Tcm4TlvDq8ikWAM")
    for bad in (EL_KEY, "sk_abc", "", "abc", "yue 123", "voice/../x", "a" * 40):
        assert not valid_voice_id(bad)
    assert looks_like_key(EL_KEY) and looks_like_key("sk_abc") and not looks_like_key("abc")


def test_synth_refuses_bad_voice_id():
    sent = []
    client = httpx.Client(transport=httpx.MockTransport(lambda r: sent.append(r)))
    el = ElevenLabs(KEY, client=client)
    for bad in (EL_KEY, "abc"):
        with pytest.raises(VoiceError) as exc:
            el.synth(bad, "Salom", "eleven_v4")
        assert exc.value.kind == "bad"
    assert sent == []  # so'rov umuman yuborilmadi


def test_migration_clears_key_in_voice_id(tmp_path, monkeypatch, qapp, caplog):
    monkeypatch.setenv("YUE_DATA", str(tmp_path))
    caplog.set_level(logging.INFO)
    cfg = Config(path=tmp_path / "config.json")
    cfg.set("voice.voice_id", EL_KEY)
    cfg.save()
    client = FakeClient()
    secrets = SecretStore(cfg, FakeDpapi())
    secrets.set(SECRET, KEY)
    v = Voice(cfg, secrets, player_factory=FakePlayer, client_factory=lambda k: client)
    assert cfg.get("voice.voice_id") == "" and EL_KEY not in cfg.path.read_text(encoding="utf-8")
    assert "voice_id tozalandi" in caplog.text and EL_KEY not in caplog.text
    v.speak("Salom, bugun qalaysiz?")
    assert client.calls == []
    v.shutdown()


def test_invalid_voice_id_never_requested(voice, qtbot):  # noqa: F811
    voice.cfg.set("voice.voice_id", "noto'g'ri id")
    voice.speak("Bu gap so'ralmasligi kerak.")
    qtbot.wait(50)
    assert voice.test_client.calls == [] and not voice.can_live()


def test_settings_rejects_key_in_voice_id(controller, qtbot):  # noqa: F811
    from yue.i18n import t
    from yue.ui.settings import SettingsDialog

    c = controller
    c.cfg.set("voice.voice_id", VID)
    dlg = SettingsDialog(c, tab="voice")
    qtbot.addWidget(dlg)
    dlg.v_voice_id.setText(EL_KEY)
    assert dlg.v_voice_id_warn.isVisibleTo(dlg)
    assert dlg.v_voice_id_warn.text() == t("voice.voice_id.key")
    dlg._save()
    assert c.cfg.get("voice.voice_id") == VID  # kalit saqlanmadi, eskisi qoldi
    assert EL_KEY not in c.cfg.path.read_text(encoding="utf-8")
    dlg.v_voice_id.setText("abc")
    assert dlg.v_voice_id_warn.text() == t("voice.voice_id.bad")
    dlg._on_account({"used": 0, "limit": 100, "voices": [(VID, "Yue")]})
    dlg.v_voices.setCurrentIndex(1)  # ro'yxatdan tanlash noto'g'ri qiymatni almashtiradi
    assert dlg.v_voice_id.text() == VID and not dlg.v_voice_id_warn.isVisibleTo(dlg)


# --- 3. Ruxsat yetishmasa — "perm" ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "body", "kind", "perm"),
    [
        (
            401,
            b'{"detail": {"status": "missing_permissions", "message": "The API key you used is '
            b'missing the permission user_read to execute this operation."}}',
            "perm",
            "user_read",
        ),
        (403, b'{"detail": {"code": "insufficient_permissions", "message": "x"}}', "perm", ""),
        (
            401,
            b'{"detail": {"status": "invalid_api_key", "message": "Invalid API key"}}',
            "auth",
            "",
        ),
        (401, b"", "auth", ""),
    ],
)
def test_classify_permission(status, body, kind, perm):
    err = classify(status, body)
    assert err.kind == kind and err.detail == perm


def test_perm_blocks_session_with_one_notification(voice, qtbot):  # noqa: F811
    class PermClient(FakeClient):
        def synth(self, voice_id, text, model):
            self.calls.append((voice_id, text, model))
            raise VoiceError("perm", 401, "user_read")

    client = PermClient()
    voice._client_factory = lambda k: client
    voice._clients.clear()
    notes = []
    voice.notify.connect(lambda title, text: notes.append(text))
    voice.speak("Birinchi gap shu yerda.")
    qtbot.waitUntil(lambda: bool(notes))
    voice.speak("Ikkinchi gap ham bor.")
    qtbot.wait(50)
    assert len(notes) == 1 and len(client.calls) == 1
    assert "ruxsat" in notes[0] and "user_read" in notes[0] and "noto'g'ri" not in notes[0]


def test_settings_check_shows_permission(controller, qtbot):  # noqa: F811
    from yue.ui.settings import SettingsDialog

    dlg = SettingsDialog(controller, tab="voice")
    qtbot.addWidget(dlg)
    dlg._on_account({"error": "perm", "perm": "user_read"})
    text = dlg.v_key.status.text()
    assert "ruxsat yetishmayapti" in text and "user_read" in text


# --- 4. Kunlik hisob faqat muvaffaqiyatdan keyin -------------------------------------------------


@pytest.mark.parametrize("kind", ["bad", "auth", "network"])
def test_failed_request_not_counted(voice, qtbot, kind):  # noqa: F811
    voice.test_client.fail = kind
    voice.speak("Bu so'rov xato bilan tugaydi.")
    qtbot.waitUntil(lambda: bool(voice.test_client.calls))
    qtbot.wait(50)
    assert voice.used_today() == 0 and voice._inflight == 0


def test_success_counted_after_answer(voice, qtbot):  # noqa: F811
    voice.speak("Muvaffaqiyatli gap.")
    qtbot.waitUntil(lambda: bool(voice.test_player.played))
    assert voice.used_today() == len("Muvaffaqiyatli gap.") and voice._inflight == 0


# --- 5. Log niqoblash ----------------------------------------------------------------------------


def test_redact_elevenlabs_openrouter_header():
    or_key = "sk-or-v1-" + "ab12" * 16
    for raw in (
        f"so'rov /v1/text-to-speech/{EL_KEY} xato",
        f"kalit {or_key} ishlamadi",
        "xi-api-key: abcDEF123456",
        "{'xi-api-key': 'abcDEF123456', 'accept': 'audio/mpeg'}",
    ):
        out = redact(raw)
        assert "[yashirildi]" in out
        assert EL_KEY not in out and or_key not in out and "abcDEF123456" not in out


# --- 6. Jim qilish tugmasi -----------------------------------------------------------------------


def test_hotkey_parse():
    c = hotkey.parse(hotkey.DEFAULT_VOICE)
    assert c is not None and c.mods == {"ctrl", "alt", "shift"} and c.key == "U"
    assert c.portable() == "Ctrl+Alt+Shift+U"
    assert hotkey.parse("Meta+F5").portable() == "Meta+F5"
    for bad in ("", "M", "Shift+M", "Ctrl+", "Ctrl+Ctrl+M", "Ctrl+Space", "Ctrl+F25", "Foo+M"):
        assert hotkey.parse(bad) is None


def test_default_hotkey_in_config(tmp_path):
    assert Config(path=tmp_path / "c.json").get("voice.hotkey") == "Ctrl+Alt+Shift+U"


def test_set_voice_hotkey_ok_busy_invalid(controller, monkeypatch):  # noqa: F811
    c = controller
    taken = {"Ctrl+Alt+M"}
    registered = []
    monkeypatch.setattr(
        c.platform,
        "register_combo",
        lambda h, i, combo: combo.portable() not in taken and not registered.append(combo),
    )
    assert c.set_voice_hotkey("Ctrl+Alt+Shift+V") == "ok"
    assert c.voice_hotkey == "Ctrl+Alt+Shift+V" and c.hotkey_voice_ok
    assert c.cfg.get("voice.hotkey") == "Ctrl+Alt+Shift+V"
    assert c.set_voice_hotkey("Ctrl+Alt+M") == "busy"  # band — eskisi qaytadan
    assert c.voice_hotkey == "Ctrl+Alt+Shift+V" and c.hotkey_voice_ok
    assert registered[-1].portable() == "Ctrl+Alt+Shift+V"
    assert c.cfg.get("voice.hotkey") == "Ctrl+Alt+Shift+V"
    assert c.set_voice_hotkey("M") == "invalid"


def test_settings_hotkey_field_busy_message(controller, qtbot, monkeypatch):  # noqa: F811
    from PySide6.QtGui import QKeySequence

    from yue.i18n import t
    from yue.ui.settings import SettingsDialog

    c = controller
    monkeypatch.setattr(c.platform, "register_combo", lambda h, i, combo: False)  # hammasi band
    dlg = SettingsDialog(c, tab="voice")
    qtbot.addWidget(dlg)
    assert dlg.v_hotkey.keySequence().toString(QKeySequence.SequenceFormat.PortableText) == (
        "Ctrl+Alt+Shift+U"
    )
    dlg.v_hotkey.setKeySequence(QKeySequence("Ctrl+Alt+K"))
    dlg._apply_hotkey()
    assert dlg.v_hotkey_status.text() == t("voice.hotkey.busy")
    monkeypatch.setattr(c.platform, "register_combo", lambda h, i, combo: True)
    dlg._apply_hotkey()
    assert dlg.v_hotkey_status.text() == t("voice.hotkey.ok", combo="Ctrl+Alt+K")
    assert c.cfg.get("voice.hotkey") == "Ctrl+Alt+K"
