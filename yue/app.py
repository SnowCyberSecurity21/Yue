"""Ilova boshqaruvchisi: personaj, interfeys va "miya" (`yue.core.Brain`) ni ulaydi.

Personaj: kiyim, fizika, faoliyatlar, to'liq ekranda yashirinish, harakatsizlikda uxlash.
Interfeys: gap pufagi, menyu, tray, sozlamalar, birinchi ochilish, xotira.
AI manbasi (Online/Offline): chatdagi kalit so'z AI'ga yuborilmaydi (`yue.modes`).
Tezkor tugmalarni foydalanuvchi tanlaydi: ko'rsatish/yashirish (standart Ctrl+Alt+Y,
`pet.hotkey`) va ovozni jim qilish (standart Ctrl+Alt+Shift+U, `voice.hotkey`).
Miya: xotira, AI, vazifalar va eslatmalar — signallar orqali (UI oqimi bloklanmaydi).
Ovoz (`yue.voice`): Yue gapi pufak bilan birga ovozda (kesh yoki ElevenLabs).
"""

from __future__ import annotations

import contextlib
import datetime as dt
import logging
import os
import random
import sys
import time
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, QPoint, QTimer
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from yue import APP_ID, __version__, hotkey, modes, paths
from yue.commands import FAST_REPEAT_S, Commands, UniquePicker
from yue.config import Config
from yue.core import Brain, PetState
from yue.ctl import ControlServer, acquire_instance_lock, send_command
from yue.feelings import mood_expression
from yue.i18n import t
from yue.lines import Lines
from yue.logsetup import setup_logging
from yue.modes import recognize as recognize_mode
from yue.pet.behavior import Behavior, clamp_tempo
from yue.pet.pack import PackError, PackMeta, load_pack
from yue.pet.physics import Body
from yue.pet.sprites import SpriteStore
from yue.pet.wardrobe import PERIODS, Overrides, Period, Wardrobe
from yue.pet.window import PetWindow
from yue.platform import Platform, get_platform
from yue.quick import Quick
from yue.quick import parse as parse_quick
from yue.ui.bubble import Bubble
from yue.ui.menu import TaskDialog, fill_menu
from yue.ui.styles import app_icon, apply_app_style, inform, tray_icon
from yue.voice.service import Voice

log = logging.getLogger(__name__)

HOUSEKEEPING_MS = 2000
TOPMOST_EVERY = 5  # har necha housekeeping'da
FULLSCREEN_CONFIRM = 2  # ketma-ket necha tekshiruvda to'liq ekran bo'lsa yashirinadi
WAKE_IDLE = 3.0  # uxlab yotganda foydalanuvchi shundan kam harakatsiz bo'lsa — uyg'onadi
SLOW_MS = 6000  # birinchi token shundan kech kelsa — "slow" iborasi
# Tezkor tugma ID lari (Nora'nikidan farqli: u 0x4E..): ikkalasini ham foydalanuvchi tanlaydi
HOTKEY_ID = 0x5954  # "YT" — ko'rsatish/yashirish
HOTKEY_VOICE_ID = 0x594D  # "YM" — jim qilish tugmasi: ovoz o'chadi/yonadi
CHATTER_CHECK_MS = 30_000
ACTIVITY_LINE_CHANCE = 0.2
AUTO_LINE_GAP = 5 * 60  # avtomatik gaplar orasidagi eng kam vaqt (s)
TYPING_IDLE = 3.0  # foydalanuvchi hozir yozyapti — bezovta qilinmaydi
AWAY_IDLE = 10 * 60  # shundan uzoq jim — kompyuter yonida emas
AUTOSTART_DELAY_S = 15
NO_KEYS_GAP = 10 * 60  # kalitsiz rejim: to'liq no_keys iborasi shundan tez-tez takrorlanmaydi
INSTANCE_RETRY_S = 3.0  # qulf band, kanal hali yo'q: shuncha vaqt buyruq yuborishga urinamiz
OUTFIT_LINE_MS = 2500  # "kiyinib olay" iborasidan keyin harakat iborasi
# Raqs: pack.json da "dance" sloti bo'lmasa — vaqtinchalik ketma-ketlik (~8 s)
DANCE_SLOT = "dance"
DANCE_STEPS = (("excited_jump", 2.0), ("wave", 2.0), ("excited_jump", 2.0), ("music", 2.0))
# O'zidan aytiladigan gaplar: kayfiyat faol bo'lsa — shu ulush kayfiyat iborasi
MOOD_LINE_SHARE = 0.5
MOOD_LINE_KEYS = {
    "xavotirda": "xavotirda",
    "g'ururli": "gururli",
    "charchagan": "charchagan",
}
JOKE_SHARE = {"low": 0.08, "medium": 0.2, "high": 0.35}  # hazil darajasiga qarab
CARE_SHARE = 0.15


class _HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, platform: Platform, callbacks: dict) -> None:
        super().__init__()
        self.platform = platform
        self.callbacks = callbacks  # hotkey_id → funksiya

    def nativeEventFilter(self, event_type, message):  # noqa: N802
        if bytes(event_type) != b"windows_generic_MSG":
            return False, 0
        for hotkey_id, callback in self.callbacks.items():
            if self.platform.is_hotkey_message(int(message), hotkey_id):
                QTimer.singleShot(0, callback)
                return True, 0
        return False, 0


