"""O'ng tugma va tray menyusi (bitta quruvchi) hamda vazifa qo'shish oynasi."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QMenu, QVBoxLayout, QWidget

from yue.i18n import STRINGS, t
from yue.logsetup import debug_enabled
from yue.pet.wardrobe import PERIODS
from yue.tasks.timeparse import parse_user_time
from yue.ui.styles import app_icon, button, label, uz_edit_menu

if TYPE_CHECKING:
    from yue.app import Controller

MAX_TASKS_IN_MENU = 15
WALK_TEMPOS = (0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3)  # sinov uchun (pet.walk_tempo)


def fill_menu(c: Controller, m: QMenu, tray: bool = False) -> None:
    bh = c.behavior
    m.addAction(t("menu.chat"), c.open_chat)
    if bh.sleeping:
        m.addAction(t("menu.wake"), c.wake)
    else:
        m.addAction(t("menu.sleep"), c.sleep)
    m.addAction(t("menu.pat"), c.pat)
    m.addAction(t("menu.summon"), c.summon)
    m.addSeparator()

    tasks_menu = m.addMenu(t("menu.tasks"))
    _fill_tasks(c, tasks_menu)

    outfit = m.addMenu(t("menu.outfit"))
    group = QActionGroup(outfit)
    auto = QAction(t("menu.outfit.auto"), outfit, checkable=True)
    auto.setChecked(c.cfg.get("wardrobe.mode", "auto") != "manual")
    auto.triggered.connect(lambda: c.set_wardrobe_mode("auto"))
    manual = QAction(t("menu.outfit.manual"), outfit, checkable=True)
    manual.setChecked(not auto.isChecked())
    manual.triggered.connect(lambda: c.show_settings("wardrobe"))
    for a in (auto, manual):
        group.addAction(a)
        outfit.addAction(a)
    outfit.addSeparator()
    outfit.addAction(t("menu.outfit_now"), c.reroll_outfit)

    # AI manbasi (radio)
    m.addSeparator()
    sources = QActionGroup(m)
    for key, source in (("menu.online", "online"), ("menu.offline", "offline")):
        act = QAction(t(key), m, checkable=True)
        act.setChecked(c.offline == (source == "offline"))
        act.triggered.connect(lambda _=False, s=source: c.set_source(s))
        sources.addAction(act)
        m.addAction(act)
    voice = QAction(t("menu.voice"), m, checkable=True)  # jim qilish tugmasi bilan bir xil
    voice.setChecked(c.voice.enabled)
    voice.triggered.connect(lambda _=False: c.toggle_voice())
    m.addAction(voice)

    m.addSeparator()
    m.addAction(t("menu.settings"), c.show_settings)
    m.addAction(t("menu.memory"), c.show_memory)
    if c.pet.isVisible() or not c.hidden_by_user:
        m.addAction(t("menu.hide"), lambda: c.set_hidden(True))
    else:
        m.addAction(t("menu.show"), lambda: c.set_hidden(False))
    if debug_enabled():
        _fill_debug(c, m.addMenu(t("menu.debug")))
    m.addSeparator()
    m.addAction(t("menu.about"), c.show_about)
    m.addAction(t("menu.quit"), c.quit)


def _fill_tasks(c: Controller, m: QMenu) -> None:
    tasks = c.brain.store.tasks()
    now = dt.datetime.now()
    if not tasks:
        act = m.addAction(t("menu.tasks.empty"))
        act.setEnabled(False)
    for task in tasks[:MAX_TASKS_IN_MENU]:
        title = c.brain.book.describe(task, now)
        if len(title) > 60:
            title = title[:57] + "…"
        sub = m.addMenu(title)
        sub.addAction(t("menu.tasks.done"), lambda tid=task.id: c.complete_task(tid))
        sub.addAction(t("menu.tasks.delete"), lambda tid=task.id: c.delete_task(tid))
    m.addSeparator()
    m.addAction(t("menu.tasks.add"), c.add_task_dialog)
    m.addAction(t("menu.tasks.remind"), lambda: c.brain.remind_open_tasks(force=True))


def _fill_debug(c: Controller, m: QMenu) -> None:
    pm = m.addMenu(t("menu.period"))
    group = QActionGroup(pm)
    options = [(t("menu.period.auto"), None)] + [(t(f"period.{p}"), p) for p in PERIODS]
    for text, value in options:
        act = QAction(text, pm, checkable=True)
        act.setChecked(c.period_override == value)
        act.triggered.connect(lambda _=False, v=value: c.set_period_override(v))
        group.addAction(act)
        pm.addAction(act)
    wardrobe = c.wardrobe
    om = m.addMenu(t("menu.debug.outfit"))
    group = QActionGroup(om)
    for outfit in c.meta.outfits if c.meta.version >= 4 else wardrobe.rules["base_outfits"]:
        act = QAction(t(f"outfit.{outfit}"), om, checkable=True)
        act.setChecked(wardrobe.base_outfit == outfit)
        act.triggered.connect(lambda _=False, o=outfit: c.debug_outfit(o))
        group.addAction(act)
        om.addAction(act)

    # Har bir slot; joriy kiyimda rasmi yo'qlari belgilanadi (fallback ko'rinadi).
    am = m.addMenu(t("menu.action"))
    for slot in c.meta.slots:
        if slot in ("expressions", "standup"):
            continue
        name = t(f"slot.{slot}")
        if not wardrobe.has(slot) and slot != "sleep":
            name = t("menu.debug.no_art", name=name)
        am.addAction(name, lambda s=slot: c.perform(s))

    cm = m.addMenu(t("menu.debug.commands"))  # harakatlar.json dagi har bir buyruq
    for name in c.commands.names:
        cm.addAction(name, lambda n=name: c.run_command(n))
    cm.addSeparator()
    cm.addAction(t("menu.debug.sayr30"), lambda: c.run_command("sayr", seconds=30.0))

    m.addAction(t("menu.debug.drop"), c.debug_drop)
    m.addAction(t("menu.debug.blink"), c.debug_blink)

    em = m.addMenu(t("menu.debug.expression"))
    tags = list(c.meta.raw.get("expression_map") or c.meta.slots["expressions"].names)
    for tag in tags:
        name = t(f"expr.{tag}") if f"expr.{tag}" in STRINGS else tag
        if not c.behavior.expression_available(tag):
            name = t("menu.debug.no_art", name=name)
        em.addAction(name, lambda tg=tag: c.debug_expression(tg))

    sm = m.addMenu(t("menu.debug.speed"))
    group = QActionGroup(sm)
    for tempo in WALK_TEMPOS:
        act = QAction(f"{tempo * 100:.0f}%", sm, checkable=True)
        act.setChecked(abs(c.behavior.walk_tempo - tempo) < 0.01)
        act.triggered.connect(lambda _=False, v=tempo: c.set_walk_tempo(v))
        group.addAction(act)
        sm.addAction(act)


class TaskDialog(QDialog):
    """Vazifani qo'lda qo'shish: matn va (ixtiyoriy) vaqt."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("task.title"))
        self.setWindowIcon(app_icon())
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setMinimumWidth(420)
        self.result_task: tuple[str, str | None, str | None] | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(8)
        lay.addWidget(label(t("task.text")))
        self.text = QLineEdit()
        self.text.setPlaceholderText(t("task.text.placeholder"))
        self.text.setMaxLength(300)
        uz_edit_menu(self.text)
        lay.addWidget(self.text)
        lay.addSpacing(6)
        lay.addWidget(label(t("task.when")))
        self.when = QLineEdit()
        self.when.setPlaceholderText(t("task.when.placeholder"))
        uz_edit_menu(self.when)
        lay.addWidget(self.when)
        self.error = label("", muted=True)
        self.error.hide()
        lay.addWidget(self.error)

        row = QHBoxLayout()
        row.addStretch(1)
        cancel = button(t("btn.cancel"))
        cancel.clicked.connect(self.reject)
        ok = button(t("btn.add"), primary=True)
        ok.clicked.connect(self._accept)
        row.addWidget(cancel)
        row.addWidget(ok)
        lay.addSpacing(8)
        lay.addLayout(row)
        self.text.returnPressed.connect(self.when.setFocus)
        self.when.returnPressed.connect(self._accept)

    def _accept(self) -> None:
        text = " ".join(self.text.text().split())
        if not text:
            self.text.setFocus()
            return
        parsed = parse_user_time(self.when.text(), dt.datetime.now())
        if parsed is None:
            self.error.setText(t("task.when.bad"))
            self.error.show()
            self.when.setFocus()
            return
        self.result_task = (text, parsed[0], parsed[1])
        self.accept()
