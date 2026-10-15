""" "Yue haqida" oynasi: versiya, qisqa tavsif, maxfiylik va hujjatlarni ochadigan tugmalar."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout

from yue import __version__, docs, paths
from yue.i18n import t
from yue.ui.styles import app_icon, button, label

# Har kompyuterda ochiladigan formatlar: .html va .txt (`yue.docs`)
DOCS = (
    ("about.readme", docs.README_HTML),
    ("about.license", docs.LICENSE_TXT),
    ("about.third_party", docs.THIRD_PARTY),
)


def open_doc(name: str) -> bool:
    """Hujjatni standart dastur bilan ochish (manba versiyada — vaqtinchalik nusxasi)."""
    path = docs.doc_file(name)
    return path is not None and QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


class AboutDialog(QDialog):
    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowTitle(t("about.title"))
        self.setWindowIcon(app_icon())
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setMinimumWidth(460)
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 20, 22, 16)
        v.addWidget(label(t("about.heading", version=__version__), heading=True))
        v.addWidget(label(t("about.description")))
        v.addSpacing(6)
        v.addWidget(label(t("about.privacy"), muted=True))
        v.addWidget(label(t("about.data", path=str(paths.data_dir())), muted=True))
        v.addSpacing(8)
        row = QHBoxLayout()
        self.doc_buttons = {}
        for key, name in DOCS:
            b = button(t(key))
            b.clicked.connect(lambda _=False, n=name: open_doc(n))
            self.doc_buttons[name] = b
            row.addWidget(b)
        row.addStretch(1)
        close = button(t("btn.close"), primary=True)
        close.clicked.connect(self.accept)
        row.addWidget(close)
        v.addLayout(row)
