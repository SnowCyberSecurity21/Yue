"""Ovoz xizmati: Yue gapirganda nimani, qachon va qanday o'ynatish.

- Tayyor ibora: keshda bo'lsa — darhol; bo'lmasa va jonli o'qish mumkin bo'lsa (Online, kalit va
  voice_id bor, kunlik chegara tugamagan) — so'rov; aks holda jim.
- AI javobi: gap-gap bo'lib navbat bilan so'raladi, birinchi gap tayyor bo'lishi bilan o'ynaydi.
  Keshlanmaydi — faqat xotirada.
- Yangi gap eskisini to'xtatadi (`stop`). `allowed()` — ilova holati (to'liq ekran, uyqu, sudrash).
- Offline (`ai.manba = offline`) — hech qanday TTS so'rovi yo'q (keshdagi tayyor iboralar o'ynaydi).
- Kunlik chegara (harf): so'rovdan oldin tekshiriladi, harflar esa faqat ovoz muvaffaqiyatli
  kelgandan keyin qo'shiladi. Oshsa, shu kun oxirigacha faqat jonli so'rov to'xtaydi (keshdagi
  iboralar o'ynayveradi), bitta ibora aytiladi, kuniga bir marta bildirishnoma va log qatori.
  Chegara oshirilsa yoki 0 qilinsa (`set_daily_limit`), bugungi o'chirish bekor bo'ladi.
- Xatolar: 401 — kalit noto'g'ri, ruxsat yetishmaydi (perm), 402/kredit tugadi — bitta
  bildirishnoma va shu seansda jonli o'qish to'xtaydi; 429 — provayder ichida kutib qayta urinadi.
  Ovoz ishlamasa, Yue matn bilan davom etadi.
- voice_id faqat ElevenLabs formatida; config'da boshqa narsa (masalan, adashib yozilgan API kalit)
  bo'lsa, ishga tushishda tozalanadi.

Tarmoq so'rovlari alohida oqimda; natija Qt signal orqali UI oqimiga keladi.
"""

from __future__ import annotations

import datetime as dt
import logging
import queue
import threading
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

from yue import modes
from yue.i18n import t
from yue.memory.crypto import CryptoError
from yue.voice import stages
from yue.voice.cache import VoiceCache, cache_key
from yue.voice.eleven import (
    MODEL_STANDARD,
    MODELS,
    VOICE_SETTINGS,
    ElevenLabs,
    VoiceError,
    valid_voice_id,
)
from yue.voice.text import split_complete, split_sentences, tts_text

log = logging.getLogger(__name__)

SECRET = "elevenlabs_key"  # noqa: S105 — SecretStore dagi yozuv nomi, kalit emas
DEFAULT_DAILY_CHARS = 3000
_PENDING = object()  # so'rov yuborildi, javob hali yo'q


def error_text(kind: str, perm: str = "") -> str:
    """Bildirishnoma matni; perm — javobda ruxsat nomi bo'lsa, u ham ko'rsatiladi."""
    text = t(f"voice.notify.{kind}")
    if kind == "perm" and perm:
        text += " " + t("voice.perm.name", perm=perm)
    return text


