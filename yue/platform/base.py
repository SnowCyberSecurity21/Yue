"""OS'ga bog'liq funksiyalar interfeysi. Windows — `windows.py`, boshqalar — `NullPlatform`.

Hamma koordinatalar shu yerda **fizik** piksellarda; mantiqiy piksellarga o'tkazish Qt
tomonida (`yue.pet.window`) qilinadi.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from yue.hotkey import Combo


@dataclass(frozen=True)
class NativeWindow:
    handle: int
    rect: tuple[int, int, int, int]  # left, top, right, bottom (fizik px)
    maximized: bool = False


@dataclass(frozen=True)
class Battery:
    percent: int
    plugged: bool


class Platform:
    """Standart (bo'sh) amalga oshirish: testlar va hali qo'llab-quvvatlanmagan OS uchun."""

    name = "null"

    def visible_windows(self) -> list[NativeWindow]:
        """Ko'rinib turgan oddiy oynalar, z-tartibda (eng yuqorisi birinchi). O'zimiznikisiz."""
        return []

    def fullscreen_busy(self) -> bool:
        """To'liq ekranli dastur (o'yin, video, taqdimot) ochiqmi."""
        return False

    def set_app_id(self, app_id: str) -> None:
        """Jarayonning ilova identifikatori (Windows: AppUserModelID)."""

    def idle_seconds(self) -> float:
        """Foydalanuvchi oxirgi marta sichqoncha/klaviaturaga tekkanidan beri o'tgan vaqt."""
        return 0.0

    def battery(self) -> Battery | None:
        return None

    def set_noactivate(self, handle: int) -> None:
        """Oyna bosilganda boshqa dasturdan fokusni olmasin."""

    def keep_topmost(self, handle: int) -> None:
        """Oynani boshqa "doim ustda" oynalar ustiga qaytarish."""

    def bring_to_front(self, handle: int) -> None:
        """Oynani oldinga chiqarib klaviatura fokusini berish.

        Faqat foydalanuvchi o'zi ochganda chaqiriladi (Yueni bosish, tezkor tugma, tray) —
        boshqa dasturda yozayotgan foydalanuvchidan fokus o'g'irlanmaydi.
        """

    # --- tezkor tugma, avtoyuklash, yorliq ---
    def register_combo(self, handle: int, hotkey_id: int, combo: Combo) -> bool:
        """Foydalanuvchi tanlagan birikma (`yue.hotkey.Combo`). False — band yoki imkonsiz."""
        return False

    def unregister_hotkey(self, handle: int, hotkey_id: int) -> None:
        pass

    def is_hotkey_message(self, message: int, hotkey_id: int) -> bool:
        """Qt native hodisasi (MSG manzili) bizning tezkor tugmamizmi."""
        return False

    def autostart_enabled(self) -> bool:
        return False

    def set_autostart(self, on: bool, command: list[str]) -> bool:
        return False

    def create_desktop_shortcut(
        self, name: str, target: str, args: list[str], icon: str, workdir: str
    ) -> bool:
        return False

    # --- DPAPI ---
    def protect(self, data: bytes) -> bytes:
        raise NotImplementedError("bu OS'da DPAPI yo'q")

    def unprotect(self, blob: bytes) -> bytes:
        raise NotImplementedError("bu OS'da DPAPI yo'q")


NullPlatform = Platform
