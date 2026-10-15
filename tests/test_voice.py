"""Ovoz (ElevenLabs): provayder (soxta HTTP), matn, kesh, bosqichlar, xizmat. Tarmoq yo'q."""

import datetime as dt
import json
import logging
import threading

import httpx
import pytest
from PySide6.QtCore import QObject, Signal

from yue.config import Config
from yue.lines import Lines
from yue.memory.crypto import SecretStore
from yue.platform import NullPlatform
from yue.voice import stages
from yue.voice.cache import VoiceCache, cache_key
from yue.voice.eleven import VOICE_SETTINGS, ElevenLabs, VoiceError, api_settings
from yue.voice.service import SECRET, Voice
from yue.voice.text import number_words, split_complete, split_sentences, tts_text

KEY = "sk_test_0123456789abcdef"  # soxta kalit (haqiqiy emas)
VID = "YueVoice0123456789A"  # soxta voice_id (ElevenLabs formatida, 20 belgi)


# --- provayder ----------------------------------------------------------------------------------


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_synth_request_shape():
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, content=b"ID3mp3")

    el = ElevenLabs(KEY, client=_client(handler))
    assert el.synth(VID, "Salom!", "eleven_v4") == b"ID3mp3"
    req = seen[0]
    body = json.loads(req.content)
    assert req.method == "POST" and req.url.path == f"/v1/text-to-speech/{VID}"
    assert req.url.params["output_format"] == "mp3_44100_128"
    assert body["model_id"] == "eleven_v4" and body["language_code"] == "uz"
    assert body["voice_settings"]["stability"] == 0.5
    assert body["voice_settings"]["similarity_boost"] == 0.75
    assert body["text"] == "Salom!"
    assert req.headers["xi-api-key"] == KEY
    assert KEY not in str(req.url) and KEY not in repr(el)


def test_speed_sent_only_when_not_default():
    assert "speed" not in api_settings()  # Eleven v4: tezlik standarti (1.0) — yuborilmaydi
    assert api_settings({**VOICE_SETTINGS, "speed": 1.1})["speed"] == 1.1


@pytest.mark.parametrize(
    ("status", "body", "kind"),
    [
        (401, b'{"detail": {"status": "invalid_api_key"}}', "auth"),
        (402, b"{}", "credits"),
        (401, b'{"detail": {"status": "quota_exceeded"}}', "credits"),
        (500, b"", "bad"),
    ],
)
def test_synth_errors(status, body, kind):
    el = ElevenLabs(KEY, client=_client(lambda r: httpx.Response(status, content=body)))
    with pytest.raises(VoiceError) as exc:
        el.synth(VID, "Salom", "eleven_v4")
    assert exc.value.kind == kind


def test_429_waits_and_retries():
    calls, slept = [], []

    def handler(req):
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(429, headers={"retry-after": "2"})
        return httpx.Response(200, content=b"mp3")

    el = ElevenLabs(KEY, client=_client(handler), sleep=slept.append)
    assert el.synth(VID, "Salom", "eleven_v4") == b"mp3"
    assert len(calls) == 3 and slept == [2.0, 2.0]


def test_429_gives_up():
    el = ElevenLabs(KEY, client=_client(lambda r: httpx.Response(429)), sleep=lambda s: None)
    with pytest.raises(VoiceError) as exc:
        el.synth(VID, "Salom", "eleven_v4")
    assert exc.value.kind == "rate"


def test_network_error():
    def handler(req):
        raise httpx.ConnectError("yo'q")

    with pytest.raises(VoiceError) as exc:
        ElevenLabs(KEY, client=_client(handler)).synth(VID, "Salom", "eleven_v4")
    assert exc.value.kind == "network"


def test_credits_and_voices():
    def handler(req):
        if req.url.path == "/v1/user/subscription":
            return httpx.Response(200, json={"character_count": 1200, "character_limit": 30000})
        return httpx.Response(200, json={"voices": [{"voice_id": "abc", "name": "Yue"}]})

    el = ElevenLabs(KEY, client=_client(handler))
    assert el.credits() == (1200, 30000)
    assert el.voices() == [("abc", "Yue")]


# --- matn ------------------------------------------------------------------------------------


