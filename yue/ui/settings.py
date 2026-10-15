"""Sozlamalar oynasi: AI (Ishlash rejimi, Kalitlar, Model, Xarajat), Offline (Ollama), Yue,
Ovoz (ElevenLabs), Eslatmalar, Kiyim, Xotira, Umumiy (tezkor tugmalar).

Har bo'lim QScrollArea ichida; "Saqlash"/"Bekor qilish" pastda doim ko'rinadi. Oyna boshlang'ich
balandligi ekranning mavjud balandligining 85% idan oshmaydi.

Kalitlar faqat DPAPI bilan himoyalangan holda saqlanadi; maydonda saqlangan kalit ko'rsatilmaydi.
"Tekshirish" — kalit bilan kichik o'zbekcha so'rov (fonda, UI bloklanmaydi).
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from PySide6.QtCore import QLocale, QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QKeySequenceEdit,
    QLineEdit,
    QProgressBar,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from yue import modes, paths
from yue.ai.providers.base import ChatMessage, ProviderError, SystemBlock
from yue.ai.providers.claude import HAIKU, ClaudeProvider
from yue.ai.providers.gemini import GeminiProvider
from yue.ai.providers.ollama import installed_models
from yue.ai.providers.openrouter import DEFAULT_MODEL as OPENROUTER_DEFAULT
from yue.ai.providers.openrouter import MODELS as OPENROUTER_MODELS
from yue.ai.providers.openrouter import OpenRouterProvider
from yue.i18n import STRINGS, t
from yue.ui.styles import DANGER, app_icon, ask, button, inform, label, uz_edit_menu
from yue.voice.eleven import MODEL_FAST, MODEL_STANDARD, looks_like_key, valid_voice_id
from yue.voice.service import SECRET as VOICE_SECRET

if TYPE_CHECKING:
    from yue.app import Controller

CLAUDE_KEYS_URL = "https://platform.claude.com/settings/keys"
GEMINI_KEYS_URL = "https://aistudio.google.com/apikey"
OPENROUTER_KEYS_URL = "https://openrouter.ai/settings/keys"
ELEVENLABS_KEYS_URL = "https://elevenlabs.io/app/settings/api-keys"
VOICE_NAME = "yue"  # "Tekshirish": voice_id bo'sh bo'lsa, shu nomli ovoz tanlanadi
CHECK_GEMINI_MODEL = "gemini-3.1-flash-lite"
SCREEN_SHARE = 0.85  # oyna boshlang'ich balandligi — ekranning shu qismidan oshmaydi

_CHECK_MESSAGES = {
    "auth": "ai.check.auth",
    "network": "ai.check.network",
    "rate_limit": "ai.check.busy",
    "transient": "ai.check.busy",
    "quota_daily": "ai.check.daily",
}


def check_key(provider: str, key: str, model: str | None = None) -> str:
    """Kalitni sinash (fon oqimida). Natija — foydalanuvchiga ko'rsatiladigan o'zbekcha matn.

    OpenRouter uchun `model` — Sozlamalarda tanlangan model (aynan u bilan sinaladi).
    """
    if provider == "claude":
        p = ClaudeProvider(key, model=HAIKU)
    elif provider == "openrouter":
        p = OpenRouterProvider(key, model=model or OPENROUTER_DEFAULT)
    else:
        p = GeminiProvider(key, model=CHECK_GEMINI_MODEL)
    try:
        text = "".join(
            p.stream([SystemBlock(t("ai.check.prompt"))], [ChatMessage("user", "Salom!")], 256, 20)
        )
    except ProviderError as exc:
        if exc.kind == "auth" and exc.detail == "billing":
            return t("ai.check.billing")
        return t(_CHECK_MESSAGES.get(exc.kind, "ai.check.other"))
    return t("ai.check.ok", model=p.model) if text.strip() else t("ai.check.other")


class _Checker(QObject):
    done = Signal(str)

    def run(self, provider: str, key: str, model: str | None = None) -> None:
        threading.Thread(
            target=lambda: self.done.emit(check_key(provider, key, model)), daemon=True
        ).start()


class KeyField(QWidget):
    """API kalit maydoni: yashirin kiritish, ko'rsatish, o'chirish, tekshirish, havola."""

    def __init__(self, provider: str, saved: bool, url: str, link_text: str) -> None:
        super().__init__()
        self.provider = provider
        self.saved = saved
        self.removed = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        row = QHBoxLayout()
        self.edit = QLineEdit()
        self.edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit.setPlaceholderText(
            t("ai.key.placeholder.saved" if saved else "ai.key.placeholder.empty")
        )
        uz_edit_menu(self.edit)
        self.show_btn = button(t("btn.show_key"))
        self.show_btn.setCheckable(True)
        self.show_btn.toggled.connect(
            lambda on: self.edit.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
        )
        self.check_btn = button(t("btn.check"))
        self.check_btn.clicked.connect(self._check)
        row.addWidget(self.edit, 1)
        row.addWidget(self.show_btn)
        row.addWidget(self.check_btn)
        lay.addLayout(row)
        info = QHBoxLayout()
        link = label(f'<a href="{url}">{link_text}</a>', muted=True, wrap=False)
        link.setTextFormat(Qt.TextFormat.RichText)
        link.setOpenExternalLinks(True)
        info.addWidget(link)
        info.addStretch(1)
        self.remove_btn = button(t("ai.key.remove"), danger=True)
        self.remove_btn.setVisible(saved)
        self.remove_btn.clicked.connect(self._remove)
        info.addWidget(self.remove_btn)
        lay.addLayout(info)
        self.status = label("", muted=True)
        self.status.hide()
        lay.addWidget(self.status)
        self._checker = _Checker()
        self._checker.done.connect(self._checked)
        self.get_saved_key = lambda: None  # sozlamalar oynasi o'rnatadi
        self.get_model = lambda: None  # OpenRouter: tanlangan model bilan tekshiriladi
        self.check_override = None  # ElevenLabs: o'z tekshiruvi (natija — `_checked`)

    def value(self) -> str:
        return "".join(self.edit.text().split())

    def _remove(self) -> None:
        self.removed = True
        self.saved = False
        self.edit.clear()
        self.edit.setPlaceholderText(t("ai.key.placeholder.empty"))
        self.remove_btn.hide()

    def _check(self) -> None:
        key = self.value() or (None if self.removed else self.get_saved_key())
        self.status.show()
        if not key:
            self.status.setText(t("ai.check.no_key"))
            return
        self.status.setText(t("ai.check.running"))
        self.check_btn.setEnabled(False)
        if self.check_override is not None:
            self.check_override(key)
            return
        self._checker.run(self.provider, key, self.get_model())

    def _checked(self, text: str) -> None:
        self.status.setText(text)
        self.check_btn.setEnabled(True)


def _spin(lo: int, hi: int, value: int, suffix: str = "", special: str | None = None) -> QSpinBox:
    s = QSpinBox()
    s.setRange(lo, hi)
    s.setValue(value)
    if suffix:
        s.setSuffix(suffix)
    if special:
        s.setSpecialValueText(special)
    s.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
    return s


def _combo(items: list[tuple[str, object]], current: object) -> QComboBox:
    c = QComboBox()
    for text, value in items:
        c.addItem(text, value)
    idx = next((i for i, (_, v) in enumerate(items) if v == current), 0)
    c.setCurrentIndex(idx)
    return c


class SettingsDialog(QDialog):
    TABS = (
        "ai", "local", "yue", "voice", "reminders", "wardrobe", "privacy", "general",
    )  # fmt: skip

    def __init__(self, c: Controller, tab: str = "ai") -> None:
        super().__init__(None)
        self.c = c
        cfg = c.cfg
        self.setWindowTitle(t("settings.title"))
        self.setWindowIcon(app_icon())
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setMinimumSize(560, 360)
        self.setSizeGripEnabled(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        # --- AI ---
        ai = QWidget()
        ai.setObjectName("page")
        page = QVBoxLayout(ai)
        page.setContentsMargins(16, 16, 16, 16)
        page.setSpacing(12)

        box = QGroupBox(t("ai.group.source"))
        v = QVBoxLayout(box)
        row = QHBoxLayout()
        self.src_online = QRadioButton(t("ai.source.online"))
        self.src_offline = QRadioButton(t("ai.source.offline"))
        src = QButtonGroup(self)
        src.addButton(self.src_online)
        src.addButton(self.src_offline)
        offline = modes.source(cfg) == "offline"
        self.src_online.setChecked(not offline)
        self.src_offline.setChecked(offline)
        row.addWidget(self.src_online)
        row.addWidget(self.src_offline)
        row.addStretch(1)
        v.addLayout(row)
        v.addWidget(label(t("ai.source.hint"), muted=True))
        page.addWidget(box)

        box = QGroupBox(t("ai.group.keys"))
        f = QFormLayout(box)
        f.setVerticalSpacing(10)
        secrets = c.brain.secrets
        self.claude = KeyField(
            "claude", secrets.has("claude_key"), CLAUDE_KEYS_URL, t("ai.get_claude")
        )
        self.claude.get_saved_key = lambda: c.brain.keys()[0]
        self.gemini = KeyField(
            "gemini", secrets.has("gemini_key"), GEMINI_KEYS_URL, t("ai.get_gemini")
        )
        self.gemini.get_saved_key = lambda: c.brain.keys()[1]
        self.openrouter = KeyField(
            "openrouter",
            secrets.has("openrouter_key"),
            OPENROUTER_KEYS_URL,
            t("ai.get_openrouter"),
        )
        self.openrouter.get_saved_key = lambda: c.brain.keys()[2]
        f.addRow(label(t("ai.claude_key")), self.claude)
        f.addRow(label(t("ai.gemini_key")), self.gemini)
        self.gemini_paid = QCheckBox(t("ai.gemini_paid"))
        self.gemini_paid.setChecked(bool(cfg.get("ai.gemini_paid", False)))
        f.addRow("", self.gemini_paid)
        f.addRow("", label(t("ai.gemini_paid.hint"), muted=True))
        f.addRow(label(t("ai.openrouter_key")), self.openrouter)
        page.addWidget(box)

        box = QGroupBox(t("ai.group.model"))
        f = QFormLayout(box)
        f.setVerticalSpacing(10)
        self.primary = _combo(
            [
                (t("ai.primary.claude"), "claude"),
                (t("ai.primary.gemini"), "gemini"),
                (t("ai.primary.openrouter"), "openrouter"),
            ],
            cfg.get("ai.primary", "claude"),
        )
        f.addRow(label(t("ai.primary")), self.primary)
        self.mode = _combo(
            [(t("ai.mode.smart"), "smart"), (t("ai.mode.fast"), "fast")],
            cfg.get("ai.mode", "smart"),
        )
        f.addRow(label(t("ai.mode")), self.mode)
        saved_or = str(cfg.get("ai.openrouter_model", "") or "") or OPENROUTER_DEFAULT
        or_models = [(m, m) for m in OPENROUTER_MODELS]
        if saved_or not in OPENROUTER_MODELS:
            or_models.append((saved_or, saved_or))  # config.json da qo'lda yozilgan model
        self.openrouter_model = _combo(or_models, saved_or)
        self.openrouter.get_model = self.openrouter_model.currentData
        f.addRow(label(t("ai.openrouter_model")), self.openrouter_model)
        f.addRow("", label(t("ai.openrouter.hint"), muted=True))
        page.addWidget(box)

        box = QGroupBox(t("ai.group.cost"))
        f = QFormLayout(box)
        f.setVerticalSpacing(10)
        self.budget = QDoubleSpinBox()
        self.budget.setLocale(QLocale.c())
        self.budget.setRange(0, 100)
        self.budget.setDecimals(2)
        self.budget.setSingleStep(0.1)
        self.budget.setPrefix("$")
        self.budget.setSpecialValueText(t("ai.budget.off"))
        self.budget.setValue(float(cfg.get("ai.daily_budget_usd", 0) or 0))
        self.budget.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        f.addRow(label(t("ai.budget")), self.budget)
        day = c.brain.usage.day
        f.addRow(
            "",
            label(
                t("ai.budget.hint")
                + "\n"
                + t("ai.today", requests=day.requests, cost=f"{day.cost:.3f}"),
                muted=True,
            ),
        )
        page.addWidget(box)
        page.addStretch(1)
        self._add_tab(ai, "ai")

        # --- Offline (Ollama) ---
        loc = QWidget()
        loc.setObjectName("page")
        f = QFormLayout(loc)
        f.setContentsMargins(16, 16, 16, 16)
        f.setVerticalSpacing(12)
        f.addRow(label(t("local.intro"), muted=True))
        row = QHBoxLayout()
        self.local_model = QComboBox()
        self.local_model.setMinimumWidth(240)
        saved_model = str(cfg.get("ai.local_model", "") or "")
        if saved_model:
            self.local_model.addItem(saved_model, saved_model)
        refresh = button(t("local.refresh"))
        refresh.clicked.connect(self._list_models)
        row.addWidget(self.local_model, 1)
        row.addWidget(refresh)
        f.addRow(label(t("local.model")), row)
        self.local_status = label(t("local.checking"), muted=True)
        f.addRow("", self.local_status)
        f.addRow("", label(t("local.install"), muted=True))
        # Fon oqimi Qt obyektlariga tegmaydi: natija lug'atga yoziladi, dialog taymeri o'qiydi
        # (oyna yopilsa taymer ham yo'qoladi — o'chirilgan obyektga signal yuborilmaydi).
        self._models_box: dict[str, object] = {}
        self._models_poll = QTimer(self)
        self._models_poll.timeout.connect(self._poll_models)
        self._list_models()
        self._add_tab(loc, "local")

        # --- Yue ---
        yue = QWidget()
        yue.setObjectName("page")
        f = QFormLayout(yue)
        f.setContentsMargins(16, 16, 16, 16)
        f.setVerticalSpacing(12)
        self.name = QLineEdit(str(cfg.get("user.name", "") or ""))
        self.name.setMaxLength(60)
        uz_edit_menu(self.name)
        f.addRow(label(t("general.name")), self.name)
        self.size = _spin(50, 200, int(round(float(cfg.get("pet.size", 1.0)) * 100)), " %")
        self.size.setSingleStep(10)
        f.addRow(label(t("yue.size")), self.size)
        self.walk_windows = QCheckBox(t("yue.walk_windows"))
        self.walk_windows.setChecked(bool(cfg.get("pet.walk_on_windows", True)))
        f.addRow("", self.walk_windows)
        self.hide_fs = QCheckBox(t("yue.hide_fullscreen"))
        self.hide_fs.setChecked(bool(cfg.get("pet.hide_fullscreen", True)))
        f.addRow("", self.hide_fs)
        self.chatter = _spin(
            0, 240, int(cfg.get("pet.chatter_min", 20)), t("minutes.suffix"), t("yue.chatter.off")
        )
        self.chatter.setSingleStep(5)
        f.addRow(label(t("yue.chatter")), self.chatter)
        self.sleep_after = _spin(
            0,
            240,
            int(cfg.get("pet.sleep_after_min", 10)),
            t("minutes.suffix"),
            t("yue.chatter.off"),
        )
        f.addRow(label(t("yue.sleep_after")), self.sleep_after)
        self.humor = _combo(
            [(t(f"yue.humor.{v}"), v) for v in ("low", "medium", "high")],
            cfg.get("pet.humor", "medium"),
        )
        f.addRow(label(t("yue.humor")), self.humor)
        self._add_tab(yue, "yue")
        self._build_voice_tab()

        # --- Eslatmalar ---
        rem = QWidget()
        rem.setObjectName("page")
        f = QFormLayout(rem)
        f.setContentsMargins(16, 16, 16, 16)
        f.setVerticalSpacing(12)
        self.tasks_every = _spin(
            0,
            1440,
            int(cfg.get("reminders.tasks_every_min", 120)),
            t("minutes.suffix"),
            t("rem.off"),
        )
        self.tasks_every.setSingleStep(15)
        f.addRow(label(t("rem.tasks_every")), self.tasks_every)
        self.break_min = _spin(
            0, 600, int(cfg.get("reminders.break_min", 90)), t("minutes.suffix"), t("rem.off")
        )
        self.break_min.setSingleStep(15)
        f.addRow(label(t("rem.break")), self.break_min)
        self.battery = QCheckBox(t("rem.battery"))
        self.battery.setChecked(bool(cfg.get("reminders.battery", True)))
        f.addRow("", self.battery)
        self._add_tab(rem, "reminders")

        # --- Kiyim ---
        wr = QWidget()
        wr.setObjectName("page")
        f = QFormLayout(wr)
        f.setContentsMargins(16, 16, 16, 16)
        f.setVerticalSpacing(12)
        self.w_auto = QRadioButton(t("wardrobe.auto"))
        self.w_manual = QRadioButton(t("wardrobe.manual"))
        grp = QButtonGroup(self)
        grp.addButton(self.w_auto)
        grp.addButton(self.w_manual)
        manual = cfg.get("wardrobe.mode") == "manual"
        self.w_manual.setChecked(manual)
        self.w_auto.setChecked(not manual)
        f.addRow(label(t("wardrobe.mode")), self.w_auto)
        f.addRow("", self.w_manual)
        auto = (t("choice.auto"), None)
        self.w_outfit = _combo(
            [auto, (t("outfit.tee"), "tee"), (t("outfit.hoodie_black"), "hoodie_black"),
             (t("outfit.hoodie_silver"), "hoodie_silver")],
            cfg.get("wardrobe.outfit"),
        )  # fmt: skip
        self.w_glasses = _combo(
            [auto, (t("choice.on"), True), (t("choice.off"), False)], cfg.get("wardrobe.glasses")
        )
        self.w_phones = _combo(
            [
                auto,
                (t("phones.head"), "head"),
                (t("phones.neck"), "neck"),
                (t("phones.none"), "none"),
            ],
            cfg.get("wardrobe.phones"),
        )
        self.w_hood = _combo(
            [auto, (t("choice.on"), True), (t("choice.off"), False)], cfg.get("wardrobe.hood")
        )
        rows = [("wardrobe.outfit", self.w_outfit)]
        if c.meta.version < 4:
            # v4 da ko'zoynak va quloqchin rasmga chizilgan — majburlab bo'lmaydi.
            rows += [("wardrobe.glasses", self.w_glasses), ("wardrobe.phones", self.w_phones)]
        rows.append(("wardrobe.hood", self.w_hood))  # v4: xudidagi yurishda kapyushon
        for name, w in rows:
            f.addRow(label(t(name)), w)
        self.w_manual.toggled.connect(self._sync_wardrobe)
        self._sync_wardrobe()
        self._add_tab(wr, "wardrobe")

        # --- Maxfiylik ---
        pv = QWidget()
        pv.setObjectName("page")
        v = QVBoxLayout(pv)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(12)
        v.addWidget(label(t("privacy.status")))
        v.addWidget(label(t("privacy.location", path=str(paths.data_dir())), muted=True))
        row = QHBoxLayout()
        mem = button(t("privacy.open_memory"))
        mem.clicked.connect(c.show_memory)
        folder = button(t("privacy.open_folder"))
        folder.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.data_dir())))
        )
        row.addWidget(mem)
        row.addWidget(folder)
        row.addStretch(1)
        v.addLayout(row)
        v.addStretch(1)
        self._add_tab(pv, "privacy")

        # --- Umumiy ---
        gen = QWidget()
        gen.setObjectName("page")
        f = QFormLayout(gen)
        f.setContentsMargins(16, 16, 16, 16)
        f.setVerticalSpacing(12)
        self.autostart = QCheckBox(t("general.autostart"))
        self.autostart.setChecked(c.platform.autostart_enabled())
        f.addRow("", self.autostart)
        self.g_hotkey = QKeySequenceEdit(
            QKeySequence(c.toggle_hotkey, QKeySequence.SequenceFormat.PortableText)
        )
        self.g_hotkey.setMaximumSequenceLength(1)
        self.g_hotkey.editingFinished.connect(self._apply_toggle_hotkey)
        f.addRow(label(t("general.hotkey")), self.g_hotkey)
        self.g_hotkey_status = label("", muted=True)
        self._show_status(
            self.g_hotkey_status, "general.hotkey", "ok" if c.hotkey_ok else "busy", c.toggle_hotkey
        )
        f.addRow("", self.g_hotkey_status)
        self.gen_hk_voice = label("", muted=True)
        self._sync_general_hotkey()
        f.addRow("", self.gen_hk_voice)
        sc = button(t("general.shortcut"))
        self.sc_status = label("", muted=True)
        sc.clicked.connect(
            lambda: self.sc_status.setText(
                t("general.shortcut.done") if c.create_shortcut() else t("general.shortcut.fail")
            )
        )
        f.addRow("", sc)
        f.addRow("", self.sc_status)
        self._add_tab(gen, "general")

        # --- tugmalar ---
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = button(t("btn.cancel"))
        cancel.clicked.connect(self.reject)
        save = button(t("btn.save"), primary=True)
        save.clicked.connect(self._save)
        row.addWidget(cancel)
        row.addWidget(save)
        root.addLayout(row)
        if tab in self.TABS:
            self.tabs.setCurrentIndex(self.TABS.index(tab))
        self._fit_to_screen()

    # --- Ovoz ------------------------------------------------------------------------------------

    def _build_voice_tab(self) -> None:
        c, voice = self.c, self.c.voice
        secrets = c.brain.secrets
        vo = QWidget()
        vo.setObjectName("page")
        page = QVBoxLayout(vo)
        page.setContentsMargins(16, 16, 16, 16)
        page.setSpacing(12)

        box = QGroupBox(t("voice.group.main"))
        f = QFormLayout(box)
        f.setVerticalSpacing(10)
        self.v_enabled = QCheckBox(t("voice.enabled"))
        self.v_enabled.setChecked(voice.enabled)
        f.addRow("", self.v_enabled)
        self.v_volume = _spin(0, 100, int(voice.volume * 100), " %")
        self.v_volume.setSingleStep(10)
        f.addRow(label(t("voice.volume")), self.v_volume)
        self.v_key = KeyField(
            "elevenlabs", secrets.has(VOICE_SECRET), ELEVENLABS_KEYS_URL, t("voice.link")
        )
        self.v_key.get_saved_key = lambda: secrets.get(VOICE_SECRET)
        self.v_key.check_override = voice.check_account
        f.addRow(label(t("voice.key")), self.v_key)
        self.v_voice_id = QLineEdit(voice.voice_id)
        self.v_voice_id.setMaxLength(64)
        self.v_voice_id.setPlaceholderText(t("voice.voice_id.placeholder"))
        uz_edit_menu(self.v_voice_id)
        f.addRow(label(t("voice.voice_id")), self.v_voice_id)
        self.v_voice_id_warn = label("")
        self.v_voice_id_warn.setStyleSheet(f"color: {DANGER};")
        self.v_voice_id_warn.hide()
        f.addRow("", self.v_voice_id_warn)
        self.v_voice_id.textChanged.connect(self._check_voice_id)
        self._check_voice_id(self.v_voice_id.text())
        self.v_model = _combo(
            [(t("voice.model.standard"), MODEL_STANDARD), (t("voice.model.fast"), MODEL_FAST)],
            voice.model,
        )
        f.addRow(label(t("voice.model")), self.v_model)
        self.v_read_ai = QCheckBox(t("voice.read_ai"))
        self.v_read_ai.setChecked(voice.read_ai)
        f.addRow("", self.v_read_ai)
        self.v_daily = _spin(
            0, 100_000, voice.daily_limit, t("voice.daily.suffix"), t("voice.daily.off")
        )
        self.v_daily.setSingleStep(500)
        f.addRow(label(t("voice.daily")), self.v_daily)
        used = t("voice.daily.off_today") if voice.off_today() else ""
        used = used or t("voice.daily.used", used=voice.used_today())
        f.addRow("", label(used, muted=True))
        self.v_hotkey = QKeySequenceEdit(
            QKeySequence(c.voice_hotkey, QKeySequence.SequenceFormat.PortableText)
        )
        self.v_hotkey.setMaximumSequenceLength(1)
        self.v_hotkey.editingFinished.connect(self._apply_hotkey)
        f.addRow(label(t("voice.hotkey")), self.v_hotkey)
        self.v_hotkey_status = label("", muted=True)
        self._show_hotkey_status("ok" if c.hotkey_voice_ok else "busy", c.voice_hotkey)
        f.addRow("", self.v_hotkey_status)
        f.addRow("", label(t("voice.note"), muted=True))
        page.addWidget(box)

        box = QGroupBox(t("voice.group.stages"))
        v = QVBoxLayout(box)
        v.addWidget(label(t("voice.stages.intro"), muted=True))
        row = QHBoxLayout()
        self.v_stage_btns = []
        for n in (1, 2, 3):
            b = button(t("voice.stage.btn", n=n))
            b.clicked.connect(lambda _=False, n=n: self._prepare_stage(n))
            row.addWidget(b)
            self.v_stage_btns.append(b)
        self.v_stop = button(t("voice.stage.stop"), danger=True)
        self.v_stop.clicked.connect(voice.stop_prepare)
        row.addWidget(self.v_stop)
        row.addStretch(1)
        v.addLayout(row)
        self.v_bar = QProgressBar()
        self.v_bar.setTextVisible(False)
        v.addWidget(self.v_bar)
        self.v_status = label("", muted=True)
        v.addWidget(self.v_status)
        page.addWidget(box)
        page.addStretch(1)
        self._stage = 0
        self._stage_done = (0, 0)
        voice.progress.connect(self._on_prep_progress)
        voice.prepare_done.connect(self._on_prep_done)
        voice.account.connect(self._on_account)
        self._sync_prep(voice.preparing)
        self._add_tab(vo, "voice")

    def _sync_prep(self, running: bool) -> None:
        for b in self.v_stage_btns:
            b.setEnabled(not running)
        self.v_stop.setVisible(running)
        self.v_bar.setVisible(running)

    def _check_voice_id(self, text: str) -> bool:
        """Ovoz ID formatga mos kelmasa (masalan, kalit yozilgan) — ogohlantirish; saqlanmaydi."""
        text = text.strip()
        ok = not text or valid_voice_id(text)
        if not ok:
            key = "voice.voice_id.key" if looks_like_key(text) else "voice.voice_id.bad"
            self.v_voice_id_warn.setText(t(key))
        self.v_voice_id_warn.setVisible(not ok)
        return ok

    @staticmethod
    def _show_status(widget: QWidget, prefix: str, result: str, combo: str) -> None:
        """Tezkor tugma holati: ok — birikma, busy / invalid — qizil izoh."""
        if result == "ok":
            widget.setText(t(f"{prefix}.ok", combo=combo))
        else:
            widget.setText(t(f"{prefix}.{result}"))
        widget.setStyleSheet("" if result == "ok" else f"color: {DANGER};")

    def _show_hotkey_status(self, result: str, combo: str) -> None:
        self._show_status(self.v_hotkey_status, "voice.hotkey", result, combo)

    def _apply_toggle_hotkey(self) -> None:
        """Ko'rsatish/yashirish tugmasi tanlandi: darhol ro'yxatdan o'tkaziladi."""
        c = self.c
        text = self.g_hotkey.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        if text:
            result = c.set_toggle_hotkey(text)
        else:  # tozalandi — joriy birikma qaytadi
            self.g_hotkey.setKeySequence(
                QKeySequence(c.toggle_hotkey, QKeySequence.SequenceFormat.PortableText)
            )
            result = "ok" if c.hotkey_ok else "busy"
        self._show_status(self.g_hotkey_status, "general.hotkey", result, c.toggle_hotkey)

    def _sync_general_hotkey(self) -> None:
        c = self.c
        key = "general.hotkey.voice" if c.hotkey_voice_ok else "general.hotkey.voice.busy"
        self.gen_hk_voice.setText(t(key, combo=c.voice_hotkey))

    def _apply_hotkey(self) -> None:
        """Jim qilish tugmasi tanlandi: darhol ro'yxatdan o'tkaziladi (band bo'lsa — izoh)."""
        c = self.c
        text = self.v_hotkey.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        if not text:  # tozalandi — joriy birikma qaytadi
            self.v_hotkey.setKeySequence(
                QKeySequence(c.voice_hotkey, QKeySequence.SequenceFormat.PortableText)
            )
            self._show_hotkey_status("ok" if c.hotkey_voice_ok else "busy", c.voice_hotkey)
            return
        result = c.set_voice_hotkey(text)
        self._show_hotkey_status(result, c.voice_hotkey)
        if hasattr(self, "gen_hk_voice"):
            self._sync_general_hotkey()

    def _save_voice_fields(self) -> None:
        """Kalit, voice_id va model — tayyorlash va "Saqlash" uchun."""
        cfg, secrets = self.c.cfg, self.c.brain.secrets
        if self.v_key.value():
            secrets.set(VOICE_SECRET, self.v_key.value())
        elif self.v_key.removed:
            secrets.set(VOICE_SECRET, None)
        if self._check_voice_id(self.v_voice_id.text()):  # kalit va boshqa narsa saqlanmaydi
            cfg.set("voice.voice_id", self.v_voice_id.text().strip())
        cfg.set("voice.model", self.v_model.currentData())
        self.c.voice.reload()

    def _prepare_stage(self, n: int) -> None:
        voice = self.c.voice
        self._save_voice_fields()
        blocker = voice.prepare_blocker()
        if blocker is not None:
            inform(self, t("voice.stage.confirm.title", n=n), t(blocker))
            return
        name = str(self.c.cfg.get("user.name", "") or "")
        items, chars = voice.plan(self.c.lines.data, n, name)
        if not items:
            self.v_status.setText(t("voice.stage.nothing", n=n))
            return
        if voice.last_credits is not None:
            used, total = voice.last_credits
            left = str(max(0, total - used))
        else:
            left = t("voice.stage.unknown")
        text = t("voice.stage.confirm", count=len(items), chars=chars, left=left)
        if not ask(self, t("voice.stage.confirm.title", n=n), text):
            return
        self._stage = n
        if voice.start_prepare(self.c.lines.data, n, name):
            self._sync_prep(True)

    def _on_prep_progress(self, done: int, total: int) -> None:
        self._stage_done = (done, total)
        self.v_bar.setRange(0, max(1, total))
        self.v_bar.setValue(done)
        self.v_status.setText(t("voice.stage.progress", n=self._stage, done=done, total=total))

    def _on_prep_done(self, result: str) -> None:
        self._sync_prep(False)
        done, total = self._stage_done
        if result == "done":
            self.v_status.setText(t("voice.stage.done", n=self._stage))
        elif result == "stopped":
            self.v_status.setText(t("voice.stage.stopped", done=done, total=total))
        else:
            key = f"voice.check.{result}"
            reason = t(key) if key in STRINGS else t("voice.check.bad")
            self.v_status.setText(t("voice.stage.error", reason=reason))

    def _on_account(self, res: dict) -> None:
        err = res.get("error")
        if err:
            text = t(f"voice.check.{err}")
            if err == "perm" and res.get("perm"):
                text += " " + t("voice.perm.name", perm=res["perm"])
            self.v_key._checked(text)
            return
        used, total = int(res.get("used", 0)), int(res.get("limit", 0))
        text = t("voice.check.ok", left=max(0, total - used), total=total)
        if not valid_voice_id(self.v_voice_id.text().strip()):  # bo'sh yoki noto'g'ri
            found = [(i, n) for i, n in res.get("voices", []) if n.strip().casefold() == VOICE_NAME]
            if found:
                self.v_voice_id.setText(found[0][0])
                text += "\n" + t("voice.check.found", name=found[0][1])
            else:
                text += "\n" + t("voice.check.no_voice")
        self.v_key._checked(text)

    def _add_tab(self, w: QWidget, key: str) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(w)
        self.tabs.addTab(scroll, t(f"settings.tab.{key}"))

    def _fit_to_screen(self) -> None:
        """Boshlang'ich o'lcham: mazmunga yarasha, lekin ekranning 85% idan baland emas."""
        hint = self.sizeHint()
        page = max(
            (self.tabs.widget(i).widget().sizeHint().height() for i in range(self.tabs.count())),
            default=0,
        )
        want = max(hint.height(), page + 140)
        screen = self.screen()
        if screen is not None:
            want = min(want, int(screen.availableGeometry().height() * SCREEN_SHARE))
        self.resize(max(self.minimumWidth(), 680), max(self.minimumHeight(), want))

    def _list_models(self) -> None:
        self.local_status.setText(t("local.checking"))
        box: dict[str, object] = {}
        self._models_box = box
        threading.Thread(
            target=lambda: box.__setitem__("names", installed_models()), daemon=True
        ).start()
        self._models_poll.start(150)

    def _poll_models(self) -> None:
        if "names" in self._models_box:
            self._models_poll.stop()
            self._models_listed(self._models_box["names"])  # type: ignore[arg-type]

    def _models_listed(self, names: list[str] | None) -> None:
        current = self.local_model.currentData()
        if names is None:
            self.local_status.setText(t("local.missing"))
            return
        self.local_model.clear()
        for name in names:
            self.local_model.addItem(name, name)
        if current and current not in names:
            # saqlangan model o'chirilgan bo'lsa ham ro'yxatda ko'rinsin
            self.local_model.addItem(current, current)
        idx = self.local_model.findData(current)
        self.local_model.setCurrentIndex(max(0, idx))
        self.local_status.setText(
            t("local.found", count=len(names)) if names else t("local.no_models")
        )

    def _sync_wardrobe(self) -> None:
        on = self.w_manual.isChecked()
        for w in (self.w_outfit, self.w_glasses, self.w_phones, self.w_hood):
            w.setEnabled(on)

    def _save(self) -> None:
        c, cfg = self.c, self.c.cfg
        secrets = c.brain.secrets
        keys_changed = False
        fields = (
            (self.claude, "claude_key"),
            (self.gemini, "gemini_key"),
            (self.openrouter, "openrouter_key"),
        )
        for field, name in fields:
            if field.value():
                secrets.set(name, field.value())
                keys_changed = True
            elif field.removed:
                secrets.set(name, None)
                keys_changed = True
        ai_keys = (
            "ai.gemini_paid", "ai.primary", "ai.mode", "ai.local_model", "ai.manba",
            "ai.openrouter_model",
        )  # fmt: skip
        ai_before = tuple(cfg.get(k) for k in ai_keys)
        cfg.set("ai.manba", "offline" if self.src_offline.isChecked() else "online")
        cfg.set("ai.local_model", self.local_model.currentData() or "")
        cfg.set("ai.gemini_paid", self.gemini_paid.isChecked())
        cfg.set("ai.primary", self.primary.currentData())
        cfg.set("ai.openrouter_model", self.openrouter_model.currentData() or OPENROUTER_DEFAULT)
        cfg.set("ai.mode", self.mode.currentData())
        cfg.set("ai.daily_budget_usd", round(self.budget.value(), 2))
        cfg.set("pet.size", self.size.value() / 100)
        cfg.set("pet.walk_on_windows", self.walk_windows.isChecked())
        cfg.set("pet.hide_fullscreen", self.hide_fs.isChecked())
        cfg.set("pet.chatter_min", self.chatter.value())
        cfg.set("pet.sleep_after_min", self.sleep_after.value())
        cfg.set("pet.humor", self.humor.currentData())
        cfg.set("reminders.tasks_every_min", self.tasks_every.value())
        cfg.set("reminders.break_min", self.break_min.value())
        cfg.set("reminders.battery", self.battery.isChecked())
        cfg.set("wardrobe.mode", "manual" if self.w_manual.isChecked() else "auto")
        cfg.set("wardrobe.outfit", self.w_outfit.currentData())
        cfg.set("wardrobe.glasses", self.w_glasses.currentData())
        cfg.set("wardrobe.phones", self.w_phones.currentData())
        cfg.set("wardrobe.hood", self.w_hood.currentData())
        cfg.set("user.name", " ".join(self.name.text().split()))
        self._save_voice_fields()
        self._apply_hotkey()
        self._apply_toggle_hotkey()
        cfg.set("voice.enabled", self.v_enabled.isChecked())
        cfg.set("voice.volume", self.v_volume.value())
        cfg.set("voice.read_ai", self.v_read_ai.isChecked())
        cfg.set("voice.daily_chars", self.v_daily.value())
        cfg.save()
        ai_after = tuple(cfg.get(k) for k in ai_keys)
        c.apply_settings(
            ai_changed=keys_changed or ai_before != ai_after,
            autostart=self.autostart.isChecked(),
        )
        self.accept()
