"""Tanaffus va batareya eslatmalari (Qt'siz mantiq; `app.py` davriy chaqiradi)."""

from __future__ import annotations

from dataclasses import dataclass

from yue.platform import Battery

AWAY_RESET = 5 * 60  # shuncha harakatsizlik — tanaffus qilindi deb hisoblanadi


@dataclass
class BreakTracker:
    """Uzluksiz faol vaqt (GetLastInputInfo) standart 90 daqiqadan oshsa — eslatma."""

    limit_min: float = 90.0
    active_since: float | None = None

    def update(self, now: float, idle_seconds: float) -> float | None:
        """Eslatish kerak bo'lsa — faol bo'lgan soatlar soni, aks holda None."""
        if idle_seconds >= AWAY_RESET:
            self.active_since = None
            return None
        if self.active_since is None:
            self.active_since = now - idle_seconds
            return None
        active = now - self.active_since
        if self.limit_min > 0 and active >= self.limit_min * 60:
            self.active_since = now  # keyingi eslatma yana `limit` dan keyin
            return active / 3600
        return None


@dataclass
class BatteryWatcher:
    low: int = 20
    critical: int = 10
    _plugged: bool | None = None
    _warned_low: bool = False
    _warned_critical: bool = False
    _warned_full: bool = False

    def update(self, b: Battery | None) -> str | None:
        """Aytish kerak bo'lgan hodisa: low / critical / plug / unplug / full yoki None."""
        if b is None:
            return None
        event: str | None = None
        if self._plugged is not None and b.plugged != self._plugged:
            event = "plug" if b.plugged else "unplug"
        self._plugged = b.plugged
        if b.plugged:
            self._warned_low = self._warned_critical = False
            if b.percent >= 100 and not self._warned_full:
                self._warned_full = True
                return event or "full"
            if b.percent < 95:
                self._warned_full = False
            return event
        self._warned_full = False
        if b.percent <= self.critical and not self._warned_critical:
            self._warned_critical = self._warned_low = True
            return "critical"
        if b.percent <= self.low and not self._warned_low:
            self._warned_low = True
            return "low"
        return event