def test_numbers_to_words():
    assert number_words(0) == "nol"
    assert number_words(15) == "o'n besh"
    assert number_words(100) == "yuz"
    assert number_words(245) == "ikki yuz qirq besh"
    assert number_words(1000) == "ming"
    assert number_words(2026) == "ikki ming yigirma olti"
    assert number_words(9999) == "to'qqiz ming to'qqiz yuz to'qson to'qqiz"
    assert tts_text("Soat 15:30 da") == "Soat o'n besh o'ttiz da"
    assert tts_text("9:05 bo'ldi") == "to'qqiz nol besh bo'ldi"
    assert tts_text("Batareya 15%") == "Batareya o'n besh foiz"
    assert tts_text("3 ta vazifa") == "uch ta vazifa"


def test_lexicon_and_actions_only_in_voice_text():
    assert tts_text("Xayrli tong, Yue!") == "Xayrli tong, Yu-e!"
    assert tts_text("yue, salom") == "Yu-e, salom"
    assert tts_text("Yueni") == "Yueni"  # so'z chegarasi
    assert tts_text("*jilmayadi* Bu... juda yoqimli.") == "Bu... juda yoqimli."
    assert tts_text("*boshini egadi*") == ""


def test_bubble_keeps_original_name(monkeypatch):
    lines = Lines.load()
    lines.name_fn = lambda: "Akmal"
    texts = {lines.pick("welcome_back")[1] for _ in range(300)}
    assert any("Akmal" in x for x in texts)  # pufakda — asl yozilishi


def test_sentence_split():
    parts, used = split_complete("Salom! Bugun nima qilamiz? Men esa hali yoz")
    assert parts == ["Salom! Bugun nima qilamiz?"] and used == len("Salom! Bugun nima qilamiz? ")
    assert split_sentences("Birinchi uzun gap shu yerda. Ikkinchi gap ham bor!") == [
        "Birinchi uzun gap shu yerda.",
        "Ikkinchi gap ham bor!",
    ]


# --- kesh va bosqichlar -------------------------------------------------------------------------


def test_cache_key_stable():
    a = cache_key("eleven_v4", VOICE_SETTINGS, "Salom")
    assert a == cache_key("eleven_v4", dict(reversed(VOICE_SETTINGS.items())), "Salom")
    assert a != cache_key("eleven_v4_turbo", VOICE_SETTINGS, "Salom")
    assert a != cache_key("eleven_v4", {**VOICE_SETTINGS, "stability": 0.6}, "Salom")
    assert a != cache_key("eleven_v4", VOICE_SETTINGS, "Salom!")
    assert len(a) == 64


def test_stages_cover_every_key_once():
    data = Lines.load().data
    st = stages.load_stages()
    keys = stages.stage_keys(data, st)
    listed = [k for n in (1, 2) for k in st[n]]
    assert len(listed) == len(set(listed))
    assert set(listed) <= set(keys)  # ro'yxatdagi har kalit iboralar.json da bor
    assert set(keys) == {k for k, v in data.items() if isinstance(v, dict | list)}
    assert "yaqin" not in keys and keys["greet"] == 1 and keys["hazil"] == 2
    assert keys["manba"] == 3
    every = {x for n in (1, 2, 3) for x in stages.stage_texts(data, n, "Akmal")}
    canned = {x for x in stages._texts(data) if "{" not in x}  # Yue aytadigan hamma gap
    assert canned <= every  # 1 + 2 + 3 = hamma o'zgaruvchisiz gap


def test_stage_texts_skip_variables_and_fill_name():
    data = Lines.load().data
    texts = [x for n in (1, 2, 3) for x in stages.stage_texts(data, n, "Akmal")]
    assert texts and not any("{" in x for x in texts)
    assert "Ana, Akmal keldi! Qalay, hammasi joyidami?" in texts
    no_name = [x for n in (1, 2, 3) for x in stages.stage_texts(data, n, "")]
    assert "Suv ichdingizmi? Rostini ayting." in no_name
    assert not any("Akmal" in x or "Ana, " in x and "keldi" in x for x in no_name)


