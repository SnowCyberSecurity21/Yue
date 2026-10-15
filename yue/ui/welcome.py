"""Birinchi ochilish: tanishuv va ism → kalitlar (Gemini bepul tarifi haqida ogohlantirish) →
avtoyuklash va yorliq."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from yue import paths
from yue.i18n import t
from yue.ui.settings import CLAUDE_KEYS_URL, GEMINI_KEYS_URL, KeyField
from yue.ui.styles import app_icon, button, label, uz_edit_menu

if TYPE_CHECKING:
    from yue.app import Controller


class WelcomeDialog(QDialog):
    def __init__(self, c: Controller) -> None:
        super().__init__(None)
        self.c = c
        self.setWindowTitle(t("welcome.title"))
        self.setWindowIcon(app_icon())
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setMinimumSize(560, 480)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 16)
        self.pages = QStackedWidget()
        root.addWidget(self.pages, 1)

        # 1 — tanishuv
        p1 = QWidget()
        v = QVBoxLayout(p1)
        top = QHBoxLayout()
        icon = QLabel()
        icon_path = paths.ICON_PNG
        if icon_path.exists():
            icon.setPixmap(
                QPixmap(str(icon_path)).scaled(
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
        self.name = QLineEdit(str(c.cfg.get("user.name", "") or ""))
        self.name.setPlaceholderText(t("welcome.name.placeholder"))
        self.name.setMaxLength(60)
        uz_edit_menu(self.name)
        v.addWidget(self.name)
        v.addStretch(1)
        self.pages.addWidget(p1)

        # 2 — kalitlar
        p2 = QWidget()
        v = QVBoxLayout(p2)
        v.addWidget(label(t("welcome.keys"), heading=True))
        v.addWidget(label(t("welcome.keys.intro"), muted=True))
        secrets = c.brain.secrets
        v.addWidget(label(t("ai.claude_key")))
        self.claude = KeyField(
            "claude", secrets.has("claude_key"), CLAUDE_KEYS_URL, t("ai.get_claude")
        )
        self.claude.get_saved_key = lambda: c.brain.keys()[0]
        v.addWidget(self.claude)
        v.addWidget(label(t("ai.gemini_key")))
        self.gemini = KeyField(
            "gemini", secrets.has("gemini_key"), GEMINI_KEYS_URL, t("ai.get_gemini")
        )
        self.gemini.get_saved_key = lambda: c.brain.keys()[1]
        v.addWidget(self.gemini)
        self.paid = QCheckBox(t("ai.gemini_paid"))
        self.paid.setChecked(bool(c.cfg.get("ai.gemini_paid", False)))
        v.addWidget(self.paid)
        warn = label(t("welcome.gemini_warning"), muted=True)
        v.addWidget(warn)
        v.addWidget(label(t("welcome.later"), muted=True))
        v.addStretch(1)
        self.pages.addWidget(p2)

        # 3 — avtoyuklash
        p3 = QWidget()
        v = QVBoxLayout(p3)
        v.addWidget(label(t("welcome.start"), heading=True))
        self.autostart = QCheckBox(t("welcome.autostart"))
        self.autostart.setChecked(True)
        self.shortcut = QCheckBox(t("welcome.shortcut"))
        self.shortcut.setChecked(True)
        v.addWidget(self.autostart)
        v.addWidget(self.shortcut)
        v.addSpacing(8)
        v.addWidget(label(t("welcome.hotkey", combo=c.toggle_hotkey), muted=True))
        v.addStretch(1)
        self.pages.addWidget(p3)

        row = QHBoxLayout()
        self.back = button(t("btn.back"))
        self.back.clicked.connect(lambda: self._go(-1))
        self.next = button(t("btn.next"), primary=True)
        self.next.clicked.connect(lambda: self._go(1))
        row.addWidget(self.back)
        row.addStretch(1)
        row.addWidget(self.next)
        root.addLayout(row)
        self._go(0)

    def _go(self, step: int) -> None:
        i = self.pages.currentIndex() + step
        if i >= self.pages.count():
            self._finish()
            return
        self.pages.setCurrentIndex(max(0, i))
        last = self.pages.currentIndex() == self.pages.count() - 1
        self.back.setVisible(self.pages.currentIndex() > 0)
        self.next.setText(t("btn.finish") if last else t("btn.next"))

    def _finish(self) -> None:
        c, cfg = self.c, self.c.cfg
        secrets = c.brain.secrets
        if self.claude.value():
            secrets.set("claude_key", self.claude.value())
        if self.gemini.value():
            secrets.set("gemini_key", self.gemini.value())
        cfg.set("ai.gemini_paid", self.paid.isChecked())
        cfg.set("user.name", " ".join(self.name.text().split()))
        cfg.set("welcome_done", True)
        cfg.save()
        if self.shortcut.isChecked():
            c.create_shortcut()
        c.apply_settings(ai_changed=True, autostart=self.autostart.isChecked())
        self.accept()