def launch_command(*extra: str) -> list[str]:
    """Yueni ishga tushirish buyrug'i (exe yoki pythonw + yue.pyw)."""
    if getattr(sys, "frozen", False):
        return [sys.executable, *extra]
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    return [str(pythonw if pythonw.exists() else exe), str(paths.RES / "yue.pyw"), *extra]


class Controller(QObject):
    def __init__(
        self,
        app: QApplication,
        cfg: Config,
        meta: PackMeta,
        platform: Platform | None = None,
    ) -> None:
        super().__init__()
        self.app = app
        self.cfg = cfg
        self.meta = meta
        self.platform = platform or get_platform()
        self.lines = Lines.load()
        self.commands = Commands.load()
        self._fast_cmd: tuple[str, float] | None = None  # AI'siz tanilgan buyruq (nom, vaqt)
        self._no_keys_at: float | None = None  # oxirgi to'liq no_keys iborasi (monotonic)
        self._sayr_lines = UniquePicker()  # bitta sayr ichida gap takrorlanmaydi
        self._dance_gen = 0  # raqs ketma-ketligi: yangi buyruq eskisini to'xtatadi
        self.period_override: Period | None = None
        env_period = os.environ.get("YUE_PERIOD")
        if env_period in PERIODS:
            self.period_override = env_period  # type: ignore[assignment]

        self.wardrobe = Wardrobe.from_pack(meta.raw, overrides=self._overrides())
        self.body = Body()
        self.behavior = Behavior(meta, self.wardrobe, self.body, self.period, random.Random())
        self.behavior.walk_speed = float(cfg.get("pet.walk_speed", self.behavior.walk_speed))
        self.behavior.walk_tempo = clamp_tempo(cfg.get("pet.walk_tempo", 1.0))
        self.sprites = SpriteStore(meta)
        self.pet = PetWindow(meta, self.behavior, self.sprites, self.platform, cfg)
        self.pet.context_requested.connect(self.show_menu)
        self.pet.clicked.connect(self.on_click)
        self.pet.pet_event.connect(self.on_pet_event)
        self.pet.moved.connect(self._place_bubble)

        self.bubble = Bubble()
        self.bubble.submitted.connect(self.on_submit)
        self.bubble.closed.connect(self.on_bubble_closed)
        self.bubble.typing.connect(self._on_typing)
        self._pending_expr = "neutral"
        self._got_token = False
        self.slow_timer = QTimer(self)
        self.slow_timer.setSingleShot(True)
        self.slow_timer.timeout.connect(self._on_slow)

        self.hidden_by_user = False
        self.hidden_by_fullscreen = False
        self._fs_count = 0
        self._hk_count = 0
        self.housekeeping = QTimer(self)
        self.housekeeping.timeout.connect(self.tick_housekeeping)
        self._last_auto_line = time.monotonic()
        self._last_chatter = time.monotonic()
        self.chatter_timer = QTimer(self)
        self.chatter_timer.timeout.connect(self._maybe_chatter)

        self.tray = QSystemTrayIcon(app_icon(), self)
        self._tray_marks: bool | None = None
        self.tray.setToolTip(t("app.name"))
        self.tray_menu = QMenu()
        self.tray_menu.aboutToShow.connect(self._refresh_tray_menu)
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(self._on_tray)

        self.brain = Brain(cfg, self.platform, self.pet_state, self.lines)
        self.brain.say.connect(self.say)
        self.brain.notify.connect(self.notify)
        self.brain.stream_text.connect(self._on_stream)
        self.brain.answered.connect(self._on_answered)
        self._typing = False
        self.voice = Voice(cfg, self.brain.secrets, allowed=self._voice_allowed)
        self.voice.playing.connect(self._on_voice_playing)
        self.voice.notify.connect(self.notify)
        self.voice.limit_reached.connect(
            lambda: QTimer.singleShot(300, lambda: self.say(*self.lines.pick("ovoz", "chegara")))
        )
        self.update_tray_icon()

        # Joriy birikmalar (ro'yxatdan o'tgan yoki band)
        self.hotkey_ok = False
        self.hotkey_voice_ok = False
        self.toggle_hotkey = hotkey.DEFAULT_TOGGLE
        self.voice_hotkey = hotkey.DEFAULT_VOICE
        self._hotkey_filter = _HotkeyFilter(
            self.platform, {HOTKEY_ID: self.toggle, HOTKEY_VOICE_ID: self.toggle_voice}
        )
        self.ctl = ControlServer(self)
        self.ctl.command.connect(self.on_command)
        self._dialogs: list = []

    # --- ishga tushirish ---------------------------------------------------------------------

    def start(self) -> None:
        now = time.monotonic()
        self.ctl.start()
        self.behavior.start(now)
        self.sprites.set_k(self.pet.scale * self.app.primaryScreen().devicePixelRatio())
        slot, look, _ = self.behavior.resolve("fall", self.behavior.look)
        variant = self.meta.variant(slot, look.outfit)
        if variant is not None:
            self.sprites.load_now(variant, ("base", *look.overlays))
        self.pet.spawn()
        self.pet.show()
        self.tray.show()
        self.housekeeping.start(HOUSEKEEPING_MS)
        self.chatter_timer.start(CHATTER_CHECK_MS)
        self.app.installNativeEventFilter(self._hotkey_filter)
        self.toggle_hotkey, self.hotkey_ok = self._register_saved(
            HOTKEY_ID, "pet.hotkey", hotkey.DEFAULT_TOGGLE
        )
        self.voice_hotkey, self.hotkey_voice_ok = self._register_saved(
            HOTKEY_VOICE_ID, "voice.hotkey", hotkey.DEFAULT_VOICE
        )
        log.info("Yue %s ishga tushdi (kun qismi: %s)", __version__, self.period())
        self.voice.log_state()
        if not self.cfg.get("welcome_done", False):
            QTimer.singleShot(1200, self.show_welcome)
        else:
            QTimer.singleShot(2500, self.greet)

    def shutdown(self) -> None:
        self.housekeeping.stop()
        self.chatter_timer.stop()
        with contextlib.suppress(OSError, ValueError):
            self.platform.unregister_hotkey(int(self.pet.winId()), HOTKEY_ID)
            self.platform.unregister_hotkey(int(self.pet.winId()), HOTKEY_VOICE_ID)
        self.app.removeNativeEventFilter(self._hotkey_filter)
        self.ctl.stop()
        self.voice.shutdown()
        self.brain.shutdown()
        self.sprites.shutdown()
        self.tray.hide()
        log.info("Yue yopildi")

    def quit(self) -> None:
        self.say(*self.lines.pick("goodbye"))
        QTimer.singleShot(1400, self.app.quit)

    def greet(self) -> None:
        self.say(*self.lines.pick("greet", self.period()))

    # --- miya bilan aloqa ----------------------------------------------------------------------

    def pet_state(self) -> PetState:
        """AI prompti uchun Yuening holati (ishchi oqimidan o'qiladi — faqat oddiy atributlar)."""
        bh = self.behavior
        return PetState(
            period=self.period(),
            outfit=bh.look.outfit,
            overlays=bh.look.accessories,
            activity="sleep" if bh.sleeping else (bh.activity or "idle"),
        )

    def say(self, expression: str, text: str) -> None:
        """Yue o'zi gapiradi (eslatma, ibora): javob kutilayotgan bo'lsa — keyinroq."""
        if not text:
            return
        if self.bubble.input_mode and self.brain.busy:
            QTimer.singleShot(4000, lambda: self.say(expression, text))
            return
        if not self.pet.isVisible():
            return
        self.say_text(expression, text)

    def say_text(
        self,
        expression: str,
        text: str,
        *,
        typewriter: bool = True,
        auto_hide: bool = True,
        voice: bool = True,
    ) -> None:
        """Yue gapi pufakka chiqadigan yagona joy; `voice` — shu gap ovozda ham aytiladi
        (keshdan yoki jonli; AI javobi ovozi `_on_answered` da alohida).

        Pufakda harflab chiqadi (gapirish animatsiyasi), tugagach `expression` ifodasi.
        """
        if not text:
            return
        self._pending_expr = expression
        self._place_bubble()
        self.bubble.show_text(text, typewriter=typewriter, auto_hide=auto_hide)
        if voice:
            self.voice.speak(text)

    def notify(self, title: str, text: str) -> None:
        if QSystemTrayIcon.isSystemTrayAvailable() and self.tray.isVisible():
            self.tray.showMessage(title, text, app_icon(), 10_000)

    def _on_typing(self, on: bool) -> None:
        now = time.monotonic()
        self._typing = on
        if on:
            self.behavior.set_talking(now, True)
        elif self.behavior.talking and not self.voice.is_playing:
            self.behavior.set_talking(now, False, self._pending_expr)

    # --- ovoz --------------------------------------------------------------------------------

    def _voice_allowed(self) -> bool:
        """Ovoz chiqishi mumkinmi: to'liq ekran/taqdimotda, uyquda va sudralganda — yo'q."""
        bh = self.behavior
        if self.hidden_by_fullscreen or bh.sleeping or bh.dragging:
            return False
        try:
            return not self.platform.fullscreen_busy()
        except (OSError, ValueError):
            return True

    def _on_voice_playing(self, on: bool) -> None:
        """Ovoz o'ynayotganda — gapirish animatsiyasi; tugagach odatiy holat."""
        now = time.monotonic()
        bh = self.behavior
        if on:
            if not bh.talking and not bh.dragging:
                bh.set_talking(now, True)
        elif bh.talking and not self._typing:
            bh.set_talking(now, False, self._pending_expr)

    def toggle_voice(self) -> None:
        """Jim qilish tugmasi, menyu: ovozni jim o'chirish/yoqish."""
        self.voice.set_enabled(not self.voice.enabled)
        log.info("ovoz: %s", "yoqildi" if self.voice.enabled else "o'chirildi")

    def _register_saved(self, hotkey_id: int, key: str, default: str) -> tuple[str, bool]:
        """Saqlangan (yoki standart) birikmani ro'yxatdan o'tkazish: (birikma, ok)."""
        combo = hotkey.parse(str(self.cfg.get(key, "") or "")) or hotkey.parse(default)
        assert combo is not None
        ok = self.platform.register_combo(int(self.pet.winId()), hotkey_id, combo)
        if not ok:
            log.info("%s ro'yxatdan o'tmadi (band)", combo.portable())
        return combo.portable(), ok

    def _rebind(
        self, hotkey_id: int, key: str, current: str, current_ok: bool, text: str
    ) -> tuple[str, str, bool]:
        """Yangi birikma: (natija, birikma, ok). Natija: ok / invalid / busy.

        Band bo'lsa — eski birikma qaytadan ro'yxatdan o'tadi, config o'zgarmaydi.
        """
        combo = hotkey.parse(text)
        if combo is None:
            return "invalid", current, current_ok
        if combo.portable() == current and current_ok:
            return "ok", current, True
        handle = int(self.pet.winId())
        old = hotkey.parse(current)
        if current_ok:
            self.platform.unregister_hotkey(handle, hotkey_id)
        if self.platform.register_combo(handle, hotkey_id, combo):
            self.cfg.set(key, combo.portable())
            self.cfg.save()
            log.info("tezkor tugma o'zgardi: %s", combo.portable())
            return "ok", combo.portable(), True
        ok = False
        if current_ok and old is not None:
            ok = self.platform.register_combo(handle, hotkey_id, old)
        log.info("%s ro'yxatdan o'tmadi (band)", combo.portable())
        return "busy", current, ok

    def set_voice_hotkey(self, text: str) -> str:
        """Sozlamalar → Ovoz: yangi jim qilish birikmasi. Natija: ok / invalid / busy."""
        result, self.voice_hotkey, self.hotkey_voice_ok = self._rebind(
            HOTKEY_VOICE_ID, "voice.hotkey", self.voice_hotkey, self.hotkey_voice_ok, text
        )
        return result

    def set_toggle_hotkey(self, text: str) -> str:
        """Sozlamalar → Umumiy: ko'rsatish/yashirish birikmasi. Natija: ok / invalid / busy."""
        result, self.toggle_hotkey, self.hotkey_ok = self._rebind(
            HOTKEY_ID, "pet.hotkey", self.toggle_hotkey, self.hotkey_ok, text
        )
        return result

    def _place_bubble(self) -> None:
        self.bubble.anchor_to(*self.pet.head_anchor())

    # --- suhbat ------------------------------------------------------------------------------

    def open_chat(self) -> None:
        now = time.monotonic()
        if self.hidden_by_user or not self.pet.isVisible():
            self.set_hidden(False)
        if self.behavior.sleeping:
            self.behavior.wake(now)
        self.behavior.set_focus(now, True)
        self._place_bubble()
        was_visible = self.bubble.isVisible()
        self.bubble.open_input()
        if not was_visible:
            self.say_text(*self.lines.pick("listen"), auto_hide=False)
        # Foydalanuvchi o'zi ochdi (Yueni bosdi, tezkor tugma, tray) — fokus aniq maydonga kelsin.
        with contextlib.suppress(OSError, ValueError):
            self.platform.bring_to_front(int(self.bubble.winId()))
        self.bubble.focus_input()

    def on_submit(self, text: str) -> None:
        quick = parse_quick(text, dt.datetime.now())
        if quick is not None:
            self.apply_quick(quick)  # "eslat: …", "vazifalar" — AI'siz
            return
        switch = recognize_mode(text)
        if switch is not None:
            self.apply_mode_switch(switch)  # kalit so'z AI'ga yuborilmaydi
            return
        cmd = self.commands.recognize(text)
        spec = self.commands.get(cmd) if cmd is not None else None
        if spec is not None and spec.no_ai:
            # "hazil ayt" — AI'siz, darhol tayyor ibora (gapirish animatsiyasi bilan)
            self.say_text(*self.command_line(spec.name), auto_hide=not self.bubble.input_mode)
            return
        if not self.brain.has_ai():
            if cmd is not None:  # harakat va uning iborasi — AI'siz ham
                if self.run_command(cmd, source="fast") != "missing":
                    self.say_text(*self.command_line(cmd), auto_hide=not self.bubble.input_mode)
            else:
                self._say_no_keys()
            return
        # Tanilgan buyruq navbatga qo'yilmaydi: javob bo'lmasa harakatning tayyor iborasi bor.
        if not self.brain.ask(text, enqueue=cmd is None):
            self.bubble.restore_input(text)  # matn yo'qolmasin
            return
        now = time.monotonic()
        self.bubble.set_busy(True)
        self._got_token = False
        expr, line = self.lines.pick("thinking")
        self.say_text(expr, line, typewriter=False, auto_hide=False)
        self.slow_timer.start(SLOW_MS)
        bh = self.behavior
        if cmd is not None:
            self._fast_cmd = (cmd, now)
            self.run_command(cmd, source="fast")  # AI javobini kutmasdan
        elif bh.sleeping and bh.command is not None:
            bh.wake(now)  # "uxla" buyrug'i — foydalanuvchi yana yozguncha

    def apply_quick(self, quick: Quick) -> None:
        keep = not self.bubble.input_mode
        if quick.kind == "list":
            self.brain.remind_open_tasks(force=True)
            return
        if quick.kind == "bad":
            self.say_text(*self.lines.pick("eslat_xato"), auto_hide=keep)
            return
        applied = self.brain.book.add(quick.text, quick.due, quick.repeat)
        if applied and applied.task:
            self.brain.tasks_changed.emit()
            self.say_text(*self.lines.pick("task_added", task=applied.task.text), auto_hide=keep)
        else:
            self.say_text(*self.lines.pick("eslat_xato"), auto_hide=keep)

    def _say_no_keys(self) -> None:
        """Kalitsiz (yoki Offline modelsiz): to'liq ibora va "Sozlamalarni ochish" tugmasi 10
        daqiqada ko'pi bilan bir marta; oraliqda — qisqa ibora."""
        now = time.monotonic()
        keep = not self.bubble.input_mode
        if self._no_keys_at is not None and now - self._no_keys_at < NO_KEYS_GAP:
            self.say_text(*self.lines.pick("kalitsiz"), auto_hide=keep)
            return
        self._no_keys_at = now
        if self.offline:
            line, tab = ("thinking", t("notify.local_missing")), "local"
        else:
            line, tab = self.lines.pick("no_keys"), "ai"
        self.say_text(*line, auto_hide=keep)
        self.bubble.show_action(t("bubble.open_settings"), lambda: self.show_settings(tab))

    def _on_slow(self) -> None:
        if self.brain.busy and not self._got_token:
            expr, line = self.lines.pick("slow")
            self.say_text(expr, line, typewriter=False, auto_hide=False)

    def _on_stream(self, visible: str) -> None:
        if not visible:  # zanjir boshqa maqsadga o'tdi — yarim javob tozalanadi
            self._got_token = False
            self.voice.stream_update("")
            return
        self._got_token = True
        self.slow_timer.stop()
        if not self.behavior.talking:
            self.behavior.set_talking(time.monotonic(), True)
        self.bubble.set_stream(visible)
        self.voice.stream_update(visible)

    def _on_answered(self, res) -> None:
        self.slow_timer.stop()
        self.bubble.set_busy(False)
        now = time.monotonic()
        fast, self._fast_cmd = self._fast_cmd, None
        if fast is not None and now - fast[1] > FAST_REPEAT_S:
            fast = None
        if res.kind == "cancelled":
            return
        command = None
        ai_text = False
        if res.kind == "answer" and res.reply is not None:
            expr, text = res.reply.expression, res.reply.text
            command = res.reply.command
            ai_text = True
            if not res.reply.tagged:
                expr = mood_expression(self.brain.last_mood) or expr  # tegsiz — kayfiyat ifodasi
        elif fast is not None:
            # Internet yoki kalit yo'q: javob o'rniga harakatning tayyor iborasi
            expr, text = self.command_line(fast[0])
        else:
            expr, text = res.line or ("neutral", "…")
        self.say_text(
            expr,
            text,
            typewriter=not self._got_token,
            auto_hide=not self.bubble.input_mode,
            voice=not ai_text,
        )
        if ai_text:  # AI javobi: oqimda boshlangan bo'lsa davom etadi, bo'lmasa gap-gap
            if self._got_token:
                self.voice.stream_end(text)
            else:
                self.voice.speak_ai(text)
        if self._got_token and not self.voice.is_playing:
            self.behavior.set_talking(now, False, expr)
        if command is not None and not (fast is not None and fast[0] == command):
            self.run_command(command, source="ai")  # tez tanilgani ikkinchi marta bajarilmaydi
        # Fokus faqat foydalanuvchi pufakda bo'lsa — boshqa oynada yozayotgan bo'lsa o'g'irlanmaydi.
        if self.bubble.input_mode and self.bubble.isActiveWindow():
            self.bubble.edit.setFocus()

    def on_bubble_closed(self) -> None:
        now = time.monotonic()
        self.behavior.set_focus(now, False)
        if self.behavior.talking:
            self.behavior.set_talking(now, False, self._pending_expr)

    # --- kun qismi va kiyim ------------------------------------------------------------------

    def period(self) -> Period:
        if self.period_override:
            return self.period_override
        return self.wardrobe.period_for_hour(dt.datetime.now().hour)

    def _overrides(self) -> Overrides:
        if self.cfg.get("wardrobe.mode") != "manual":
            return Overrides()
        return Overrides.from_config(self.cfg.get("wardrobe"))

    def set_period_override(self, period: Period | None) -> None:
        self.period_override = period
        self.behavior.restart(time.monotonic())

    def reroll_outfit(self) -> None:
        self.wardrobe.reroll_base()
        self.behavior.restart(time.monotonic())

    def debug_outfit(self, outfit: str) -> None:
        """Sinov: asosiy kiyimni darhol almashtirish (saqlanmaydi; kun qismi almashguncha)."""
        self.wardrobe.update_period(self.period())
        self.wardrobe.base_outfit = outfit
        self.behavior.restart(time.monotonic())

    def debug_expression(self, tag: str) -> None:
        self.behavior.show_expression(time.monotonic(), tag)

    def debug_drop(self) -> None:
        """Sinov: Yueni ekran tepasidan tashlash (fall → land)."""
        self.bubble.close_bubble()
        self.pet.drop_from_top()

    def debug_blink(self) -> None:
        self.behavior.blink_now(time.monotonic())

    def set_walk_tempo(self, tempo: float) -> None:
        """Sinov: yurish tempi (fps va tezlik birga) — config.json ga yoziladi."""
        tempo = clamp_tempo(tempo)
        self.behavior.walk_tempo = tempo
        self.cfg.set("pet.walk_tempo", tempo)
        self.cfg.save()
        log.info("yurish tempi: %s", tempo)

    def set_wardrobe_mode(self, mode: str) -> None:
        self.cfg.set("wardrobe.mode", mode)
        self.cfg.save()
        self.wardrobe.overrides = self._overrides()
        self.reroll_outfit()

    # --- davriy tekshiruvlar -----------------------------------------------------------------

    def tick_housekeeping(self) -> None:
        self._hk_count += 1
        now = time.monotonic()

        # Kun qismi almashdi → yangi kiyim va faoliyatlar
        if self.wardrobe.period != self.period() and not self.behavior.sleeping:
            self.behavior.restart(now)

        # To'liq ekranli dastur — yashirinish
        if self.cfg.get("pet.hide_fullscreen", True):
            busy = self.platform.fullscreen_busy()
            self._fs_count = self._fs_count + 1 if busy else min(0, self._fs_count + 1)
            should_hide = self._fs_count >= FULLSCREEN_CONFIRM
            if should_hide != self.hidden_by_fullscreen:
                self.hidden_by_fullscreen = should_hide
                if should_hide:
                    self.voice.stop()
                self._apply_visibility()
                if not should_hide and self.pet.isVisible():
                    QTimer.singleShot(1500, lambda: self.say(*self.lines.pick("fullscreen_back")))

        if not self.pet.isVisible():
            return

        # Harakatsizlik → uxlash; foydalanuvchi qaytsa — uyg'onish
        idle = self.platform.idle_seconds()
        sleep_after = float(self.cfg.get("pet.sleep_after_min", 10)) * 60
        bh = self.behavior
        if bh.sleeping and not bh.forced_sleep and idle < WAKE_IDLE:
            bh.wake(now)
            QTimer.singleShot(2500, lambda: self.say(*self.lines.pick("welcome_back")))
        elif (
            not bh.sleeping
            and sleep_after > 0
            and idle >= sleep_after
            and bh.body.grounded
            and not self.bubble.isVisible()
        ):
            self.voice.stop()
            bh.go_sleep(now)

        if self._hk_count % TOPMOST_EVERY == 0:
            with contextlib.suppress(OSError, ValueError):
                self.platform.keep_topmost(int(self.pet.winId()))
                if self.bubble.isVisible():
                    self.platform.keep_topmost(int(self.bubble.winId()))

    def _apply_visibility(self) -> None:
        visible = not (self.hidden_by_user or self.hidden_by_fullscreen)
        if visible and not self.pet.isVisible():
            self.pet.refresh_surfaces()
            self.pet.show()
        elif not visible and self.pet.isVisible():
            self.voice.stop()
            self.pet.hide()
            self.bubble.close_bubble()

    def set_hidden(self, hidden: bool) -> None:
        self.hidden_by_user = hidden
        if not hidden:
            self.hidden_by_fullscreen = False
            self._fs_count = -15  # foydalanuvchi o'zi chaqirdi — ~30 s to'liq ekranga qaramaymiz
        self._apply_visibility()

    def toggle(self) -> None:
        if self.pet.isVisible():
            self.set_hidden(True)
        else:
            self.set_hidden(False)
            self.pet.summon()

    def on_command(self, cmd: str) -> None:
        if cmd == "toggle":
            self.toggle()
        elif cmd == "show":
            self.set_hidden(False)
            self.pet.summon()
        elif cmd == "hide":
            self.set_hidden(True)
        elif cmd == "chat":
            self.open_chat()

    # --- hodisalar ---------------------------------------------------------------------------

    def on_click(self) -> None:
        now = time.monotonic()
        if self.behavior.sleeping:
            self.behavior.wake(now)
            QTimer.singleShot(900, lambda: self.say(*self.lines.pick("wake")))
            return
        self.open_chat()

    def on_pet_event(self, name: str, data: object) -> None:
        if name == "drag":
            self.voice.stop()  # sudralganda ovoz to'xtaydi
        if name == "sayr":
            self._on_sayr(str(data))
            return
        if name == "drag" and not self.bubble.input_mode and random.random() < 0.5:
            self.say(*self.lines.pick("drag"))
        elif name == "thrown":
            self.say(*self.lines.pick("thrown"))
        elif name == "action" and isinstance(data, str):
            self._maybe_activity_line(data)

    def _on_sayr(self, what: str) -> None:
        """Sayr gaplari: to'xtashda "gap" yoki "kulish", oxirida "tugash" (takrorlanmaydi)."""
        if what == "start":
            self._sayr_lines.reset()
            return
        sub = {"gap": "gap", "kulish": "kulish", "end": "tugash"}.get(what)
        line = self._sayr_lines.pick(self.lines.options("sayr", sub)) if sub else None
        if line is not None:
            self.say(*line)

    # --- o'zi gap boshlash -------------------------------------------------------------------

    def _can_speak_unprompted(self) -> bool:
        """Yue o'zi gapirsa bo'ladimi: ko'rinib turibdi, band emas, foydalanuvchi yonida."""
        bh = self.behavior
        if not self.pet.isVisible() or self.bubble.isVisible() or self.brain.busy:
            return False
        if bh.sleeping or bh.dragging or not bh.body.grounded:
            return False
        idle = self.platform.idle_seconds()
        return TYPING_IDLE <= idle < AWAY_IDLE

    def _maybe_chatter(self) -> None:
        every = float(self.cfg.get("pet.chatter_min", 20) or 0) * 60
        now = time.monotonic()
        if every <= 0 or now - self._last_chatter < every:
            return
        if not self._can_speak_unprompted():
            return  # keyingi tekshiruvda (30 s) yana urinadi
        self._last_chatter = self._last_auto_line = now
        self.say(*self.chatter_line())

    def chatter_line(self, rng: random.Random | None = None) -> tuple[str, str]:
        """O'zidan aytiladigan gap: kayfiyat (faol bo'lsa), hazil (darajasiga qarab), mehr,
        taklif yoki kun qismiga mos bekorchi gap."""
        rng = rng or random
        mood_key = MOOD_LINE_KEYS.get(self.brain.current_mood())
        if mood_key and self.lines.has("kayfiyat", mood_key) and rng.random() < MOOD_LINE_SHARE:
            return self.lines.pick("kayfiyat", mood_key)
        roll = rng.random()
        joke = JOKE_SHARE.get(str(self.cfg.get("pet.humor", "medium")), JOKE_SHARE["medium"])
        if roll < joke and self.lines.has("hazil"):
            return self.lines.pick("hazil")
        if roll < joke + CARE_SHARE and self.lines.has("mehr"):
            return self.lines.pick("mehr")
        if roll < joke + 2 * CARE_SHARE and self.lines.has("taklif"):
            return self.lines.pick("taklif")  # taklif — mehr bilan bir xil chastotada
        return self.lines.pick("idle", self.period())

    def _maybe_activity_line(self, activity: str) -> None:
        if float(self.cfg.get("pet.chatter_min", 20) or 0) <= 0:
            return
        now = time.monotonic()
        if now - self._last_auto_line < AUTO_LINE_GAP or random.random() > ACTIVITY_LINE_CHANCE:
            return
        if not self.lines.options("activity", activity) or not self._can_speak_unprompted():
            return
        self._last_auto_line = now
        QTimer.singleShot(1200, lambda: self.say(*self.lines.pick("activity", activity)))

    def sleep(self) -> None:
        self.voice.stop()
        self.bubble.close_bubble()
        self.behavior.go_sleep(time.monotonic(), forced=True)

    def wake(self) -> None:
        self.behavior.wake(time.monotonic())
        QTimer.singleShot(900, lambda: self.say(*self.lines.pick("wake")))

    def pat(self) -> None:
        """Boshini silash: mehr yo'q — qisqa kesatiq (grumpy yoki smug ifoda)."""
        if self.behavior.sleeping:
            self.wake()
            return
        self.say(*self.lines.pick("pat"))

    def summon(self) -> None:
        self.set_hidden(False)
        self.pet.summon()

    def perform(self, slot: str) -> None:
        self.behavior.perform(time.monotonic(), slot)

    # --- buyruqlar ---------------------------------------------------------------------------

    def command_line(self, name: str) -> tuple[str, str]:
        """Harakatning tayyor iborasi (harakatlar.json → "ibora")."""
        spec = self.commands.get(name)
        if spec is None or not spec.line:
            return self.lines.pick("harakat_yoq")
        return self.lines.pick(*spec.line_key)

    def run_command(self, name: str, source: str = "menu", seconds: float | None = None) -> str:
        """Buyruqni bajarish. `source`: menu — Sinov (ibora aytiladi); fast — AI'siz tanildi,
        javob kutilmoqda; ai — javobdagi <harakat> (gapni AI o'zi aytdi)."""
        spec = self.commands.get(name)
        if spec is None:
            return "missing"
        if name == "raqs":
            return self._dance(source)
        if seconds is not None:
            spec = replace(spec, seconds=seconds)  # Sinov: qisqa sayr
        result = self.behavior.run_command(time.monotonic(), spec)
        log.info("buyruq: %s → %s", name, result)
        if result == "missing":
            self.say(*self.lines.pick("harakat_yoq"))
        elif result == "outfit":
            expr, line = self.lines.pick("harakat_kiyim")
            if source == "fast":  # javob kelguncha pufakda "kiyinib olay"
                self.say_text(expr, line, typewriter=False, auto_hide=False)
            elif source == "menu":
                self.say(expr, line)
                QTimer.singleShot(OUTFIT_LINE_MS, lambda: self.say(*self.command_line(name)))
        elif source == "menu" and result in ("ok", "idle"):
            self.say(*self.command_line(name))
        return result

    def _dance(self, source: str) -> str:
        """Raqs — oddiy o'yin harakati: "dance" sloti, bo'lmasa vaqtinchalik ketma-ketlik."""
        bh = self.behavior
        if bh.dragging or not bh.body.grounded:
            return "busy"
        self._dance_gen += 1
        if self.wardrobe.has(DANCE_SLOT):
            spec = self.commands.get("raqs")
            result = bh.run_command(time.monotonic(), spec) if spec else "missing"
        else:
            self._dance_step(self._dance_gen, 0)
            result = "ok"
        log.info("buyruq: raqs → %s", result)
        if source == "menu":
            self.say(*self.command_line("raqs"))
        return result

    def _dance_step(self, gen: int, i: int) -> None:
        if gen != self._dance_gen or i >= len(DANCE_STEPS):
            return
        slot, secs = DANCE_STEPS[i]
        if self.wardrobe.has(slot):
            self.behavior.play(time.monotonic(), slot, secs)
        QTimer.singleShot(int(secs * 1000), lambda: self._dance_step(gen, i + 1))

    # --- vazifalar ---------------------------------------------------------------------------

    def add_task_dialog(self) -> None:
        dlg = TaskDialog()
        if dlg.exec() and dlg.result_task:
            text, due, repeat = dlg.result_task
            applied = self.brain.book.add(text, due, repeat)
            if applied and applied.task:
                self.say(*self.lines.pick("task_added", task=applied.task.text))

    def complete_task(self, tid: int) -> None:
        task = self.brain.store.task(tid)
        if task and self.brain.store.complete_task(tid):
            self.brain.mood.on_success()
            self.say(*self.lines.pick("task_done", task=task.text))

    # --- AI manbasi (Online/Offline) ---------------------------------------------------------

    @property
    def offline(self) -> bool:
        return self.brain.offline

    def apply_mode_switch(self, switch: str) -> None:
        """Chatdagi kalit so'z (AI'ga yuborilmaydi): AI manbasi almashadi."""
        line = self.set_source(switch, speak=False)
        self.say_text(*line, auto_hide=not self.bubble.input_mode)

    def set_source(self, source: str, speak: bool = True) -> tuple[str, str]:
        """AI manbasi: "online" — bulut API'lar, "offline" — faqat Ollama."""
        source = "offline" if source == "offline" else "online"
        if source != modes.source(self.cfg):
            if self.brain.busy:
                self.brain.cancel()
            self.cfg.set("ai.manba", source)
            self.cfg.save()
            self.brain.reload_ai()
            self.update_tray_icon()
            log.info("AI manbasi: %s", source)
        if source == "offline" and not self.cfg.get("ai.local_model"):
            self.notify(t("app.name"), t("notify.local_missing"))
        line = self.lines.pick("manba", source)
        if speak:
            self.say(*line)
        return line

    def update_tray_icon(self) -> None:
        """Tray belgisi: Offline'da kulrang nuqta, Online'da belgisiz."""
        mark = self.offline
        if mark != self._tray_marks:
            self._tray_marks = mark
            self.tray.setIcon(tray_icon(offline=mark))

    def delete_task(self, tid: int) -> None:
        self.brain.store.delete_task(tid)

    # --- oynalar ------------------------------------------------------------------------------

    def _open(self, dlg) -> None:
        """Modal bo'lmagan oyna (bir nechta bir vaqtda ochilishi mumkin)."""
        self._dialogs.append(dlg)
        dlg.finished.connect(
            lambda _=0, d=dlg: self._dialogs.remove(d) if d in self._dialogs else None
        )
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def show_settings(self, tab: str = "ai") -> None:
        from yue.ui.settings import SettingsDialog

        for d in self._dialogs:
            if isinstance(d, SettingsDialog):
                d.raise_()
                d.activateWindow()
                return
        self._open(SettingsDialog(self, tab if isinstance(tab, str) else "ai"))

    def show_memory(self) -> None:
        from yue.ui.memory_view import MemoryDialog

        self._open(MemoryDialog(self))

    def show_welcome(self) -> None:
        from yue.ui.welcome import WelcomeDialog

        dlg = WelcomeDialog(self)
        dlg.finished.connect(lambda _=0: QTimer.singleShot(600, self.greet))
        self._open(dlg)

    def show_about(self) -> None:
        from yue.ui.about import AboutDialog

        self._open(AboutDialog())

    def apply_settings(self, ai_changed: bool = False, autostart: bool | None = None) -> None:
        cfg = self.cfg
        self.pet.set_size(float(cfg.get("pet.size", 1.0)))
        self.pet.refresh_surfaces()
        self.wardrobe.overrides = self._overrides()
        self.behavior.restart(time.monotonic())
        self.brain.break_tracker.limit_min = float(cfg.get("reminders.break_min", 90) or 0)
        self.brain.usage.budget_usd = float(cfg.get("ai.daily_budget_usd", 0) or 0)
        if ai_changed:
            self.brain.reload_ai()
        self.voice.reload()
        self.update_tray_icon()
        if autostart is not None and autostart != self.platform.autostart_enabled():
            self.platform.set_autostart(autostart, launch_command("--autostart"))
        self.say(*self.lines.pick("settings_saved"))

    def create_shortcut(self) -> bool:
        cmd = launch_command("--toggle")
        return self.platform.create_desktop_shortcut(
            "Yue", cmd[0], cmd[1:], str(paths.ICON), str(paths.RES)
        )

    # --- menyu va tray -----------------------------------------------------------------------

    def show_menu(self, pos: QPoint) -> None:
        menu = QMenu()
        fill_menu(self, menu)
        menu.exec(pos)

    def _refresh_tray_menu(self) -> None:
        self.tray_menu.clear()
        fill_menu(self, self.tray_menu, tray=True)

    def _on_tray(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle()


def run(toggle: bool = False, autostart: bool = False) -> int:
    setup_logging()
    with contextlib.suppress(OSError, AttributeError):
        get_platform().set_app_id(APP_ID)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("Yue")
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(app_icon())
    apply_app_style(app)

    # Bitta nusxa: ishlab turgani bo'lsa — unga buyruq yuborib chiqamiz
    cmd = "toggle" if toggle else "show"
    if send_command(cmd):
        return 0
    instance_lock = acquire_instance_lock()  # kutishdan oldin olinadi; ilova yopilguncha turadi
    if instance_lock is None:
        deadline = time.monotonic() + INSTANCE_RETRY_S
        while not send_command(cmd) and time.monotonic() < deadline:
            time.sleep(0.25)
        log.info("boshqa nusxa ishlayapti — chiqildi")
        return 0
    if autostart:
        time.sleep(AUTOSTART_DELAY_S)  # Windows ish stoli tinchlansin
        if send_command(cmd):  # qulfsiz eski nusxa ochilgan bo'lsa
            return 0
    meta = None
    for root in dict.fromkeys((paths.pack_dir(), paths.DEFAULT_PACK)):
        try:
            meta = load_pack(root)
            break
        except PackError:
            log.exception("pack yuklanmadi: %s", root.name)
    if meta is None:
        inform(None, t("error.title"), t("error.pack"))
        return 1
    log.info("to'plam: %s (versiya %s)", meta.root.name, meta.version)
    cfg = Config.load()
    controller = Controller(app, cfg, meta)
    app.aboutToQuit.connect(controller.shutdown)
    controller.start()
    try:
        return app.exec()
    finally:
        instance_lock.unlock()