def test_prepare_skips_cached_and_resumes(tmp_path):
    data = Lines.load().data
    cache = VoiceCache("voice1", root=tmp_path)
    todo, chars = stages.plan(data, 1, "Akmal", "eleven_v4", VOICE_SETTINGS, cache)
    assert todo and chars == sum(len(i.tts) for i in todo)
    calls = []
    stop = threading.Event()

    def synth(tts):
        calls.append(tts)
        if len(calls) == 5:
            stop.set()  # foydalanuvchi "To'xtatish"ni bosdi
        return b"mp3"

    assert stages.run(todo, synth, cache, 1, "Akmal", stop, lambda d, n: None) == "stopped"
    assert len(calls) == 5
    rest, _ = stages.plan(data, 1, "Akmal", "eleven_v4", VOICE_SETTINGS, cache)
    assert len(rest) == len(todo) - 5  # keshdagilar qayta yasalmaydi
    calls.clear()
    assert stages.run(rest, lambda s: calls.append(s) or b"mp3", cache, 1, "Akmal",
                      threading.Event(), lambda d, n: None) == "done"  # fmt: skip
    assert len(calls) == len(rest)
    assert stages.plan(data, 1, "Akmal", "eleven_v4", VOICE_SETTINGS, cache)[0] == []
    # Ism o'zgardi: faqat {ism} li gaplar qayta yasaladi
    named = [k for k, m in cache.index.items() if m.get("ism") == "Akmal"]
    assert named and cache.forget_names("Ali") == len(named)
    again, _ = stages.plan(data, 1, "Ali", "eleven_v4", VOICE_SETTINGS, cache)
    assert again and all(i.named for i in again)


def test_prepare_stops_on_credit_error(tmp_path):
    cache = VoiceCache("v", root=tmp_path)
    todo, _ = stages.plan(Lines.load().data, 1, "", "eleven_v4", VOICE_SETTINGS, cache)

    def synth(tts):
        raise VoiceError("credits", 402)

    assert stages.run(todo, synth, cache, 1, "", threading.Event(), lambda d, n: None) == "credits"


# --- xizmat -------------------------------------------------------------------------------------


class FakePlayer(QObject):
    finished = Signal()

    def __init__(self):
        super().__init__()
        self.played: list = []
        self.stopped = 0
        self.volume = None

    def set_volume(self, v):
        self.volume = v

    def play_file(self, path):
        self.played.append(path)

    def play_bytes(self, data):
        self.played.append(data)

    def stop(self):
        self.stopped += 1


class FakeClient:
    def __init__(self, fail=None):
        self.calls: list[tuple] = []
        self.fail = fail

    def synth(self, voice_id, text, model):
        self.calls.append((voice_id, text, model))
        if self.fail:
            raise VoiceError(self.fail)
        return f"mp3:{text}".encode()


class FakeDpapi(NullPlatform):
    def protect(self, data):
        return data[::-1]

    def unprotect(self, blob):
        return blob[::-1]


@pytest.fixture
def voice(tmp_path, monkeypatch, qapp):
    monkeypatch.setenv("YUE_DATA", str(tmp_path))
    cfg = Config(path=tmp_path / "config.json")
    secrets = SecretStore(cfg, FakeDpapi())
    secrets.set(SECRET, KEY)
    cfg.set("voice.voice_id", VID)
    player, client = FakePlayer(), FakeClient()
    v = Voice(cfg, secrets, player_factory=lambda: player, client_factory=lambda k: client)
    v.test_player, v.test_client = player, client
    yield v
    v.shutdown()


def test_cached_line_plays_without_request(voice, qtbot):
    tts = tts_text("Salom, Yue!")
    voice.cache().put(cache_key(voice.model, VOICE_SETTINGS, tts), b"mp3", {})
    voice.speak("Salom, Yue!")
    assert len(voice.test_player.played) == 1 and voice.test_client.calls == []
    assert voice.is_playing
    voice.test_player.finished.emit()
    assert not voice.is_playing


def test_live_line_sends_voice_text(voice, qtbot):
    voice.speak("Xayrli tong, Yue! Soat 9:30.")
    qtbot.waitUntil(lambda: bool(voice.test_player.played))
    assert voice.test_client.calls == [(VID, "Xayrli tong, Yu-e! Soat to'qqiz o'ttiz.",
                                        "eleven_v4")]  # fmt: skip
    assert voice.used_today() == len(voice.test_client.calls[0][1])


