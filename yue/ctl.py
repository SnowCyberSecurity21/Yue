"""Bitta nusxa va boshqaruv kanali.

- Kanal: `QLocalServer` (Windows'da nomli pipe) + `UserAccessOption` — faqat joriy Windows
  foydalanuvchisi ulana oladi. Nom foydalanuvchi va ma'lumotlar papkasiga bog'liq.
- Autentifikatsiya: birinchi nusxa tasodifiy token yaratib, uni `%APPDATA%\\Yue\\ctl.token` ga
  yozadi (foydalanuvchi profili ACL bilan himoyalangan). Har bir buyruq shu token bilan keladi;
  tokeni noto'g'ri yoki buyruq oq ro'yxatda bo'lmasa — e'tiborsiz qoldiriladi.
- Ikkinchi ishga tushirish birinchisiga "show" (yoki "toggle") yuboradi va o'zi chiqadi.
- Qulf: `%APPDATA%\\Yue\\yue.lock` (`QLockFile`) — kanal hali ochilmagan bo'lsa ham (masalan,
  autostart nusxasi ish stoli tinchlanishini kutyapti) ikkinchi nusxa ishga tushmaydi.
"""

from __future__ import annotations

import getpass
import hashlib
import hmac
import logging
import os
import secrets
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from yue import paths

log = logging.getLogger(__name__)

COMMANDS = frozenset({"show", "toggle", "hide", "chat"})
MAX_MSG = 256


def server_name() -> str:
    """Kanal nomi: foydalanuvchi va ma'lumotlar papkasiga bog'liq.

    `YUE_DATA` bilan ishga tushirilgan nusxa (testlar, sinov) haqiqiy Yuega ulanmaydi.
    """
    data = str(paths.data_dir().resolve()).lower()
    user = f"{getpass.getuser()}|{os.environ.get('USERDOMAIN', '')}|{data}"
    return "yue-ctl-" + hashlib.sha256(user.encode()).hexdigest()[:16]


def token_path() -> Path:
    return paths.data_dir() / "ctl.token"


def lock_path() -> Path:
    return paths.data_dir() / "yue.lock"


def acquire_instance_lock() -> QLockFile | None:
    """Bitta nusxa qulfi; band bo'lsa — None. Qulf obyekti ilova yopilguncha saqlanadi."""
    try:
        paths.data_dir().mkdir(parents=True, exist_ok=True)
    except OSError:
        log.warning("ma'lumotlar papkasi yaratilmadi")
    lock = QLockFile(str(lock_path()))
    lock.setStaleLockTime(0)  # eskirgan deb faqat egasi (PID) yo'q bo'lsa hisoblanadi
    if lock.tryLock(0):
        return lock
    return None


def send_command(cmd: str, timeout_ms: int = 800) -> bool:
    """Ishlab turgan nusxaga buyruq. True — u bor va buyruqni oldi."""
    try:
        token = token_path().read_text(encoding="ascii").strip()
    except OSError:
        token = ""
    sock = QLocalSocket()
    sock.connectToServer(server_name())
    if not sock.waitForConnected(timeout_ms):
        return False
    sock.write(f"{token} {cmd}\n".encode("ascii", "ignore"))
    sock.flush()
    sock.waitForBytesWritten(timeout_ms)
    sock.disconnectFromServer()
    return True


class ControlServer(QObject):
    command = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self._on_connection)
        self._token = secrets.token_hex(32)

    def start(self) -> bool:
        name = server_name()
        if not self.server.listen(name):
            QLocalServer.removeServer(name)  # oldingi nusxa yiqilgan bo'lsa
            if not self.server.listen(name):
                log.warning("boshqaruv kanali ochilmadi")
                return False
        try:
            path = token_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self._token, encoding="ascii")
        except OSError:
            log.warning("boshqaruv tokeni yozilmadi")
        return True

    def stop(self) -> None:
        self.server.close()
        try:
            if token_path().read_text(encoding="ascii").strip() == self._token:
                token_path().unlink()
        except OSError:
            pass

    def _on_connection(self) -> None:
        while self.server.hasPendingConnections():
            sock = self.server.nextPendingConnection()
            sock.readyRead.connect(lambda s=sock: self._read(s))
            sock.disconnected.connect(sock.deleteLater)

    def _read(self, sock: QLocalSocket) -> None:
        data = bytes(sock.readAll().data())[:MAX_MSG]
        sock.disconnectFromServer()
        self.handle(data)

    def handle(self, data: bytes, emit: Callable[[str], None] | None = None) -> bool:
        """Xabarni tekshirish. True — qabul qilindi."""
        try:
            token, cmd = data.decode("ascii").strip().split(" ", 1)
        except (UnicodeDecodeError, ValueError):
            log.warning("boshqaruv kanali: noto'g'ri xabar rad etildi")
            return False
        if not hmac.compare_digest(token, self._token) or cmd not in COMMANDS:
            log.warning("boshqaruv kanali: ruxsatsiz buyruq rad etildi")
            return False
        (emit or self.command.emit)(cmd)
        return True
