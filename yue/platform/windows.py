"""Windows: oynalar, to'liq ekran, bo'sh vaqt, batareya, DPAPI (ctypes orqali).

Maxfiylik: oyna sarlavhalari o'qilmaydi va logga yozilmaydi — faqat sarlavha *uzunligi*
(oddiy dastur oynasini xizmat oynalaridan ajratish uchun) tekshiriladi.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import winreg
from ctypes import wintypes

from yue.hotkey import Combo
from yue.platform.base import Battery, NativeWindow, Platform

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi")
shell32 = ctypes.WinDLL("shell32")
crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOACTIVATE = 0x08000000
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14
HWND_TOPMOST = wintypes.HWND(-1)
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010
MONITOR_DEFAULTTONEAREST = 2
WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x0001, 0x0002, 0x4000
MOD_SHIFT, MOD_WIN = 0x0004, 0x0008
VK_F1 = 0x70
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "Yue"
CREATE_NO_WINDOW = 0x08000000
CRYPTPROTECT_UI_FORBIDDEN = 0x1

# Ustida yurib bo'lmaydigan xizmat oynalari
SKIP_CLASSES = frozenset(
    {
        "Shell_TrayWnd",
        "Shell_SecondaryTrayWnd",
        "Progman",
        "WorkerW",
        "NotifyIconOverflowWindow",
        "TopLevelWindowForOverflowXamlIsland",
        "XamlExplorerHostIslandWindow",
        "Windows.UI.Core.CoreWindow",
        "ApplicationFrameWindow_Hidden",
        "Xaml_WindowedPopupClass",
        "tooltips_class32",
        "#32768",  # menyu
    }
)
MIN_W, MIN_H = 80, 40

LONG_PTR = ctypes.c_ssize_t
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsZoomed.argtypes = [wintypes.HWND]
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = LONG_PTR
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, LONG_PTR]
user32.SetWindowLongPtrW.restype = LONG_PTR
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
user32.MonitorFromWindow.restype = wintypes.HANDLE
user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
dwmapi.DwmGetWindowAttribute.argtypes = [
    wintypes.HWND,
    wintypes.DWORD,
    ctypes.c_void_p,
    wintypes.DWORD,
]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_MONITORINFO)]


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


class _SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_ubyte),
        ("BatteryFlag", ctypes.c_ubyte),
        ("BatteryLifePercent", ctypes.c_ubyte),
        ("SystemStatusFlag", ctypes.c_ubyte),
        ("BatteryLifeTime", wintypes.DWORD),
        ("BatteryFullLifeTime", wintypes.DWORD),
    ]


class _BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


crypt32.CryptProtectData.argtypes = [
    ctypes.POINTER(_BLOB),
    wintypes.LPCWSTR,
    ctypes.POINTER(_BLOB),
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(_BLOB),
]
crypt32.CryptUnprotectData.argtypes = [
    ctypes.POINTER(_BLOB),
    ctypes.c_void_p,
    ctypes.POINTER(_BLOB),
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(_BLOB),
]
kernel32.LocalFree.argtypes = [ctypes.c_void_p]
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
shell32.SHGetFolderPathW.argtypes = [
    wintypes.HWND,
    ctypes.c_int,
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
]
CSIDL_DESKTOPDIRECTORY = 0x10
kernel32.GetTickCount.restype = wintypes.DWORD
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.SetFocus.argtypes = [wintypes.HWND]


def _class_name(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(128)
    user32.GetClassNameW(hwnd, buf, 128)
    return buf.value


def _frame_rect(hwnd: int) -> tuple[int, int, int, int]:
    """Ko'rinadigan chegaralar (DWM soyasiz); bo'lmasa GetWindowRect."""
    r = wintypes.RECT()
    if dwmapi.DwmGetWindowAttribute(
        hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(r), ctypes.sizeof(r)
    ):
        user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def _cloaked(hwnd: int) -> bool:
    v = ctypes.c_int(0)
    dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(v), ctypes.sizeof(v))
    return v.value != 0


def _pid_of(hwnd: int) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _powershell() -> str:
    """PowerShell'ning to'liq tizim yo'li (PATH orqali qidirilmaydi)."""
    root = os.environ.get("SYSTEMROOT", r"C:\Windows")
    return os.path.join(root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")


def _blob(data: bytes) -> tuple[_BLOB, ctypes.Array]:
    buf = ctypes.create_string_buffer(data, len(data))
    return _BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf


class WindowsPlatform(Platform):
    name = "windows"

    def __init__(self) -> None:
        self._pid = os.getpid()

    # --- oynalar ----------------------------------------------------------------------------

    def visible_windows(self) -> list[NativeWindow]:
        out: list[NativeWindow] = []

        def cb(hwnd: int, _lparam: int) -> bool:
            try:
                if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
                    return True
                ex = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
                if ex & (WS_EX_TOOLWINDOW | WS_EX_TRANSPARENT):
                    return True
                if user32.GetWindowTextLengthW(hwnd) == 0:
                    return True
                if _pid_of(hwnd) == self._pid or _class_name(hwnd) in SKIP_CLASSES:
                    return True
                if _cloaked(hwnd):
                    return True
                rect = _frame_rect(hwnd)
                if rect[2] - rect[0] < MIN_W or rect[3] - rect[1] < MIN_H:
                    return True
                out.append(NativeWindow(int(hwnd), rect, bool(user32.IsZoomed(hwnd))))
            except OSError:
                pass
            return True

        user32.EnumWindows(EnumWindowsProc(cb), 0)
        return out

    def _covers_monitor(self, hwnd: int) -> bool:
        if not hwnd or _pid_of(hwnd) == self._pid or _class_name(hwnd) in SKIP_CLASSES:
            return False
        if user32.IsIconic(hwnd):
            return False
        r = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        mon = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        mi = _MONITORINFO()
        mi.cbSize = ctypes.sizeof(mi)
        if not user32.GetMonitorInfoW(mon, ctypes.byref(mi)):
            return False
        m = mi.rcMonitor
        return r.left <= m.left and r.top <= m.top and r.right >= m.right and r.bottom >= m.bottom

    def fullscreen_busy(self) -> bool:
        try:
            state = ctypes.c_int(0)
            if shell32.SHQueryUserNotificationState(ctypes.byref(state)) == 0:
                # 2 BUSY, 3 D3D to'liq ekran, 4 taqdimot rejimi
                if state.value in (2, 3, 4):
                    return True
            return self._covers_monitor(user32.GetForegroundWindow())
        except OSError:
            return False

    def set_noactivate(self, handle: int) -> None:
        ex = user32.GetWindowLongPtrW(handle, GWL_EXSTYLE)
        user32.SetWindowLongPtrW(handle, GWL_EXSTYLE, ex | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)

    def keep_topmost(self, handle: int) -> None:
        user32.SetWindowPos(
            handle, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
        )

    def bring_to_front(self, handle: int) -> None:
        # Windows fon jarayoniga SetForegroundWindow'ni rad etishi mumkin. Oldingi oynaning
        # kiritish oqimiga vaqtincha ulanib (AttachThreadInput) fokus beriladi.
        fg = user32.GetForegroundWindow()
        if fg == handle:
            return
        me = kernel32.GetCurrentThreadId()
        other = user32.GetWindowThreadProcessId(fg, None) if fg else 0
        attached = bool(other and other != me and user32.AttachThreadInput(me, other, True))
        try:
            user32.BringWindowToTop(handle)
            user32.SetForegroundWindow(handle)
            user32.SetFocus(handle)
        finally:
            if attached:
                user32.AttachThreadInput(me, other, False)

    def set_app_id(self, app_id: str) -> None:
        # Vazifalar paneli va bildirishnomalar Nora bilan aralashmasin
        shell32.SetCurrentProcessExplicitAppUserModelID(ctypes.c_wchar_p(app_id))

    # --- foydalanuvchi va quvvat ------------------------------------------------------------

    def idle_seconds(self) -> float:
        info = _LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        return ((kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000.0

    def battery(self) -> Battery | None:
        st = _SYSTEM_POWER_STATUS()
        if not kernel32.GetSystemPowerStatus(ctypes.byref(st)):
            return None
        if st.BatteryFlag in (128, 255) or st.BatteryLifePercent == 255:
            return None
        return Battery(percent=int(st.BatteryLifePercent), plugged=st.ACLineStatus == 1)

    # --- tezkor tugma ------------------------------------------------------------------------

    def register_combo(self, handle: int, hotkey_id: int, combo: Combo) -> bool:
        flags = {"ctrl": MOD_CONTROL, "alt": MOD_ALT, "shift": MOD_SHIFT, "win": MOD_WIN}
        mods = MOD_NOREPEAT
        for m in combo.mods:
            mods |= flags[m]
        # A–Z, 0–9: virtual kod = ASCII; F1–F24 ketma-ket
        vk = VK_F1 + int(combo.key[1:]) - 1 if len(combo.key) > 1 else ord(combo.key)
        return bool(user32.RegisterHotKey(handle, hotkey_id, mods, vk))

    def unregister_hotkey(self, handle: int, hotkey_id: int) -> None:
        user32.UnregisterHotKey(handle, hotkey_id)

    def is_hotkey_message(self, message: int, hotkey_id: int) -> bool:
        try:
            msg = wintypes.MSG.from_address(message)
        except (ValueError, TypeError):
            return False
        return msg.message == WM_HOTKEY and msg.wParam == hotkey_id

    # --- avtoyuklash va yorliq ---------------------------------------------------------------

    def autostart_enabled(self) -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
                winreg.QueryValueEx(k, RUN_NAME)
                return True
        except OSError:
            return False

    def set_autostart(self, on: bool, command: list[str]) -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
                if on:
                    value = subprocess.list2cmdline(command)
                    winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, value)
                else:
                    try:
                        winreg.DeleteValue(k, RUN_NAME)
                    except FileNotFoundError:
                        pass
            return True
        except OSError:
            return False

    def create_desktop_shortcut(
        self, name: str, target: str, args: list[str], icon: str, workdir: str
    ) -> bool:
        buf = ctypes.create_unicode_buffer(260)
        if shell32.SHGetFolderPathW(None, CSIDL_DESKTOPDIRECTORY, None, 0, buf) != 0:
            return False
        lnk = os.path.join(buf.value, f"{name}.lnk")

        def q(s: str) -> str:  # PowerShell bitta qo'shtirnoqli satr
            return "'" + s.replace("'", "''") + "'"

        script = (
            "$s=(New-Object -ComObject WScript.Shell).CreateShortcut("
            + q(lnk)
            + ");$s.TargetPath="
            + q(target)
            + ";$s.Arguments="
            + q(subprocess.list2cmdline(args))
            + ";$s.WorkingDirectory="
            + q(workdir)
            + ";$s.IconLocation="
            + q(icon + ",0")
            + ";$s.Save()"
        )
        try:
            res = subprocess.run(  # noqa: S603 — ro'yxat argumentlari, shell yo'q
                [_powershell(), "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True,
                timeout=20,
                creationflags=CREATE_NO_WINDOW,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return res.returncode == 0 and os.path.exists(lnk)

    # --- DPAPI ------------------------------------------------------------------------------

    def protect(self, data: bytes) -> bytes:
        """Joriy Windows foydalanuvchisi uchun shifrlash (CryptProtectData)."""
        src, _keep = _blob(data)
        out = _BLOB()
        if not crypt32.CryptProtectData(
            ctypes.byref(src), None, None, None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out)
        ):
            raise OSError(ctypes.get_last_error(), "CryptProtectData")
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            kernel32.LocalFree(ctypes.cast(out.pbData, ctypes.c_void_p))

    def unprotect(self, blob: bytes) -> bytes:
        src, _keep = _blob(blob)
        out = _BLOB()
        if not crypt32.CryptUnprotectData(
            ctypes.byref(src), None, None, None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out)
        ):
            raise OSError(ctypes.get_last_error(), "CryptUnprotectData")
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            kernel32.LocalFree(ctypes.cast(out.pbData, ctypes.c_void_p))
