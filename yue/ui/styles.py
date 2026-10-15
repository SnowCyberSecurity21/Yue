"""Umumiy uslub va o'zbekcha yordamchi vidjetlar.

Qt'ning o'zbekcha tarjimasi yo'q: QMessageBox/QDialogButtonBox standart tugmalari va matn
maydonlarining kontekst menyusi inglizcha chiqadi. Shuning uchun ular o'rniga bu yerdagi
`ask`, `inform` va `uz_edit_menu` ishlatiladi.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from yue import paths
from yue.i18n import t

INK = "#1f1d2b"
MUTED = "#6b6880"
PAPER = "#fffdf8"
ACCENT = "#5b5bd6"
ACCENT_SOFT = "#ecebfd"
LINE = "#e3e0ee"
DANGER = "#c2410c"

ARROW = (paths.RES / "assets" / "ui" / "arrow_down.svg").as_posix()
ARROW_UP = (paths.RES / "assets" / "ui" / "arrow_up.svg").as_posix()

APP_QSS = f"""
QDialog, QWidget#page {{ background: {PAPER}; color: {INK}; }}
QLabel {{ color: {INK}; }}
QLabel[muted="true"] {{ color: {MUTED}; }}
QLabel[heading="true"] {{ font-size: 15pt; font-weight: 600; }}
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: white; border: 1px solid {LINE}; border-radius: 8px; padding: 5px 8px;
    min-height: 22px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border: 1px solid {ACCENT};
}}
QComboBox::drop-down {{
    subcontrol-origin: padding; subcontrol-position: center right; width: 26px; border: none;
}}
QComboBox::down-arrow {{ image: url("{ARROW}"); width: 10px; height: 6px; }}
QComboBox::down-arrow:disabled {{ image: none; }}
QComboBox QAbstractItemView {{
    background: white; color: {INK}; border: 1px solid {LINE};
    selection-background-color: {ACCENT_SOFT}; selection-color: {INK}; outline: none;
}}
QAbstractSpinBox {{ padding-right: 24px; }}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
    subcontrol-origin: border; width: 22px; border: none; background: transparent;
}}
QAbstractSpinBox::up-button {{ subcontrol-position: top right; margin-top: 3px; }}
QAbstractSpinBox::down-button {{ subcontrol-position: bottom right; margin-bottom: 3px; }}
QAbstractSpinBox::up-arrow {{ image: url("{ARROW_UP}"); width: 10px; height: 6px; }}
QAbstractSpinBox::down-arrow {{ image: url("{ARROW}"); width: 10px; height: 6px; }}
QAbstractSpinBox::up-arrow:disabled, QAbstractSpinBox::up-arrow:off {{ image: none; }}
QAbstractSpinBox::down-arrow:disabled, QAbstractSpinBox::down-arrow:off {{ image: none; }}
QPushButton {{
    background: white; border: 1px solid {LINE}; border-radius: 8px; padding: 6px 14px;
    color: {INK};
}}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:pressed {{ background: {ACCENT_SOFT}; }}
QPushButton[primary="true"] {{ background: {ACCENT}; color: white; border-color: {ACCENT}; }}
QPushButton[primary="true"]:hover {{ background: #4a4ac4; }}
QPushButton[danger="true"] {{ color: {DANGER}; }}
QTabWidget::pane {{ border: 1px solid {LINE}; border-radius: 10px; top: -1px; background: white; }}
QTabBar::tab {{
    padding: 7px 14px; margin-right: 2px; border: 1px solid transparent;
    border-top-left-radius: 8px; border-top-right-radius: 8px; color: {MUTED};
}}
QTabBar::tab:selected {{ background: white; border-color: {LINE}; color: {INK}; }}
QListWidget {{ background: white; border: 1px solid {LINE}; border-radius: 8px; }}
QCheckBox, QRadioButton {{ spacing: 8px; }}
QMenu {{ background: white; border: 1px solid {LINE}; padding: 4px; }}
QMenu::item {{ padding: 6px 22px 6px 14px; border-radius: 6px; }}
QMenu::item:selected {{ background: {ACCENT_SOFT}; color: {INK}; }}
QMenu::separator {{ height: 1px; background: {LINE}; margin: 4px 8px; }}
QToolTip {{ background: white; color: {INK}; border: 1px solid {LINE}; padding: 4px; }}
"""


def light_palette() -> QPalette:
    """Windows qorong'i mavzusida ham o'qiladigan yorug' palitra (oq fon + oq matn bo'lmasin)."""
    pal = QPalette()
    roles = QPalette.ColorRole
    colors = {
        roles.Window: PAPER,
        roles.WindowText: INK,
        roles.Base: "#ffffff",
        roles.AlternateBase: "#f6f5fb",
        roles.Text: INK,
        roles.Button: "#ffffff",
        roles.ButtonText: INK,
        roles.BrightText: "#ffffff",
        roles.Highlight: ACCENT,
        roles.HighlightedText: "#ffffff",
        roles.Link: ACCENT,
        roles.LinkVisited: ACCENT,
        roles.ToolTipBase: "#ffffff",
        roles.ToolTipText: INK,
        roles.PlaceholderText: MUTED,
        roles.Light: "#ffffff",
        roles.Midlight: "#f3f2f8",
        roles.Mid: LINE,
        roles.Dark: "#bdb9cc",
        roles.Shadow: "#8c88a0",
    }
    for role, color in colors.items():
        pal.setColor(role, QColor(color))
    disabled = QPalette.ColorGroup.Disabled
    for role in (roles.Text, roles.WindowText, roles.ButtonText):
        pal.setColor(disabled, role, QColor("#aaa7b8"))
    return pal


def apply_app_style(app: QApplication) -> None:
    app.setStyle("Fusion")
    hints = app.styleHints()
    if hasattr(hints, "setColorScheme"):
        hints.setColorScheme(Qt.ColorScheme.Light)
    app.setPalette(light_palette())
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(APP_QSS)


def app_icon() -> QIcon:
    return QIcon(str(paths.ICON)) if paths.ICON.exists() else QIcon()


TRAY_SIZE = 64


def tray_icon(offline: bool = False) -> QIcon:
    """Tray belgisi: Offline'da o'ng pastda kulrang nuqta, Online'da belgisiz."""
    base = app_icon()
    if not offline:
        return base
    n = TRAY_SIZE
    pm = QPixmap(n, n)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    base.paint(p, 0, 0, n, n)
    r = n * 0.17
    p.setPen(QPen(QColor(255, 255, 255), n * 0.05))
    p.setBrush(QColor(128, 128, 136))
    p.drawEllipse(QPointF(n - r - n * 0.04, n - r - n * 0.04), r, r)
    p.end()
    return QIcon(pm)


def button(text: str, *, primary: bool = False, danger: bool = False) -> QPushButton:
    b = QPushButton(text)
    if primary:
        b.setProperty("primary", True)
        b.setDefault(True)
    if danger:
        b.setProperty("danger", True)
    return b


def label(text: str, *, muted: bool = False, heading: bool = False, wrap: bool = True) -> QLabel:
    lb = QLabel(text)
    lb.setWordWrap(wrap)
    if muted:
        lb.setProperty("muted", True)
    if heading:
        lb.setProperty("heading", True)
    return lb


# --- o'zbekcha kontekst menyu --------------------------------------------------------------


def uz_edit_menu(widget: QLineEdit | QPlainTextEdit | QTextEdit) -> None:
    """Matn maydoniga o'zbekcha "Kesish / Nusxalash / Qo'yish" menyusini o'rnatish."""
    widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def show(pos) -> None:
        m = QMenu(widget)
        if isinstance(widget, QLineEdit):
            ro = widget.isReadOnly()
            has_sel = widget.hasSelectedText()
            pairs = [
                ("edit.undo", widget.undo, widget.isUndoAvailable() and not ro),
                ("edit.redo", widget.redo, widget.isRedoAvailable() and not ro),
                (None, None, True),
                (
                    "edit.cut",
                    widget.cut,
                    has_sel and not ro and widget.echoMode() == QLineEdit.EchoMode.Normal,
                ),
                (
                    "edit.copy",
                    widget.copy,
                    has_sel and widget.echoMode() == QLineEdit.EchoMode.Normal,
                ),
                ("edit.paste", widget.paste, not ro),
                ("edit.delete", widget.del_, has_sel and not ro),
                (None, None, True),
                ("edit.select_all", widget.selectAll, bool(widget.text())),
            ]
        else:
            ro = widget.isReadOnly()
            has_sel = widget.textCursor().hasSelection()
            doc = widget.document()
            pairs = [
                ("edit.undo", widget.undo, doc.isUndoAvailable() and not ro),
                ("edit.redo", widget.redo, doc.isRedoAvailable() and not ro),
                (None, None, True),
                ("edit.cut", widget.cut, has_sel and not ro),
                ("edit.copy", widget.copy, has_sel),
                ("edit.paste", widget.paste, not ro and widget.canPaste()),
                (None, None, True),
                ("edit.select_all", widget.selectAll, not doc.isEmpty()),
            ]
        for key, fn, enabled in pairs:
            if key is None:
                m.addSeparator()
                continue
            act = m.addAction(t(key), fn)
            act.setEnabled(bool(enabled))
        m.exec(widget.mapToGlobal(pos))

    widget.customContextMenuRequested.connect(show)


def uz_label_menu(lb: QLabel) -> None:
    """Belgilanadigan QLabel uchun o'zbekcha "Nusxalash" menyusi."""
    lb.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def show(pos) -> None:
        m = QMenu(lb)
        text = lb.selectedText() or lb.text()
        m.addAction(t("edit.copy"), lambda: QApplication.clipboard().setText(text))
        m.exec(lb.mapToGlobal(pos))

    lb.customContextMenuRequested.connect(show)


# --- o'zbekcha xabar oynalari ---------------------------------------------------------------


class _Message(QDialog):
    def __init__(
        self, parent: QWidget | None, title: str, text: str, buttons: list[tuple[str, bool, bool]]
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowIcon(app_icon())
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.result_index = -1
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(14)
        body = label(text)
        body.setMinimumWidth(360)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        uz_label_menu(body)
        lay.addWidget(body)
        row = QHBoxLayout()
        row.addStretch(1)
        for i, (txt, primary, danger) in enumerate(buttons):
            b = button(txt, primary=primary, danger=danger)
            b.clicked.connect(lambda _=False, i=i: self._pick(i))
            row.addWidget(b)
        lay.addLayout(row)

    def _pick(self, i: int) -> None:
        self.result_index = i
        self.accept()


def ask(parent: QWidget | None, title: str, text: str, *, danger: bool = False) -> bool:
    """Ha/Yo'q tasdiq oynasi (o'zbekcha tugmalar)."""
    dlg = _Message(
        parent, title, text, [(t("btn.no"), False, False), (t("btn.yes"), not danger, danger)]
    )
    dlg.exec()
    return dlg.result_index == 1


def inform(parent: QWidget | None, title: str, text: str) -> None:
    dlg = _Message(parent, title, text, [(t("btn.close"), True, False)])
    dlg.exec()
