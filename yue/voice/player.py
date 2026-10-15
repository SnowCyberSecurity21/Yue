"""O'ynatish: QtMultimedia (QMediaPlayer + QAudioOutput). Keshdagi fayl yoki xotiradagi mp3.

QtMultimedia faqat birinchi o'ynatishda yuklanadi (ovoz ishlatilmasa — umuman yuklanmaydi).

Qurilma: QAudioOutput o'zi standart qurilmaga ergashmaydi — naushnik ulansa/uzilsa
(`audioOutputsChanged`) va har o'ynatish oldidan Windows'dagi standart qurilmaga o'tkaziladi.
Ovoz qurilmasi umuman bo'lmasa — jim (gap darhol "tugaydi"), Yue ishlayveradi.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, QTimer, QUrl, Signal

log = logging.getLogger(__name__)


class QtPlayer(QObject):
    finished = Signal()  # tugadi yoki o'ynatib bo'lmadi

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer

        self._status_end = (
            QMediaPlayer.MediaStatus.EndOfMedia,
            QMediaPlayer.MediaStatus.InvalidMedia,
        )
        self.output = QAudioOutput(self)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.output)
        self.player.mediaStatusChanged.connect(self._on_status)
        self.player.errorOccurred.connect(self._on_error)
        self.devices = QMediaDevices(self)
        self.devices.audioOutputsChanged.connect(self.sync_device)
        self._buffer: QBuffer | None = None
        self._active = False
        self._token = 0  # har o'ynatish/to'xtatishda oshadi (eski `_skip` ishlamasin)
        self.sync_device()

    def sync_device(self) -> bool:
        """Chiqishni joriy standart qurilmaga o'tkazish. False — ovoz qurilmasi yo'q."""
        try:
            dev = self.devices.defaultAudioOutput()
            if dev.isNull():
                return False
            if self.output.device() != dev:
                self.output.setDevice(dev)
                log.info("ovoz qurilmasi almashdi")
            return True
        except Exception:  # noqa: BLE001 — qurilma xatosi Yueni to'xtatmasin
            log.exception("ovoz qurilmasi tanlanmadi")
            return False

    def set_volume(self, volume: float) -> None:
        self.output.setVolume(max(0.0, min(1.0, volume)))

    def _no_device(self) -> bool:
        """Qurilma yo'q — gap o'tkazib yuboriladi (keyingi aylanishda `finished`)."""
        if self.sync_device():
            return False
        self._active = True
        token = self._token
        QTimer.singleShot(0, lambda: self._skip(token))
        return True

    def _skip(self, token: int) -> None:
        if self._active and token == self._token:
            self._active = False
            self.finished.emit()

    def play_file(self, path: Path) -> None:
        self._release()
        self._token += 1
        if self._no_device():
            return
        self._active = True
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.player.play()

    def play_bytes(self, data: bytes) -> None:
        self._release()
        self._token += 1
        if self._no_device():
            return
        buf = QBuffer(self)
        buf.setData(QByteArray(data))
        buf.open(QIODevice.OpenModeFlag.ReadOnly)
        self._buffer = buf
        self._active = True
        self.player.setSourceDevice(buf, QUrl("yue.mp3"))
        self.player.play()

    def stop(self) -> None:
        self._token += 1
        self._active = False
        self.player.stop()
        self._release()

    def _release(self) -> None:
        if self._buffer is not None:
            self.player.setSourceDevice(None)
            self._buffer.close()
            self._buffer.deleteLater()
            self._buffer = None

    def _on_status(self, status) -> None:
        if self._active and status in self._status_end:
            self._active = False
            self.finished.emit()

    def _on_error(self, *_args) -> None:
        log.info("ovoz o'ynatilmadi")
        if self._active:
            self._active = False
            self.finished.emit()
