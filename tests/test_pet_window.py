"""pytest-qt tutun testi: oyna yaratiladi, kadrlar almashadi, sudrash ishlaydi."""

import random
import time

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from yue import paths
from yue.config import Config
from yue.pet.behavior import Behavior
from yue.pet.pack import load_pack
from yue.pet.physics import Body, Rect
from yue.pet.sprites import SpriteStore
from yue.pet.wardrobe import Wardrobe
from yue.pet.window import PetWindow, ScreenInfo, to_logical
from yue.platform import NullPlatform


def test_to_logical_with_dpi():
    screens = [
        ScreenInfo(Rect(0, 0, 1536, 864), 0, 0, 1.25),  # 1920×1080 @125%
        ScreenInfo(Rect(1920, 0, 1920 + 1280, 720), 1920, 0, 1.5),  # 1920×1080 @150%
    ]
    r = to_logical((100, 200, 1100, 700), screens)
    assert (r.left, r.top, r.right, r.bottom) == (80, 160, 880, 560)
    r2 = to_logical((1920 + 300, 150, 1920 + 900, 600), screens)
    assert (r2.left, r2.top, r2.right, r2.bottom) == (2120, 100, 2520, 400)


@pytest.fixture
def pet(qtbot):
    meta = load_pack(paths.DEFAULT_PACK)
    wardrobe = Wardrobe.from_pack(meta.raw, rng=random.Random(1))
    bh = Behavior(meta, wardrobe, Body(), lambda: "day", rng=random.Random(1))
    store = SpriteStore(meta)
    win = PetWindow(meta, bh, store, NullPlatform(), Config())
    qtbot.addWidget(win)
    bh.start(time.monotonic())
    store.set_k(win.scale * win.devicePixelRatioF())
    win.spawn()
    win.show()
    yield win
    store.shutdown()


def test_window_flags(pet):
    flags = pet.windowFlags()
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowDoesNotAcceptFocus
    assert pet.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)


def test_frames_change_and_lands(qtbot, pet):
    qtbot.waitUntil(lambda: pet.behavior.body.grounded, timeout=10_000)
    keys = set()

    def collect():
        keys.add(pet._painted_key)
        return len(keys) >= 4

    qtbot.waitUntil(collect, timeout=10_000)
    img = pet.grab().toImage()
    assert any(
        img.pixelColor(x, y).alpha() > 0
        for x in range(0, img.width(), 4)
        for y in range(0, img.height(), 4)
    )


def opaque_point(qtbot, pet):
    """Yue chizilgan (shaffof bo'lmagan) nuqta — oyna koordinatasida."""
    qtbot.waitUntil(lambda: pet._shown is not None, timeout=10_000)
    for y in range(int(pet.anchor.y()) - 10, 0, -4):
        p = QPointF(pet.anchor.x(), y)
        if pet.hit(p):
            return p
    raise AssertionError("Yue topilmadi")


def test_drag_and_release(qtbot, pet):
    qtbot.waitUntil(lambda: pet.behavior.body.grounded, timeout=10_000)
    c = opaque_point(qtbot, pet)
    g = QPointF(pet.mapToGlobal(c.toPoint()))

    def ev(kind, local, glob, buttons):
        return QMouseEvent(
            kind, local, glob, Qt.MouseButton.LeftButton, buttons, Qt.KeyboardModifier.NoModifier
        )

    left = Qt.MouseButton.LeftButton
    pet.mousePressEvent(ev(QMouseEvent.Type.MouseButtonPress, c, g, left))
    moved = g + QPointF(0, -200)
    pet.mouseMoveEvent(ev(QMouseEvent.Type.MouseMove, c, moved, left))
    assert pet.behavior.dragging
    qtbot.wait(100)
    bh = pet.behavior
    assert bh.last_visual.slot == bh.resolve("dangle", bh.look)[0]
    # Kursor yoqani ushlaydi: langar (oyoq) kursordan pastda, deyarli markazda
    off = pet._grab
    assert off.y() > 40 and abs(off.x()) < 30
    assert bh.body.y == pytest.approx(moved.y() + off.y())
    pet.mouseReleaseEvent(
        ev(QMouseEvent.Type.MouseButtonRelease, c, moved, Qt.MouseButton.NoButton)
    )
    assert not pet.behavior.dragging
    qtbot.waitUntil(lambda: pet.behavior.body.grounded, timeout=10_000)


def test_click_on_transparent_area_is_ignored(qtbot, pet):
    opaque_point(qtbot, pet)
    corner = QPointF(1, 1)
    g = QPointF(pet.mapToGlobal(QPoint(1, 1)))
    left = Qt.MouseButton.LeftButton
    got = []
    pet.clicked.connect(lambda: got.append(1))
    press = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress, corner, g, left, left, Qt.KeyboardModifier.NoModifier
    )
    pet.mousePressEvent(press)
    assert not press.isAccepted()
    pet.mouseReleaseEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            corner,
            g,
            left,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    assert got == []


def test_click_emits_clicked(qtbot, pet):
    c = opaque_point(qtbot, pet)
    g = QPointF(pet.mapToGlobal(QPoint(int(c.x()), int(c.y()))))
    left = Qt.MouseButton.LeftButton
    with qtbot.waitSignal(pet.clicked, timeout=1000):
        pet.mousePressEvent(
            QMouseEvent(
                QMouseEvent.Type.MouseButtonPress, c, g, left, left, Qt.KeyboardModifier.NoModifier
            )
        )
        pet.mouseReleaseEvent(
            QMouseEvent(
                QMouseEvent.Type.MouseButtonRelease,
                c,
                g,
                left,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
            )
        )


def test_foot_line_is_fixed_for_every_slot(pet):
    """Har slot/look'da lenta langari oynaning bir nuqtasiga tushadi — oyoq sakramaydi."""
    from yue.pet.behavior import Visual

    meta, ay = pet.meta, pet.anchor.y()
    for slot, info in meta.slots.items():
        for look_name, variant in info.variants.items():
            look = pet.behavior.wardrobe.make_look(look_name)
            for i in range(variant.frames):
                target, _ = pet._target(Visual(slot, i, look))
                strip, _ = variant.locate(i)
                assert target.top() + strip.foot_y * pet.scale == pytest.approx(ay)
                assert target.center().x() == pytest.approx(pet.anchor.x())
                assert target.top() >= 0 and target.bottom() <= pet.height()
                assert target.left() >= 0 and target.right() <= pet.width()
