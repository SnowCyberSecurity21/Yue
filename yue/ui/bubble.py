"""Gap pufagi: Yuening boshi tepasida, ekrandan chiqib ketmaydi.

- ko'rsatish rejimi: matn harflab chiqadi (yoki streaming), bir necha soniyadan keyin yopiladi;
- kiritish rejimi: Enter — yuborish, Shift+Enter — yangi qator, Esc — yopish;
- javobni nusxalash tugmasi.
Pufak fokusni o'zi olmaydi; faqat foydalanuvchi yozmoqchi bo'lganda faollashadi.
Kiritish maydoni hech qachon qulflanmaydi: Yue o'ylayotganda ham yozish mumkin, faqat yuborish
(tugma va Enter) vaqtincha o'chadi va matn maydonda qoladi. Maydon balandligi o'ralgan
(vizual) qatorlar soniga qarab o'sadi — uzun matnning boshi ko'rinmay qolmaydi.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from yue.i18n import t
from yue.ui.styles import ACCENT, INK, LINE, MUTED, uz_edit_menu, uz_label_menu

WIDTH = 330
TAIL = 12
RADIUS = 14
SHADOW = 6
MAX_TEXT_H = 280
MAX_EDIT_LINES = 5  # shundan ko'p bo'lsa maydon ichida aylantiriladi
TYPE_MS = 22
TYPE_CHARS = 2
MILK = "#f8f2e4"  # pufak foni — sut rang
FIELD = "#fffcf5"  # kiritish maydoni — biroz ochroq sut rang


class _EnterFilter(QObject):
    def __init__(self, bubble: Bubble) -> None:
        super().__init__(bubble)
        self.bubble = bubble

    def eventFilter(self, obj, ev) -> bool:  # noqa: N802
        if ev.type() == QEvent.Type.KeyPress:
            assert isinstance(ev, QKeyEvent)
            if ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if not ev.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.bubble.submit()
                    return True
            elif ev.key() == Qt.Key.Key_Escape:
                self.bubble.close_bubble()
                return True
        elif ev.type() == QEvent.Type.MouseButtonPress and isinstance(ev, QMouseEvent):
            # Maydon bosilsa — pufak faollashadi va klaviatura shu yerga keladi.
            self.bubble.activateWindow()
            self.bubble.edit.setFocus(Qt.FocusReason.MouseFocusReason)
        return False


class Bubble(QWidget):
    submitted = Signal(str)
    closed = Signal()
    typing = Signal(bool)  # matn chiqyapti (gapirish animatsiyasi uchun)

    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("Yue")
        self.setFixedWidth(WIDTH)

        self._full = ""
        self._shown = 0
        self._tail_x = WIDTH / 2
        self._tail_down = True
        self._anchor: tuple[float, float, float] | None = None
        self.input_mode = False
        self.busy = False  # Yue javob tayyorlayapti — yuborish vaqtincha o'chiq

        outer = QVBoxLayout(self)
        outer.setContentsMargins(SHADOW + 12, SHADOW + 10, SHADOW + 12, SHADOW + TAIL + 8)
        outer.setSpacing(8)

        self.text = QLabel()
        self.text.setWordWrap(True)
        self.text.setTextFormat(Qt.TextFormat.PlainText)
        self.text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.text.setStyleSheet(f"color: {INK}; font-size: 10.5pt; background: transparent;")
        self.text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        uz_label_menu(self.text)
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.text)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            "QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        outer.addWidget(self.scroll)

        tools = QHBoxLayout()
        tools.setSpacing(4)
        self.copy_btn = self._tool("⧉", t("bubble.copy"), self.copy_text)
        self.close_btn = self._tool("✕", t("bubble.close"), self.close_bubble)
        self.status = QLabel(t("bubble.thinking"))
        self.status.setStyleSheet(f"color: {MUTED}; font-size: 9pt; background: transparent;")
        self.status.hide()
        tools.addWidget(self.copy_btn)
        # Gapga bog'liq bitta tugma (masalan, kalitsiz rejimda "Sozlamalarni ochish")
        self.action_btn = QToolButton()
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_btn.setStyleSheet(
            f"QToolButton {{ color: {ACCENT}; border: 1px solid {ACCENT}; padding: 2px 8px;"
            f" border-radius: 8px; background: transparent; }}"
            f"QToolButton:hover {{ background: #efeefa; }}"
        )
        self.action_btn.clicked.connect(self._on_action)
        self.action_btn.hide()
        self._action = None
        tools.addWidget(self.action_btn)
        tools.addStretch(1)
        tools.addWidget(self.status)
        tools.addStretch(1)
        tools.addWidget(self.close_btn)
        outer.addLayout(tools)

        self.input_row = QWidget()
        row = QHBoxLayout(self.input_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText(t("bubble.placeholder"))
        self.edit.setTabChangesFocus(True)
        self.edit.setStyleSheet(
            f"QPlainTextEdit {{ background: {FIELD}; border: 1px solid {LINE}; border-radius: 9px;"
            f" padding: 4px 6px; color: {INK}; }}"
            f"QPlainTextEdit:focus {{ border-color: {ACCENT}; }}"
        )
        enter = _EnterFilter(self)
        self.edit.installEventFilter(enter)
        self.edit.viewport().installEventFilter(enter)
        self.edit.textChanged.connect(self._fit_edit)
        uz_edit_menu(self.edit)
        self.send_btn = self._tool("➤", t("bubble.send"), self.submit)
        row.addWidget(self.edit, 1)
        row.addWidget(self.send_btn, 0, Qt.AlignmentFlag.AlignBottom)
        outer.addWidget(self.input_row)
        self.input_row.hide()
        self._fit_edit()

        self.type_timer = QTimer(self)
        self.type_timer.setInterval(TYPE_MS)
        self.type_timer.timeout.connect(self._type_step)
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._auto_hide)

    def _tool(self, glyph: str, tip: str, fn) -> QToolButton:
        b = QToolButton()
        b.setText(glyph)
        b.setToolTip(tip)
        b.setAutoRaise(True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(
            f"QToolButton {{ color: {MUTED}; border: none; padding: 2px 6px; border-radius: 6px; }}"
            f"QToolButton:hover {{ background: #efeefa; color: {INK}; }}"
        )
        b.clicked.connect(fn)
        return b

    # --- matn --------------------------------------------------------------------------------

    def show_action(self, text: str, fn) -> None:
        """Joriy gap ostida bitta tugma; keyingi gap chiqqanda yo'qoladi."""
        self._action = fn
        self.action_btn.setText(text)
        self.action_btn.show()
        self._relayout()

    def _on_action(self) -> None:
        fn, self._action = self._action, None
        self.action_btn.hide()
        if fn is not None:
            fn()

    def show_text(self, text: str, *, typewriter: bool = True, auto_hide: bool = True) -> None:
        """Yuening gapi (tayyor ibora yoki yakuniy javob)."""
        self.hide_timer.stop()
        self.action_btn.hide()
        self._full = text
        if typewriter and text:
            self._shown = 0
            self.text.setText("")
            self.type_timer.start()
            self.typing.emit(True)
        else:
            self.type_timer.stop()
            self._shown = len(text)
            self.text.setText(text)
            self.typing.emit(False)
        self.copy_btn.setVisible(bool(text))
        self._relayout()
        self._pop()
        if auto_hide and not self.input_mode:
            self._arm_hide(text)

    def set_stream(self, text: str) -> None:
        """Streaming: javobning hozirgacha kelgan qismi."""
        self.hide_timer.stop()
        self.type_timer.stop()
        self._full = text
        self._shown = len(text)
        self.text.setText(text)
        self.copy_btn.setVisible(bool(text))
        self._relayout()
        self._pop()
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _type_step(self) -> None:
        self._shown = min(len(self._full), self._shown + TYPE_CHARS)
        self.text.setText(self._full[: self._shown])
        if self._shown >= len(self._full):
            self.type_timer.stop()
            self.typing.emit(False)
        self._relayout()

    def finish_typing(self) -> None:
        if self.type_timer.isActive():
            self._shown = len(self._full)
            self.text.setText(self._full)
            self.type_timer.stop()
            self.typing.emit(False)
            self._relayout()

    def _arm_hide(self, text: str) -> None:
        secs = 5.0 + len(text) / 14.0
        self.hide_timer.start(int(min(secs, 45.0) * 1000))

    def _auto_hide(self) -> None:
        if self.input_mode or self.underMouse():
            self.hide_timer.start(3000)
            return
        self.close_bubble()

    def copy_text(self) -> None:
        QApplication.clipboard().setText(self._full)
        self.copy_btn.setToolTip(t("bubble.copied"))
        QTimer.singleShot(1500, lambda: self.copy_btn.setToolTip(t("bubble.copy")))

    # --- kiritish -----------------------------------------------------------------------------

    def open_input(self) -> None:
        """Kiritish maydonini ochish. Taklif gapini Controller `say_text` orqali aytadi."""
        self.input_mode = True
        self.hide_timer.stop()
        self.input_row.show()
        self._relayout()
        self._pop()
        self._fit_edit()
        self.focus_input()

    def focus_input(self) -> None:
        """Kiritish maydoniga klaviatura fokusi (faqat foydalanuvchi pufak bilan ishlayotganda)."""
        self.raise_()
        self.activateWindow()
        self.edit.setFocus(Qt.FocusReason.OtherFocusReason)

    def submit(self) -> None:
        text = self.edit.toPlainText().strip()
        if not text or self.busy:
            return  # Yue hali javob bermadi — matn maydonda qoladi
        self.edit.clear()
        self.submitted.emit(text)

    def restore_input(self, text: str) -> None:
        """Yuborilmay qolgan matnni maydonga qaytarish."""
        if not self.edit.toPlainText().strip():
            self.edit.setPlainText(text)
            self.edit.moveCursor(self.edit.textCursor().MoveOperation.End)

    def set_busy(self, on: bool) -> None:
        """Yue o'ylayapti: maydon ochiq qoladi, faqat yuborish o'chadi va belgi ko'rinadi."""
        self.busy = on
        self.send_btn.setEnabled(not on)
        self.status.setVisible(on)
        if self.isVisible():
            self._relayout()

    def edit_lines(self) -> int:
        """Maydondagi matnning o'ralgan (vizual) qatorlari soni."""
        doc = self.edit.document()
        fm = self.edit.fontMetrics()
        width = max(40, int(self.edit.viewport().width() - 2 * doc.documentMargin()))
        text = self.edit.toPlainText() or self.edit.placeholderText() or " "
        if text.endswith("\n"):
            text += " "
        rect = fm.boundingRect(QRect(0, 0, width, 100_000), Qt.TextFlag.TextWordWrap, text)
        return max(1, round(rect.height() / fm.lineSpacing()))

    def _fit_edit(self) -> None:
        lines = self.edit_lines()
        shown = min(MAX_EDIT_LINES, lines)
        fm = self.edit.fontMetrics()
        doc = self.edit.document()
        extra = 2 * doc.documentMargin() + 2 * self.edit.frameWidth() + 10
        self.edit.setFixedHeight(int(shown * fm.lineSpacing() + extra))
        bar = self.edit.verticalScrollBar()
        if lines <= MAX_EDIT_LINES:
            bar.setValue(0)  # hammasi sig'adi — boshidan ko'rinsin
        else:
            self.edit.ensureCursorVisible()
        if self.isVisible():
            self._relayout()
            # Ota layout maydonning yangi balandligini keyingi siklda oladi — shunda qayta.
            QTimer.singleShot(0, self._relayout)

    def close_bubble(self) -> None:
        self.type_timer.stop()
        self.hide_timer.stop()
        self.input_mode = False
        self.input_row.hide()
        self.hide()
        self.typing.emit(False)
        self.closed.emit()

    def keyPressEvent(self, e: QKeyEvent) -> None:  # noqa: N802
        if e.key() == Qt.Key.Key_Escape:
            self.close_bubble()
            return
        super().keyPressEvent(e)

    def enterEvent(self, e) -> None:  # noqa: N802
        self.finish_typing()
        super().enterEvent(e)

    # --- joylashuv ---------------------------------------------------------------------------

    def anchor_to(self, x: float, head_y: float, foot_y: float) -> None:
        """Yue boshi ustidagi nuqta (global mantiqiy px)."""
        self._anchor = (x, head_y, foot_y)
        if self.isVisible():
            self._place()

    def _relayout(self) -> None:
        self.text.adjustSize()
        doc_h = self.text.heightForWidth(WIDTH - 2 * (SHADOW + 12) - 4)
        self.scroll.setFixedHeight(max(20, min(MAX_TEXT_H, doc_h + 4)))
        self.layout().activate()  # yangi o'lchamlar darhol hisobga olinsin (pufak qisqarsin)
        self.resize(self.width(), self.layout().sizeHint().height())
        self._place()

    def _place(self) -> None:
        if self._anchor is None:
            return
        x, head_y, foot_y = self._anchor
        screen = (
            QGuiApplication.screenAt(QPointF(x, foot_y - 5).toPoint())
            or QGuiApplication.primaryScreen()
        )
        area: QRect = screen.availableGeometry()
        w, h = self.width(), self.height()
        left = max(area.left() + 2, min(area.right() - w - 2, x - w / 2))
        top = head_y - h + 4
        self._tail_down = True
        if top < area.top() + 2:
            # Tepada joy yo'q — Yue yonida, tepasiz
            top = area.top() + 2
            self._tail_down = False
        self._tail_x = max(RADIUS + 14, min(w - RADIUS - 14, x - left))
        self.move(int(left), int(top))
        self.update()

    def _pop(self) -> None:
        if not self.isVisible():
            self._place()
            self.show()
        self.raise_()

    # --- chizish -----------------------------------------------------------------------------

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        body = QRectF(SHADOW, SHADOW, self.width() - 2 * SHADOW, self.height() - 2 * SHADOW - TAIL)
        path = QPainterPath()
        path.addRoundedRect(body, RADIUS, RADIUS)
        if self._tail_down:
            tx, by = self._tail_x, body.bottom()
            tail = QPainterPath()
            tail.moveTo(tx - 10, by - 1)
            tail.quadTo(tx - 2, by + 2, tx + 2, by + TAIL)
            tail.quadTo(tx + 4, by + 4, tx + 12, by - 1)
            tail.closeSubpath()
            path = path.united(tail)
        for i, alpha in enumerate((18, 12, 7)):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(30, 20, 60, alpha))
            p.drawPath(path.translated(0, 1.5 + i))
        p.setBrush(QColor(MILK))
        p.setPen(QPen(QColor(LINE), 1.2))
        p.drawPath(path)
        p.end()
