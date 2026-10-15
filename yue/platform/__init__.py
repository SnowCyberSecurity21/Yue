"""Platformani tanlash. Hozircha faqat Windows; Linux keyingi bosqichda (`linux.py`)."""

from __future__ import annotations

import sys
from functools import cache

from yue.platform.base import Battery, NativeWindow, NullPlatform, Platform

__all__ = ["Battery", "NativeWindow", "NullPlatform", "Platform", "get_platform"]


@cache
def get_platform() -> Platform:
    if sys.platform == "win32":
        from yue.platform.windows import WindowsPlatform

        return WindowsPlatform()
    return NullPlatform()
