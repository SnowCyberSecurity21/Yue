"""Birinchi ochilish ustasi: tanishuv va ism → AI (beshta yo'l) → ovoz (ixtiyoriy) → oxirgi qadam.

AI qadami: bepul Gemini (tavsiya, qadamma-qadam), Claude, OpenRouter, oflayn Ollama yoki kalitsiz.
Kiritilgan kalitga qarab sozlamalar o'zi qo'yiladi: Claude bor — `ai.primary = claude`, rejim
"Tez (Haiku)"; faqat Gemini — `gemini`; faqat OpenRouter — `openrouter`; Ollama — `ai.manba =
offline`. Usta bir marta ochiladi (`welcome_done`), hammasini keyin Sozlamalarda ham qilish mumkin.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from yue import paths
from yue.i18n import STRINGS, t
from yue.ui.settings import (
    CLAUDE_KEYS_URL,
    ELEVENLABS_KEYS_URL,
    GEMINI_KEYS_URL,
    OLLAMA_URL,
    OPENROUTER_KEYS_URL,
    KeyField,
    fill_voices,
)
from yue.ui.styles import DANGER, app_icon, button, label, uz_edit_menu
from yue.voice.eleven import valid_voice_id
from yue.voice.service import SECRET as VOICE_SECRET

if TYPE_CHECKING:
    from yue.app import Controller

AI_CHOICES = ("gemini", "claude", "openrouter", "ollama", "none")


def link_button(text: str, url: str):
    b = button(text)
    b.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
    return b


class WelcomeDialog(QDialog):
    def __init__(self, c: Controller) -> None:
        super().__init__(None)
        self.c = c
        self.setWindowTitle(t("welcome.title"))
        self.setWindowIcon(app_icon())
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setMinimumSize(600, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 16)
        self.pages = QStackedWidget()
        root.addWidget(self.pages, 1)
        self.pages.addWidget(self._page_hello())
        self.pages.addWidget(self._page_ai())
        self.pages.addWidget(self._page_voice())
        self.pages.addWidget(self._page_finish())

        row = QHBoxLayout()
        self.back = button(t("btn.back"))
        self.back.clicked.connect(lambda: self._go(-1))
        self.skip = button(t("welcome.voice.skip"))
        self.skip.clicked.connect(lambda: self._go(1))
        self.next = button(t("btn.next"), primary=True)
        self.next.clicked.connect(lambda: self._go(1))
        row.addWidget(self.back)
        row.addStretch(1)
        row.addWidget(self.skip)
        row.addWidget(self.next)
        root.addLayout(row)
        c.voice.account.connect(self._on_account)
        c.voice.preview_done.connect(self._on_preview)
        self._go(0)

    # --- sahifalar ----------------------------------------------------------------------------

    def _page_hello(self) -> QWidget:
        p = QWidget()
        v = QVBoxLayout(p)
        top = QHBoxLayout()
        icon = QLabel()
        if paths.ICON_PNG.exists():
            icon.setPixmap(
                QPixmap(str(paths.ICON_PNG)).scaled(
                    96,
                    96,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        top.addWidget(icon)
        top.addWidget(label(t("welcome.hello"), heading=True), 1)
        v.addLayout(top)
        v.addWidget(label(t("welcome.intro")))
        v.addSpacing(10)
        v.addWidget(label(t("welcome.name")))
        self.name = QLineEdit(str(self.c.cfg.get("user.name", "") or ""))
        self.name.setPlaceholderText(t("welcome.name.placeholder"))
        self.name.setMaxLength(60)
        uz_edit_menu(self.name)
        v.addWidget(self.name)
        v.addStretch(1)
        return p

    def _page_ai(self) -> QWidget:
        c = self.c
        secrets = c.brain.secrets
        p = QWidget()
        v = QVBoxLayout(p)
        v.addWidget(label(t("welcome.ai"), heading=True))
        v.addWidget(label(t("welcome.ai.intro"), muted=True))
        self.ai_group = QButtonGroup(self)
        self.ai_radio: dict[str, QRadioButton] = {}
        for i, key in enumerate(AI_CHOICES):
            r = QRadioButton(t(f"welcome.ai.{key}"))
            self.ai_group.addButton(r, i)
            self.ai_radio[key] = r
            v.addWidget(r)
        self.ai_stack = QStackedWidget()
        v.addWidget(self.ai_stack, 1)

        # 1 — bepul Gemini: qadamma-qadam
        g = QWidget()
        gv = QVBoxLayout(g)
        gv.setContentsMargins(0, 6, 0, 0)
        gv.addWidget(label(t("welcome.gemini.steps")))
        gv.addWidget(link_button(t("welcome.gemini.open"), GEMINI_KEYS_URL))
        self.gemini = KeyField(
            "gemini", secrets.has("gemini_key"), GEMINI_KEYS_URL, t("ai.get_gemini")
        )
        self.gemini.get_saved_key = lambda: c.brain.keys()[1]
        gv.addWidget(self.gemini)
        gv.addWidget(label(t("welcome.gemini_warning"), muted=True))
        gv.addStretch(1)
        # 2 — Claude
        cl = QWidget()
        cv = QVBoxLayout(cl)
        cv.setContentsMargins(0, 6, 0, 0)
        self.claude = KeyField(
            "claude", secrets.has("claude_key"), CLAUDE_KEYS_URL, t("ai.get_claude")
        )
        self.claude.get_saved_key = lambda: c.brain.keys()[0]
        cv.addWidget(self.claude)
        cv.addWidget(label(t("welcome.claude.note"), muted=True))
        cv.addStretch(1)
        # 3 — OpenRouter
        orw = QWidget()
        ov = QVBoxLayout(orw)
        ov.setContentsMargins(0, 6, 0, 0)
        self.openrouter = KeyField(
            "openrouter", secrets.has("openrouter_key"), OPENROUTER_KEYS_URL, t("ai.get_openrouter")
        )
        self.openrouter.get_saved_key = lambda: c.brain.keys()[2]
        ov.addWidget(self.openrouter)
        ov.addWidget(label(t("welcome.openrouter.note"), muted=True))
        ov.addStretch(1)
        # 4 — Ollama
        ol = QWidget()
        lv = QVBoxLayout(ol)
        lv.setContentsMargins(0, 6, 0, 0)
        lv.addWidget(label(t("welcome.ollama.note")))
        lv.addWidget(link_button(t("welcome.ollama.open"), OLLAMA_URL))
        lv.addStretch(1)
        # 5 — kalitsiz
        no = QWidget()
        nv = QVBoxLayout(no)
        nv.setContentsMargins(0, 6, 0, 0)
        nv.addWidget(label(t("welcome.none.note")))
        nv.addStretch(1)
        for w in (g, cl, orw, ol, no):
            self.ai_stack.addWidget(w)
        self.ai_group.idToggled.connect(
            lambda i, on: on and self.ai_stack.setCurrentIndex(i)  # type: ignore[func-returns-value]
        )
        self.ai_radio["gemini"].setChecked(True)
        v.addWidget(label(t("welcome.later"), muted=True))
        return p

    def _page_voice(self) -> QWidget:
        c = self.c
        p = QWidget()
        v = QVBoxLayout(p)
        v.addWidget(label(t("welcome.voice"), heading=True))
        v.addWidget(label(t("welcome.voice.intro"), muted=True))
        v.addWidget(label(t("voice.key")))
        self.v_key = KeyField("elevenlabs", c.voice.has_key(), ELEVENLABS_KEYS_URL, t("voice.link"))
        self.v_key.get_saved_key = c.voice.key
        self.v_key.check_override = c.voice.check_account
        v.addWidget(self.v_key)
        v.addWidget(label(t("voice.perms"), muted=True))
        v.addWidget(label(t("voice.voices")))
        self.v_voices = QComboBox()
        self.v_voices.addItem(t("voice.voices.empty"), "")
        self.v_voices.currentIndexChanged.connect(self._voice_chosen)
        v.addWidget(self.v_voices)
        v.addWidget(label(t("voice.voice_id")))
        self.v_voice_id = QLineEdit(c.voice.voice_id)
        self.v_voice_id.setMaxLength(64)
        self.v_voice_id.setPlaceholderText(t("voice.voice_id.placeholder"))
        uz_edit_menu(self.v_voice_id)
        v.addWidget(self.v_voice_id)
        row = QHBoxLayout()
        self.v_preview = button(t("voice.preview"))
        self.v_preview.clicked.connect(self._preview)
        row.addWidget(self.v_preview)
        row.addStretch(1)
        v.addLayout(row)
        self.v_status = label("", muted=True)
        v.addWidget(self.v_status)
        v.addWidget(label(t("voice.credits.note"), muted=True))
        v.addStretch(1)
        return p

    def _page_finish(self) -> QWidget:
        p = QWidget()
        v = QVBoxLayout(p)
        v.addWidget(label(t("welcome.start"), heading=True))
        self.autostart = QCheckBox(t("welcome.autostart"))
        self.autostart.setChecked(True)
        self.shortcut = QCheckBox(t("welcome.shortcut"))
        self.shortcut.setChecked(True)
        v.addWidget(self.autostart)
        v.addWidget(self.shortcut)
        v.addSpacing(8)
        self.hotkey_note = label("", muted=True)
        v.addWidget(self.hotkey_note)
        v.addStretch(1)
        return p

    # --- ovoz ---------------------------------------------------------------------------------

    def _on_account(self, res: dict) -> None:
        err = res.get("error")
        if err:
            text = t(f"voice.check.{err}")
            if err == "perm" and res.get("perm"):
                text += " " + t("voice.perm.name", perm=res["perm"])
            self.v_key._checked(text)
            return
        used, total = int(res.get("used", 0)), int(res.get("limit", 0))
        self.v_key._checked(t("voice.check.ok", left=max(0, total - used), total=total))
        fill_voices(self.v_voices, res.get("voices", []), self.v_voice_id.text().strip())

    def _voice_chosen(self, _i: int) -> None:
        vid = self.v_voices.currentData()
        if vid:
            self.v_voice_id.setText(vid)

    def _preview(self) -> None:
        key = self.v_key.value() or self.c.voice.key()
        vid = self.v_voice_id.text().strip()
        self.v_status.setStyleSheet("")
        if not key or not valid_voice_id(vid):
            self.v_status.setText(t("voice.preview.need"))
            return
        self.v_status.setText(t("ai.check.running"))
        self.v_preview.setEnabled(False)
        self.c.voice.preview(key, vid, t("voice.preview.text"))

    def _on_preview(self, result: str) -> None:
        self.v_preview.setEnabled(True)
        if result == "ok":
            self.v_status.setText(t("voice.preview.ok", n=len(t("voice.preview.text"))))
        else:
            key = f"voice.check.{result}"
            self.v_status.setText(t(key) if key in STRINGS else t("voice.check.bad"))
            self.v_status.setStyleSheet(f"color: {DANGER};")

    # --- navigatsiya va saqlash ---------------------------------------------------------------

    def _go(self, step: int) -> None:
        i = self.pages.currentIndex() + step
        if i >= self.pages.count():
            self._finish()
            return
        i = max(0, i)
        self.pages.setCurrentIndex(i)
        last = i == self.pages.count() - 1
        self.back.setVisible(i > 0)
        self.skip.setVisible(i == 2)  # ovoz — ixtiyoriy
        self.next.setText(t("btn.finish") if last else t("btn.next"))
        if last:
            self.hotkey_note.setText(t("welcome.hotkey", combo=self.c.toggle_hotkey))

    def choice(self) -> str:
        return AI_CHOICES[max(0, self.ai_group.checkedId())]

    def _finish(self) -> None:
        c, cfg = self.c, self.c.cfg
        secrets = c.brain.secrets
        choice = self.choice()
        fields = {"gemini": self.gemini, "claude": self.claude, "openrouter": self.openrouter}
        if choice in fields and fields[choice].value():
            secrets.set(f"{choice}_key", fields[choice].value())
        claude, gemini, openrouter = c.brain.keys()
        if claude:
            cfg.set("ai.primary", "claude")
            cfg.set("ai.mode", "fast")
        elif gemini:
            cfg.set("ai.primary", "gemini")
        elif openrouter:
            cfg.set("ai.primary", "openrouter")
        cfg.set("ai.manba", "offline" if choice == "ollama" else "online")
        if self.v_key.value():
            secrets.set(VOICE_SECRET, self.v_key.value())
        vid = self.v_voice_id.text().strip()
        if valid_voice_id(vid):
            cfg.set("voice.voice_id", vid)
        cfg.set("user.name", " ".join(self.name.text().split()))
        cfg.set("welcome_done", True)
        cfg.save()
        if self.shortcut.isChecked():
            c.create_shortcut()
        c.apply_settings(ai_changed=True, autostart=self.autostart.isChecked())
        self.accept()