class Voice(QObject):
    playing = Signal(bool)  # ovoz o'ynay boshladi / navbat tugadi (gapirish animatsiyasi)
    notify = Signal(str, str)  # (sarlavha, matn) — bildirishnoma
    limit_reached = Signal()  # kunlik chegara — Yue bitta ibora aytadi
    progress = Signal(int, int)  # tayyorlash: (bajarildi, jami)
    prepare_done = Signal(str)  # done / stopped / auth / credits / network / …
    account = Signal(object)  # Tekshirish natijasi (lug'at)
    _ready = Signal(int, int, object, int)  # (gen, idx, mp3 yoki None, so'ralgan harflar)
    _failed = Signal(int, str, str)  # (gen, xato turi, ruxsat nomi)

    def __init__(
        self,
        cfg,
        secrets,
        allowed: Callable[[], bool] = lambda: True,
        player_factory: Callable[[], Any] | None = None,
        client_factory: Callable[[str], Any] | None = None,
        today: Callable[[], dt.date] = dt.date.today,
    ) -> None:
        super().__init__()
        self.cfg = cfg
        self.secrets = secrets
        self.allowed = allowed
        self._player_factory = player_factory
        self._client_factory = client_factory or ElevenLabs
        self._today = today
        self._player: Any = None
        self._clients: dict[str, Any] = {}
        self._cache: VoiceCache | None = None
        self._gen = 0
        self._items: dict[int, Any] = {}
        self._n = 0
        self._next = 0
        self._busy = False
        self._is_playing = False
        self._stream_on = False
        self._stream_used = 0
        self._blocked: str | None = None  # auth / perm / credits — shu seansda jonli o'qish yo'q
        self._inflight = 0  # yuborilgan, javobi hali kelmagan harflar (chegara tekshiruvi uchun)
        self._jobs: queue.Queue[tuple | None] = queue.Queue()
        self._worker: threading.Thread | None = None
        self._prep_stop = threading.Event()
        self._prep_thread: threading.Thread | None = None
        self.last_credits: tuple[int, int] | None = None
        self._ready.connect(self._on_ready)
        self._failed.connect(self._on_failed)
        self._migrate_voice_id()

    def _migrate_voice_id(self) -> None:
        """Formatga mos kelmagan voice_id (masalan, kalit) — tozalanadi; qiymat logga yozilmaydi."""
        raw = str(self.cfg.get("voice.voice_id", "") or "").strip()
        if raw and not valid_voice_id(raw):
            self.cfg.set("voice.voice_id", "")
            self.cfg.save()
            log.info("voice_id tozalandi")

    # --- sozlamalar ---------------------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return bool(self.cfg.get("voice.enabled", True))

    def set_enabled(self, on: bool) -> None:
        self.cfg.set("voice.enabled", bool(on))
        self.cfg.save()
        if not on:
            self.stop()

    @property
    def voice_id(self) -> str:
        v = str(self.cfg.get("voice.voice_id", "") or "").strip()
        return v if valid_voice_id(v) else ""

    @property
    def model(self) -> str:
        m = str(self.cfg.get("voice.model", MODEL_STANDARD) or MODEL_STANDARD)
        return m if m in MODELS else MODEL_STANDARD

    @property
    def read_ai(self) -> bool:
        return bool(self.cfg.get("voice.read_ai", True))

    @property
    def volume(self) -> float:
        try:
            return max(0, min(100, int(self.cfg.get("voice.volume", 80)))) / 100
        except (TypeError, ValueError):
            return 0.8

    @property
    def daily_limit(self) -> int:
        try:
            return max(0, int(self.cfg.get("voice.daily_chars", DEFAULT_DAILY_CHARS)))
        except (TypeError, ValueError):
            return DEFAULT_DAILY_CHARS

    def key(self) -> str | None:
        try:
            return self.secrets.get(SECRET)
        except CryptoError:
            return None

    def has_key(self) -> bool:
        return self.secrets.has(SECRET)

    def online(self) -> bool:
        return modes.source(self.cfg) == "online"

    def reload(self) -> None:
        """Sozlamalar saqlandi: kalit/voice_id o'zgargan bo'lishi mumkin — blok olib tashlanadi."""
        self._blocked = None
        self._clients.clear()
        self._cache = None
        if self._player is not None:
            self._player.set_volume(self.volume)
        if not self.enabled:
            self.stop()

    def cache(self) -> VoiceCache:
        if self._cache is None or self._cache.dir.name != VoiceCache(self.voice_id).dir.name:
            self._cache = VoiceCache(self.voice_id)
        return self._cache

    # --- kunlik chegara -------------------------------------------------------------------------

    def _usage(self) -> dict[str, Any]:
        u = self.cfg.get("voice.usage", {}) or {}
        today = self._today().isoformat()
        if not isinstance(u, dict) or u.get("day") != today:
            u = {"day": today, "chars": 0, "off": False}
        return dict(u)

    def off_today(self) -> bool:
        return bool(self._usage().get("off"))

    def used_today(self) -> int:
        return int(self._usage().get("chars", 0))

    def _within_limit(self, n: int) -> bool:
        """So'rovdan oldin: chegaraga sig'adimi (hisobga qo'shmaydi). Sig'masa — shu kun jonli
        so'rov o'chadi (kesh o'ynayveradi)."""
        u = self._usage()
        if u.get("off"):
            return False
        limit = self.daily_limit
        if limit and int(u["chars"]) + self._inflight + n > limit:
            first = not u.get("notified")
            u["off"] = u["notified"] = True
            self.cfg.set("voice.usage", u)
            self.cfg.save()
            self.stop()
            log.info("ovoz: kunlik chegara tugadi (%d/%d)", int(u["chars"]), limit)
            if first:  # kuniga bir marta
                self.notify.emit(t("voice.notify.title"), t("voice.notify.limit", limit=limit))
            self.limit_reached.emit()
            return False
        return True

    def set_daily_limit(self, limit: int) -> None:
        """Sozlamalar: yangi kunlik chegara. O'zgarsa va bugun ishlatilganidan katta (yoki 0 —
        cheklovsiz) bo'lsa, bugungi o'chirish bekor bo'ladi. O'zgarmasa — hech narsa."""
        limit = max(0, int(limit))
        if limit == self.daily_limit:
            return
        self.cfg.set("voice.daily_chars", limit)
        u = self._usage()
        if u.get("off") and (limit == 0 or limit > int(u["chars"])):
            u["off"] = False
            self.cfg.set("voice.usage", u)
            log.info("ovoz: kunlik chegara o'zgardi — ovoz qaytdi")

    def log_state(self) -> None:
        """Ishga tushganda bitta qator (kalit va voice_id qiymatlari yozilmaydi)."""
        log.info(
            "ovoz: yoqilgan=%s, manba=%s, ovoz_id=%s, kalit_bor=%s, bugun %d/%d, off=%s",
            "ha" if self.enabled else "yo'q",
            "online" if self.online() else "offline",
            "bor" if self.voice_id else "yo'q",
            "ha" if self.has_key() else "yo'q",
            self.used_today(),
            self.daily_limit,
            "ha" if self.off_today() else "yo'q",
        )

    def _add_usage(self, n: int) -> None:
        """Ovoz muvaffaqiyatli keldi — harflar bugungi hisobga qo'shiladi."""
        u = self._usage()
        u["chars"] = int(u["chars"]) + n
        self.cfg.set("voice.usage", u)
        self.cfg.save()

    # --- qaror ----------------------------------------------------------------------------------

    def active(self) -> bool:
        """Ovoz chiqishi mumkinmi. Kunlik chegara bu yerda emas — u faqat jonli so'rovni
        to'xtatadi (`_live`), keshdagi iboralar kredit sarflamaydi."""
        return self.enabled and self.allowed()

    def can_live(self) -> bool:
        """Jonli so'rov yuborish mumkinmi (chegaradan tashqari)."""
        return self.online() and self._blocked is None and bool(self.voice_id) and self.has_key()

    def _live(self, tts: str) -> bool:
        return self.can_live() and self._within_limit(len(tts))

    # --- gapirish -------------------------------------------------------------------------------

    def speak(self, text: str) -> None:
        """Tayyor ibora (yoki tizim gapi): kesh → jonli → jim."""
        self.stop()
        if not self.active():
            return
        tts = tts_text(text)
        if not tts:
            return
        path = self.cache().get(cache_key(self.model, VOICE_SETTINGS, tts))
        if path is not None:
            self._push(path)
        elif self._live(tts):
            self._push_live(tts)

    def speak_ai(self, text: str) -> None:
        """AI javobi (oqimsiz kelgan): gap-gap bo'lib."""
        self.stop()
        if self.active() and self.read_ai:
            for s in split_sentences(text):
                self._ai_sentence(s)

    def stream_update(self, visible: str) -> None:
        """AI javobi oqimda: tugagan gaplar navbatga qo'shiladi."""
        if not visible:  # zanjir boshqa provayderga o'tdi — yarim javob bekor
            self.stop()
            return
        if not self._stream_on:
            self.stop()
            self._stream_on = True
            self._stream_used = 0
        if not (self.active() and self.read_ai):
            return
        parts, used = split_complete(visible[self._stream_used :])
        self._stream_used += used
        for p in parts:
            self._ai_sentence(p)

    def stream_end(self, final: str) -> None:
        if not self._stream_on:
            self.speak_ai(final)
            return
        rest = final[self._stream_used :] if len(final) >= self._stream_used else ""
        self._stream_on = False
        if self.active() and self.read_ai:
            for s in split_sentences(rest.strip()):
                self._ai_sentence(s)

    def _ai_sentence(self, sentence: str) -> None:
        tts = tts_text(sentence)
        if tts and self._live(tts):
            self._push_live(tts)

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    def stop(self) -> None:
        self._gen += 1
        self._items.clear()
        self._n = self._next = 0
        self._stream_on = False
        if self._busy and self._player is not None:
            self._player.stop()
        self._busy = False
        self._set_playing(False)

    def _set_playing(self, on: bool) -> None:
        if on != self._is_playing:
            self._is_playing = on
            self.playing.emit(on)

    def _push(self, item: Path | bytes) -> None:
        self._items[self._n] = item
        self._n += 1
        self._pump()

    def _push_live(self, tts: str) -> None:
        key = self.key()
        if not key:
            return
        idx = self._n
        self._items[idx] = _PENDING
        self._n += 1
        self._inflight += len(tts)
        self._ensure_worker()
        self._jobs.put((self._gen, idx, tts, self.model, self.voice_id, key))

    def _pump(self) -> None:
        if self._busy:
            return
        while self._next in self._items:
            item = self._items[self._next]
            if item is _PENDING:
                return  # navbatdagi gap hali kelmadi — animatsiya davom etadi
            del self._items[self._next]
            self._next += 1
            if item is None:
                continue  # bu gap yasalmadi — keyingisiga
            self._play(item)
            return
        self._set_playing(False)

    def _play(self, item: Path | bytes) -> None:
        player = self._get_player()
        if player is None:
            return
        player.set_volume(self.volume)
        self._busy = True
        self._set_playing(True)
        if isinstance(item, Path):
            player.play_file(item)
        else:
            player.play_bytes(item)

    def _get_player(self) -> Any:
        if self._player is None:
            try:
                if self._player_factory is not None:
                    self._player = self._player_factory()
                else:
                    from yue.voice.player import QtPlayer

                    self._player = QtPlayer(self)
            except Exception:  # noqa: BLE001 — ovozsiz ham Yue ishlayveradi
                log.exception("ovoz pleeri ochilmadi")
                self._player_factory = lambda: None
                return None
            if self._player is not None:
                self._player.finished.connect(self._on_finished)
        return self._player

    def _on_finished(self) -> None:
        self._busy = False
        self._pump()

    # --- fon oqimi -----------------------------------------------------------------------------

    def _client(self, key: str) -> Any:
        client = self._clients.get(key)
        if client is None:
            client = self._clients[key] = self._client_factory(key)
        return client

    def _ensure_worker(self) -> None:
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._work, name="yue-voice", daemon=True)
            self._worker.start()

    def _work(self) -> None:
        while True:
            job = self._jobs.get()
            if job is None:
                return
            gen, idx, tts, model, voice_id, key = job
            data = None
            if gen == self._gen:  # eskirgani (yangi gap boshlangan) yuborilmaydi
                try:
                    data = self._client(key).synth(voice_id, tts, model)
                except VoiceError as exc:
                    log.info("ovoz so'rovi bo'lmadi: %s (%s)", exc.kind, exc.status)
                    self._failed.emit(gen, exc.kind, exc.detail)
                except Exception:  # noqa: BLE001
                    log.exception("ovoz so'rovida kutilmagan xato")
            self._ready.emit(gen, idx, data, len(tts))

    def _on_ready(self, gen: int, idx: int, data: object, chars: int) -> None:
        self._inflight = max(0, self._inflight - chars)
        ok = isinstance(data, bytes) and bool(data)
        if ok:  # kredit sarflandi — gap endi kerak bo'lmasa ham hisobga tushadi
            self._add_usage(chars)
        if gen != self._gen or idx not in self._items:
            return
        self._items[idx] = data if ok else None
        self._pump()

    def _on_failed(self, _gen: int, kind: str, detail: str = "") -> None:
        if kind in ("auth", "perm", "credits") and self._blocked != kind:
            self._blocked = kind
            self.notify.emit(t("voice.notify.title"), error_text(kind, detail))

    # --- tayyorlash (bosqichlar) ----------------------------------------------------------------

    @property
    def preparing(self) -> bool:
        return self._prep_thread is not None and self._prep_thread.is_alive()

    def plan(self, data: Mapping[str, Any], stage: int, name: str) -> tuple[list, int]:
        return stages.plan(data, stage, name, self.model, VOICE_SETTINGS, self.cache())

    def prepare_blocker(self) -> str | None:
        """Tayyorlab bo'lmasa — sabab (i18n kaliti)."""
        if not self.online():
            return "voice.prep.offline"
        if not self.has_key() or not self.key():
            return "voice.prep.no_key"
        if not self.voice_id:
            return "voice.prep.no_voice"
        return None

    def start_prepare(self, data: Mapping[str, Any], stage: int, name: str) -> bool:
        if self.preparing or self.prepare_blocker() is not None:
            return False
        key, voice_id, model = self.key() or "", self.voice_id, self.model
        cache_ = self.cache()
        cache_.forget_names(name)  # ism o'zgargan bo'lsa — faqat {ism} li gaplar qayta yasaladi
        items, _ = self.plan(data, stage, name)
        self._prep_stop = threading.Event()
        stop = self._prep_stop
        client = self._client(key)

        def work() -> None:
            try:
                result = stages.run(
                    items,
                    lambda tts: client.synth(voice_id, tts, model),
                    cache_,
                    stage,
                    name,
                    stop,
                    self.progress.emit,
                )
            except Exception:  # noqa: BLE001
                log.exception("ovoz tayyorlashda kutilmagan xato")
                result = "bad"
            log.info("ovoz tayyorlash: %s-bosqich → %s", stage, result)
            self.prepare_done.emit(result)

        self.progress.emit(0, len(items))
        self._prep_thread = threading.Thread(target=work, name="yue-voice-prep", daemon=True)
        self._prep_thread.start()
        return True

    def stop_prepare(self) -> None:
        self._prep_stop.set()

    # --- hisob -----------------------------------------------------------------------------------

    def check_account(self, key: str | None = None) -> None:
        """Kalitni tekshirish: qolgan kredit va ovozlar ro'yxati (fonda) → `account` signali."""
        key = key or self.key()
        if not key:
            self.account.emit({"error": "no_key"})
            return
        client = self._client_factory(key)

        def work() -> None:
            try:
                used, limit = client.credits()
                voices = client.voices()
            except VoiceError as exc:
                self.account.emit({"error": exc.kind, "perm": exc.detail})
                return
            except Exception:  # noqa: BLE001
                log.exception("ovoz hisobi tekshirilmadi")
                self.account.emit({"error": "bad"})
                return
            self.last_credits = (used, limit)
            self.account.emit({"used": used, "limit": limit, "voices": voices})

        threading.Thread(target=work, name="yue-voice-check", daemon=True).start()

    def shutdown(self) -> None:
        self.stop()
        self._prep_stop.set()
        self._jobs.put(None)
