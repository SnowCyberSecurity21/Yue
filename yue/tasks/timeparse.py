"""Vazifa muddatlari: o'qish, keyingi takror, o'zbekcha ko'rinish va qo'lda kiritilgan vaqt.

Muddat formatlari (bazada ochiq matn):
- bir martalik: "YYYY-MM-DD HH:MM"
- har kunlik: "HH:MM" (+ repeat="har_kuni")
"""

from __future__ import annotations

import datetime as dt
import re

MONTHS_UZ = (
    "yanvar", "fevral", "mart", "aprel", "may", "iyun",
    "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
)  # fmt: skip
DAILY = "har_kuni"


def parse_due(due: str | None) -> dt.datetime | None:
    if not due:
        return None
    try:
        return dt.datetime.strptime(due.strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def parse_hhmm(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    m = re.fullmatch(r"\s*(\d{1,2})[:.](\d{2})\s*", value)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if 0 <= h <= 23 and 0 <= mi <= 59:
        return h, mi
    return None


def occurrence_on(day: dt.date, hhmm: str) -> dt.datetime | None:
    hm = parse_hhmm(hhmm)
    if hm is None:
        return None
    return dt.datetime.combine(day, dt.time(*hm))


def next_daily(hhmm: str, now: dt.datetime) -> dt.datetime | None:
    """Har kunlik vazifaning keyingi vaqti (bugun o'tmagan bo'lsa — bugun)."""
    today = occurrence_on(now.date(), hhmm)
    if today is None:
        return None
    return today if today > now else today + dt.timedelta(days=1)


def fmt_due(due: dt.datetime) -> str:
    return due.strftime("%Y-%m-%d %H:%M")


def describe_due(due: str | None, repeat: str | None, now: dt.datetime) -> str:
    """Foydalanuvchiga: "bugun 15:00", "ertaga 09:00", "14-oktabr 09:00", "har kuni 08:00"."""
    if repeat == DAILY:
        hm = parse_hhmm(due)
        return f"har kuni {hm[0]:02d}:{hm[1]:02d}" if hm else "har kuni"
    when = parse_due(due)
    if when is None:
        return ""
    days = (when.date() - now.date()).days
    hm = f"{when:%H:%M}"
    if days == 0:
        return f"bugun {hm}"
    if days == 1:
        return f"ertaga {hm}"
    if days == -1:
        return f"kecha {hm}"
    year = f" {when.year}-yil" if when.year != now.year else ""
    return f"{when.day}-{MONTHS_UZ[when.month - 1]}{year} {hm}"


def is_overdue(due: str | None, repeat: str | None, now: dt.datetime) -> bool:
    if repeat == DAILY:
        return False
    when = parse_due(due)
    return when is not None and when < now


_REL_RE = re.compile(r"(\d+)\s*(daqiqa|minut|min|soat)\s*(dan|da)?\s*(keyin|so'ng)?", re.I)


def parse_user_time(text: str, now: dt.datetime) -> tuple[str | None, str | None] | None:
    """Qo'lda kiritilgan vaqt → (due, repeat). Bo'sh matn → (None, None) (muddatsiz).

    Qabul qilinadi: "15:30", "2026-10-14 09:00", "bugun 18:00", "ertaga 9:00", "indinga 10:00",
    "har kuni 08:00", "30 daqiqadan keyin", "2 soatdan keyin". Tushunilmasa — None.
    """
    s = " ".join(text.lower().replace("ʻ", "'").replace("’", "'").split())
    if not s:
        return None, None
    if parse_due(s):
        return s, None
    m = re.search(r"(\d{1,2}[:.]\d{2})", s)
    hm = parse_hhmm(m.group(1)) if m else None
    if s.startswith(("har kuni", "harkuni", "kunda")):
        return (f"{hm[0]:02d}:{hm[1]:02d}", DAILY) if hm else None
    rel = _REL_RE.search(s)
    if rel and not hm:
        n = int(rel.group(1))
        delta = (
            dt.timedelta(hours=n) if rel.group(2).startswith("soat") else dt.timedelta(minutes=n)
        )
        due = now + delta
        if due.second or due.microsecond:  # "1 daqiqadan keyin" — kamida 1 daqiqa (yuqoriga)
            due = due.replace(second=0, microsecond=0) + dt.timedelta(minutes=1)
        return fmt_due(due), None
    if hm is None:
        return None
    day = now.date()
    if "indinga" in s:
        day += dt.timedelta(days=2)
    elif "ertaga" in s:
        day += dt.timedelta(days=1)
    when = dt.datetime.combine(day, dt.time(*hm))
    if when <= now and "bugun" not in s and "ertaga" not in s and "indinga" not in s:
        when += dt.timedelta(days=1)  # "15:30" o'tib ketgan bo'lsa — ertaga
    return fmt_due(when), None
