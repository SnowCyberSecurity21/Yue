"""Interfeys tutun testlari: gap pufagi, boshqaruv kanali, sozlamalar."""

from PySide6.QtCore import Qt

from yue.ctl import COMMANDS, ControlServer, server_name
from yue.ui.bubble import Bubble


def test_bubble_enter_sends_shift_enter_newline_esc_closes(qtbot):
    b = Bubble()
    qtbot.addWidget(b)
    b.anchor_to(500, 400, 560)
    b.open_input()
    b.show_text("Ha? Gapiring.", auto_hide=False)
    sent = []
    b.submitted.connect(sent.append)
    qtbot.keyClicks(b.edit, "Salom")
    qtbot.keyClick(b.edit, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    qtbot.keyClicks(b.edit, "Yue")
    assert b.edit.toPlainText() == "Salom\nYue"
    qtbot.keyClick(b.edit, Qt.Key.Key_Return)
    assert sent == ["Salom\nYue"] and b.edit.toPlainText() == ""
    with qtbot.waitSignal(b.closed, timeout=1000):
        qtbot.keyClick(b.edit, Qt.Key.Key_Escape)
    assert not b.isVisible() and not b.input_mode


def test_bubble_typewriter_and_stays_on_screen(qtbot):
    b = Bubble()
    qtbot.addWidget(b)
    b.anchor_to(5, 3, 200)  # ekranning chap-yuqori burchagi
    typing = []
    b.typing.connect(typing.append)
    b.show_text("Salom! Bugun nima qilamiz?")
    assert typing == [True]
    qtbot.waitUntil(lambda: typing[-1] is False, timeout=3000)
    assert b.text.text() == "Salom! Bugun nima qilamiz?"
    screen = b.screen().availableGeometry()
    assert screen.contains(b.frameGeometry().topLeft())


def test_bubble_stream_replaces_text(qtbot):
    b = Bubble()
    qtbot.addWidget(b)
    b.anchor_to(600, 400, 560)
    b.set_stream("Sal")
    b.set_stream("Salom, men")
    assert b.text.text() == "Salom, men"


def test_ctl_rejects_unauthenticated_and_unknown(tmp_path, monkeypatch, qapp):
    monkeypatch.setenv("YUE_DATA", str(tmp_path))
    srv = ControlServer()
    got = []
    token = srv._token
    assert srv.handle(f"{token} toggle".encode(), got.append)
    assert not srv.handle(b"notogri-token toggle", got.append)
    assert not srv.handle(f"{token} quit".encode(), got.append)  # oq ro'yxatda yo'q
    assert not srv.handle(f"{token} rm -rf".encode(), got.append)
    assert not srv.handle(b"\xff\xfe", got.append)
    assert got == ["toggle"]
    assert "quit" not in COMMANDS


def test_ctl_end_to_end_single_instance(tmp_path, monkeypatch, qtbot):
    """Ikkinchi nusxa (alohida jarayon) birinchisiga buyruq yuboradi."""
    import os
    import subprocess
    import sys

    from yue import paths

    monkeypatch.setenv("YUE_DATA", str(tmp_path))
    srv = ControlServer()
    assert srv.start()
    assert (tmp_path / "ctl.token").read_text() == srv._token
    code = (
        "import sys; from yue.ctl import send_command; sys.exit(0 if send_command('show') else 3)"
    )
    env = dict(os.environ, YUE_DATA=str(tmp_path))
    try:
        with qtbot.waitSignal(srv.command, timeout=10_000) as sig:
            proc = subprocess.Popen([sys.executable, "-c", code], env=env, cwd=str(paths.RES))
            qtbot.waitUntil(lambda: proc.poll() is not None, timeout=10_000)
        assert proc.returncode == 0
        assert sig.args == ["show"]
    finally:
        srv.stop()
    assert not (tmp_path / "ctl.token").exists()
    assert server_name().startswith("yue-ctl-")


def test_second_run_exits_when_lock_is_busy(tmp_path, monkeypatch, qapp):
    """Qulf band (masalan, autostart nusxasi 15 s kutyapti) — ikkinchi run() ishga tushmaydi."""
    import yue.app
    from yue.ctl import acquire_instance_lock

    monkeypatch.setenv("YUE_DATA", str(tmp_path))
    monkeypatch.setattr(yue.app, "setup_logging", lambda: None)
    monkeypatch.setattr(yue.app, "INSTANCE_RETRY_S", 0.3)
    sent = []
    monkeypatch.setattr(yue.app, "send_command", lambda cmd: sent.append(cmd) or False)
    monkeypatch.setattr(yue.app.time, "sleep", lambda s: None)

    def no_controller(*a, **kw):
        raise AssertionError("ikkinchi nusxa ishga tushdi")

    monkeypatch.setattr(yue.app, "Controller", no_controller)
    first = acquire_instance_lock()
    assert first is not None
    try:
        assert acquire_instance_lock() is None
        assert yue.app.run(autostart=True) == 0
        assert len(sent) >= 2 and set(sent) == {"show"}  # 3 s davomida qayta urinadi
    finally:
        first.unlock()
    lock = acquire_instance_lock()  # bo'shatilgach yana olinadi
    assert lock is not None
    lock.unlock()
