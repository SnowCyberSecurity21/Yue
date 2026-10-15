"""Xotira oynasi: xulosa, faktlar, sog'liq daftari, vazifalar; tozalash va eksport."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from yue.i18n import t
from yue.ui.styles import app_icon, ask, button, inform, label, uz_edit_menu

if TYPE_CHECKING:
    from yue.app import Controller


class MemoryDialog(QDialog):
    def __init__(self, c: Controller) -> None:
        super().__init__(None)
        self.c = c
        self.store = c.brain.store
        self.setWindowTitle(t("memory.title"))
        self.setWindowIcon(app_icon())
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setMinimumSize(560, 480)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        if c.brain.memory_reset:
            root.addWidget(label(t("memory.reset"), muted=True))
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self.summary = QPlainTextEdit()
        self.summary.setReadOnly(True)
        uz_edit_menu(self.summary)
        self.tabs.addTab(self._wrap(self.summary), t("memory.summary"))

        self.facts = QListWidget()
        self.tabs.addTab(self._list_page(self.facts, self._delete_fact), t("memory.facts"))
        self.health = QListWidget()
        self.tabs.addTab(self._list_page(self.health, self._delete_health), t("memory.health"))
        self.tasks = QListWidget()
        self.tabs.addTab(self._list_page(self.tasks, self._delete_task), t("memory.tasks"))

        row = QHBoxLayout()
        export = button(t("memory.export"))
        export.clicked.connect(self._export)
        clear = button(t("memory.clear"), danger=True)
        clear.clicked.connect(self._clear)
        close = button(t("btn.close"), primary=True)
        close.clicked.connect(self.accept)
        row.addWidget(export)
        row.addWidget(clear)
        row.addStretch(1)
        row.addWidget(close)
        root.addLayout(row)
        self.reload()

    def _wrap(self, w: QWidget) -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        v = QVBoxLayout(page)
        v.setContentsMargins(12, 12, 12, 12)
        v.addWidget(w)
        return page

    def _list_page(self, lst: QListWidget, on_delete) -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        v = QVBoxLayout(page)
        v.setContentsMargins(12, 12, 12, 12)
        lst.setWordWrap(True)
        lst.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        v.addWidget(lst, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        delete = button(t("btn.delete"), danger=True)
        delete.clicked.connect(on_delete)
        row.addWidget(delete)
        v.addLayout(row)
        return page

    @staticmethod
    def _fill(lst: QListWidget, items: list[tuple[int, str]]) -> None:
        lst.clear()
        if not items:
            it = QListWidgetItem(t("memory.empty"))
            it.setFlags(Qt.ItemFlag.NoItemFlags)
            lst.addItem(it)
            return
        for iid, text in items:
            it = QListWidgetItem(text)
            it.setData(Qt.ItemDataRole.UserRole, iid)
            lst.addItem(it)

    def reload(self) -> None:
        self.summary.setPlainText(self.store.get_summary() or t("memory.summary.empty"))
        self._fill(self.facts, [(f.id, f.text) for f in self.store.facts()])
        self._fill(self.health, [(h.id, h.text) for h in self.store.health()])
        now = dt.datetime.now()
        self._fill(
            self.tasks, [(x.id, self.c.brain.book.describe(x, now)) for x in self.store.tasks()]
        )

    @staticmethod
    def _selected(lst: QListWidget) -> int | None:
        it = lst.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _delete_fact(self) -> None:
        if (iid := self._selected(self.facts)) is not None:
            self.store.delete_fact(iid)
            self.reload()

    def _delete_health(self) -> None:
        if (iid := self._selected(self.health)) is not None:
            self.store.delete_health(iid)
            self.reload()

    def _delete_task(self) -> None:
        if (iid := self._selected(self.tasks)) is not None:
            self.c.delete_task(iid)
            self.reload()

    def _clear(self) -> None:
        if ask(self, t("memory.title"), t("memory.clear.confirm"), danger=True):
            self.c.brain.clear_memory()
            self.reload()

    def _export(self) -> None:
        if not ask(self, t("memory.title"), t("memory.export.warn"), danger=True):
            return
        path, _ = QFileDialog.getSaveFileName(
            self, t("memory.export"), t("memory.export.file"), t("memory.export.filter")
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.store.export_json())
        except OSError:
            inform(self, t("memory.title"), t("memory.export.fail"))
            return
        inform(self, t("memory.title"), t("memory.export.done", path=path))