def test_ai_reply_sentence_by_sentence(voice, qtbot):
    voice.stream_update("Salom! Bugun ajoyib kun bo'ladi. Ha")
    qtbot.waitUntil(lambda: len(voice.test_client.calls) == 1)
    assert voice.test_client.calls[0][1] == "Salom! Bugun ajoyib kun bo'ladi."
    qtbot.waitUntil(lambda: len(voice.test_player.played) == 1)  # birinchi gap darhol o'ynaydi
    voice.stream_end("Salom! Bugun ajoyib kun bo'ladi. Hali ko'p ishimiz bor, boshlaymiz.")
    qtbot.waitUntil(lambda: len(voice.test_client.calls) == 2)
    assert voice.test_client.calls[1][1] == "Hali ko'p ishimiz bor, boshlaymiz."
    voice.test_player.finished.emit()
    qtbot.waitUntil(lambda: len(voice.test_player.played) == 2)


def test_ai_reply_not_cached(voice, qtbot):
    voice.speak_ai("Bu sizning shaxsiy gapingiz haqida javob.")
    qtbot.waitUntil(lambda: bool(voice.test_player.played))
    assert not voice.cache().dir.exists() or not any(voice.cache().dir.glob("*.mp3"))


def test_new_line_stops_old(voice, qtbot):
    voice.speak("Birinchi uzun gap, keling gaplashamiz.")
    qtbot.waitUntil(lambda: bool(voice.test_player.played))
    voice.speak("Ikkinchi gap.")
    assert voice.test_player.stopped >= 1


def test_read_ai_off(voice, qtbot):
    voice.cfg.set("voice.read_ai", False)
    voice.speak_ai("Bu javob ovozda o'qilmasligi kerak.")
    qtbot.wait(50)
    assert voice.test_client.calls == []


def test_offline_never_calls_tts(voice, qtbot):
    voice.cfg.set("ai.manba", "offline")
    voice.speak("Salom, qalaysiz?")
    voice.speak_ai("Javob matni shu yerda.")
    voice.stream_update("Oqimdagi gap tugadi. ")
    qtbot.wait(50)
    assert voice.test_client.calls == []
    assert voice.prepare_blocker() == "voice.prep.offline"
    assert not voice.start_prepare(Lines.load().data, 1, "")


def test_daily_limit(voice, qtbot):
    voice.cfg.set("voice.daily_chars", 30)
    hit = []
    voice.limit_reached.connect(lambda: hit.append(1))
    voice.speak("Yigirma harfli gap shu.")  # 23 harf
    qtbot.waitUntil(lambda: len(voice.test_client.calls) == 1)
    voice.speak("Bu gap chegaradan oshadi.")
    qtbot.wait(50)
    assert len(voice.test_client.calls) == 1 and hit == [1] and voice.off_today()
    voice.speak("Yana bir gap.")  # ovoz bugun o'chgan
    assert len(voice.test_client.calls) == 1 and hit == [1]
    voice._today = lambda: dt.date.today() + dt.timedelta(days=1)  # ertasi kun
    assert not voice.off_today() and voice.used_today() == 0


@pytest.mark.parametrize("kind", ["auth", "credits"])
def test_key_or_credit_error_one_notification(voice, qtbot, kind):
    voice.test_client.fail = kind
    notes = []
    voice.notify.connect(lambda title, text: notes.append(text))
    voice.speak("Birinchi gap shu yerda.")
    qtbot.waitUntil(lambda: bool(notes))
    voice.speak("Ikkinchi gap ham bor.")
    qtbot.wait(50)
    assert len(notes) == 1 and len(voice.test_client.calls) == 1  # keyin so'rov yo'q
    assert voice.test_player.played == []


def test_no_key_silent(voice, qtbot):
    voice.secrets.set(SECRET, None)
    voice.speak("Kalitsiz gap.")
    qtbot.wait(50)
    assert voice.test_client.calls == [] and voice.test_player.played == []


def test_key_not_in_config_or_log(voice, qtbot, caplog):
    caplog.set_level(logging.DEBUG)
    voice.test_client.fail = "auth"
    voice.speak("Logga tushmasligi kerak bo'lgan gap.")
    qtbot.waitUntil(lambda: bool(voice.test_client.calls))
    qtbot.wait(50)
    voice.cfg.save()
    raw = voice.cfg.path.read_text(encoding="utf-8")
    assert KEY not in raw and "elevenlabs_key" in raw
    assert KEY not in caplog.text and "Logga tushmasligi" not in caplog.text
