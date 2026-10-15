"""Shifrlangan SQLite ombor: `%APPDATA%\\Yue\\yue.db` (WAL).

Jadvallar: messages, summary, facts, health, tasks, usage, queue (+ meta: sxema versiyasi).
Matn ustunlari (suhbat, xulosa, fakt, sog'liq, vazifa, navbat) AES-GCM bilan shifrlangan;
vaqt, muddat va hisoblagichlar ochiq (rejalashtirish uchun kerak, ular matn emas).
Bitta ulanish, qulf bilan — UI va AI oqimlaridan xavfsiz chaqiriladi.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yue.ai.providers.base import Usage
from yue.ai.usage import DayUsage
from yue.memory.crypto import Cipher, CryptoError

SCHEMA_VERSION = 1
MAX_FACTS = 120
MAX_HEALTH = 120

_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    text BLOB NOT NULL,
    summarized INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS summary (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    text BLOB NOT NULL,
    updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, text BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS health (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, text BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created REAL NOT NULL,
    text BLOB NOT NULL,
    due TEXT,                 -- "YYYY-MM-DD HH:MM" (bir martalik) yoki "HH:MM" (har kuni)
    repeat TEXT,              -- NULL yoki 'har_kuni'
    done INTEGER NOT NULL DEFAULT 0,
    done_ts REAL,
    fired TEXT                -- oxirgi eslatilgan muddat ("YYYY-MM-DD HH:MM")
);
CREATE TABLE IF NOT EXISTS usage (
    day TEXT NOT NULL, target TEXT NOT NULL,
    requests INTEGER NOT NULL DEFAULT 0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    cost REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (day, target)
);
CREATE TABLE IF NOT EXISTS queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT, created REAL NOT NULL, text BLOB NOT NULL
);
"""

MIGRATIONS: dict[int, str] = {1: _SCHEMA_V1}


@dataclass(frozen=True)
class Item:
    id: int
    ts: float
    text: str


@dataclass(frozen=True)
class TaskRow:
    id: int
    created: float
    text: str
    due: str | None
    repeat: str | None
    done: bool
    done_ts: float | None
    fired: str | None


class Store:
    def __init__(self, path: Path | str, cipher: Cipher) -> None:
        self.path = str(path)
        self.cipher = cipher
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.execute("PRAGMA secure_delete=ON")  # o'chirilgan sahifalar nol bilan yoziladi
        self._migrate()

    # --- infratuzilma ------------------------------------------------------------------------

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                yield self._db
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            self._db.execute("COMMIT")

    def _q(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._db.execute(sql, args).fetchall()

    def _migrate(self) -> None:
        with self._lock:
            self._db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
            row = self._db.execute("SELECT value FROM meta WHERE key='schema'").fetchone()
            current = int(row[0]) if row else 0
            if current > SCHEMA_VERSION:
                raise RuntimeError("ma'lumotlar bazasi yangiroq versiyadan")
            for v in range(current + 1, SCHEMA_VERSION + 1):
                with self._tx() as db:
                    for stmt in MIGRATIONS[v].split(";"):
                        if stmt.strip():
                            db.execute(stmt)
                    db.execute(
                        "INSERT INTO meta(key, value) VALUES('schema', ?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (str(v),),
                    )

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _enc(self, table: str, text: str) -> bytes:
        return self.cipher.encrypt(text, f"{table}:text")

    def _dec(self, table: str, blob: bytes) -> str:
        return self.cipher.decrypt(blob, f"{table}:text")

    def verify_key(self) -> bool:
        """Kalit bazadagi ma'lumotlarga mos keladimi (birinchi topilgan yozuv bo'yicha)."""
        for table in ("messages", "facts", "health", "tasks", "summary", "queue"):
            row = self._q(f"SELECT text FROM {table} LIMIT 1")  # noqa: S608 — jadval nomi kodda
            if row:
                try:
                    self.cipher.decrypt(row[0][0], f"{table}:text")
                except CryptoError:
                    return False
                return True
        return True

    # --- suhbat ------------------------------------------------------------------------------

    def add_message(self, role: str, text: str, ts: float | None = None) -> int:
        with self._tx() as db:
            cur = db.execute(
                "INSERT INTO messages(ts, role, text) VALUES(?,?,?)",
                (ts or time.time(), role, self._enc("messages", text)),
            )
            return int(cur.lastrowid or 0)

    def recent_messages(self, limit: int = 10) -> list[tuple[str, str]]:
        """Oxirgi xabarlar (eskidan yangiga)."""
        rows = self._q("SELECT role, text FROM messages ORDER BY id DESC LIMIT ?", (limit,))
        return [(r[0], self._dec("messages", r[1])) for r in reversed(rows)]

    def unsummarized(self, keep_recent: int = 10) -> list[tuple[int, str, str]]:
        """Xulosaga tayyor xabarlar (oxirgi `keep_recent` tasidan tashqari)."""
        rows = self._q(
            "SELECT id, role, text FROM messages WHERE summarized=0 ORDER BY id "
            "LIMIT max(0, (SELECT count(*) FROM messages WHERE summarized=0) - ?)",
            (keep_recent,),
        )
        return [(r[0], r[1], self._dec("messages", r[2])) for r in rows]

    def count_unsummarized(self) -> int:
        return int(self._q("SELECT count(*) FROM messages WHERE summarized=0")[0][0])

    def mark_summarized(self, ids: list[int]) -> None:
        """Xulosaga kirgan xabarlar o'chiriladi (xotirada faqat xulosa qoladi)."""
        if not ids:
            return
        with self._tx() as db:
            db.executemany("DELETE FROM messages WHERE id=?", [(i,) for i in ids])

    def get_summary(self) -> str:
        row = self._q("SELECT text FROM summary WHERE id=1")
        return self._dec("summary", row[0][0]) if row else ""

    def set_summary(self, text: str) -> None:
        with self._tx() as db:
            db.execute(
                "INSERT INTO summary(id, text, updated) VALUES(1, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET text=excluded.text, updated=excluded.updated",
                (self._enc("summary", text), time.time()),
            )

    # --- faktlar va sog'liq daftari ------------------------------------------------------

    def _add_note(self, table: str, text: str, cap: int) -> int | None:
        text = " ".join(text.split())
        if not text:
            return None
        existing = self._list_notes(table)
        if any(e.text.casefold() == text.casefold() for e in existing):
            return None
        with self._tx() as db:
            cur = db.execute(
                f"INSERT INTO {table}(ts, text) VALUES(?, ?)",  # noqa: S608
                (time.time(), self._enc(table, text)),
            )
            over = len(existing) + 1 - cap
            if over > 0:
                db.execute(
                    f"DELETE FROM {table} WHERE id IN (SELECT id FROM {table} ORDER BY id LIMIT ?)",  # noqa: S608
                    (over,),
                )
            return int(cur.lastrowid or 0)

    def _list_notes(self, table: str) -> list[Item]:
        rows = self._q(f"SELECT id, ts, text FROM {table} ORDER BY id")  # noqa: S608
        return [Item(r[0], r[1], self._dec(table, r[2])) for r in rows]

    def add_fact(self, text: str) -> int | None:
        return self._add_note("facts", text, MAX_FACTS)

    def facts(self) -> list[Item]:
        return self._list_notes("facts")

    def delete_fact(self, fid: int) -> None:
        with self._tx() as db:
            db.execute("DELETE FROM facts WHERE id=?", (fid,))

    def add_health(self, text: str) -> int | None:
        return self._add_note("health", text, MAX_HEALTH)

    def health(self) -> list[Item]:
        return self._list_notes("health")

    def delete_health(self, hid: int) -> None:
        with self._tx() as db:
            db.execute("DELETE FROM health WHERE id=?", (hid,))

    # --- vazifalar -------------------------------------------------------------------------

    def _task(self, r: sqlite3.Row | tuple) -> TaskRow:
        return TaskRow(
            id=r[0],
            created=r[1],
            text=self._dec("tasks", r[2]),
            due=r[3],
            repeat=r[4],
            done=bool(r[5]),
            done_ts=r[6],
            fired=r[7],
        )

    _TASK_COLS = "id, created, text, due, repeat, done, done_ts, fired"

    def add_task(self, text: str, due: str | None = None, repeat: str | None = None) -> int:
        with self._tx() as db:
            cur = db.execute(
                "INSERT INTO tasks(created, text, due, repeat) VALUES(?,?,?,?)",
                (time.time(), self._enc("tasks", " ".join(text.split())), due, repeat),
            )
            return int(cur.lastrowid or 0)

    def tasks(self, include_done: bool = False) -> list[TaskRow]:
        where = "" if include_done else "WHERE done=0"
        rows = self._q(f"SELECT {self._TASK_COLS} FROM tasks {where} ORDER BY id")  # noqa: S608
        return [self._task(r) for r in rows]

    def task(self, tid: int) -> TaskRow | None:
        rows = self._q(f"SELECT {self._TASK_COLS} FROM tasks WHERE id=?", (tid,))  # noqa: S608
        return self._task(rows[0]) if rows else None

    def complete_task(self, tid: int) -> bool:
        with self._tx() as db:
            cur = db.execute(
                "UPDATE tasks SET done=1, done_ts=? WHERE id=? AND done=0", (time.time(), tid)
            )
            return cur.rowcount > 0

    def delete_task(self, tid: int) -> bool:
        with self._tx() as db:
            return db.execute("DELETE FROM tasks WHERE id=?", (tid,)).rowcount > 0

    def set_task_fired(self, tid: int, fired: str) -> None:
        with self._tx() as db:
            db.execute("UPDATE tasks SET fired=? WHERE id=?", (fired, tid))

    def prune_done_tasks(self, older_than: float) -> None:
        with self._tx() as db:
            db.execute("DELETE FROM tasks WHERE done=1 AND done_ts < ?", (older_than,))

    # --- xarajat va navbat (AI qatlami interfeyslari) -----------------------------------------

    def usage_add(self, day: str, target: str, u: Usage, cost: float) -> None:
        with self._tx() as db:
            db.execute(
                "INSERT INTO usage(day, target, requests, input_tokens, output_tokens, "
                "cache_read_tokens, cost) VALUES(?,?,1,?,?,?,?) "
                "ON CONFLICT(day, target) DO UPDATE SET requests=requests+1, "
                "input_tokens=input_tokens+excluded.input_tokens, "
                "output_tokens=output_tokens+excluded.output_tokens, "
                "cache_read_tokens=cache_read_tokens+excluded.cache_read_tokens, "
                "cost=cost+excluded.cost",
                (day, target, u.input_tokens, u.output_tokens, u.cache_read_tokens, cost),
            )

    def usage_day(self, day: str) -> DayUsage | None:
        rows = self._q(
            "SELECT target, requests, input_tokens, output_tokens, cache_read_tokens, cost "
            "FROM usage WHERE day=?",
            (day,),
        )
        if not rows:
            return None
        d = DayUsage(day)
        for t, req, inp, out, cr, cost in rows:
            d.requests += req
            d.input_tokens += inp
            d.output_tokens += out
            d.cache_read_tokens += cr
            d.cost += cost
            d.by_target[t] = req
        return d

    def queue_add(self, text: str, created: float) -> int:
        with self._tx() as db:
            cur = db.execute(
                "INSERT INTO queue(created, text) VALUES(?, ?)", (created, self._enc("queue", text))
            )
            return int(cur.lastrowid or 0)

    def queue_all(self) -> list[tuple[int, str, float]]:
        rows = self._q("SELECT id, text, created FROM queue ORDER BY id")
        return [(r[0], self._dec("queue", r[1]), r[2]) for r in rows]

    def queue_remove(self, qid: int) -> None:
        with self._tx() as db:
            db.execute("DELETE FROM queue WHERE id=?", (qid,))

    # --- butun xotira ------------------------------------------------------------------------

    def clear_memory(self) -> None:
        """Suhbat, xulosa, faktlar va sog'liq daftari o'chiriladi (vazifalar qoladi)."""
        with self._tx() as db:
            for table in ("messages", "summary", "facts", "health", "queue"):
                db.execute(f"DELETE FROM {table}")  # noqa: S608
        with self._lock:
            self._db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self._db.execute("VACUUM")

    def export(self) -> dict[str, Any]:
        """Shifrlanmagan eksport (foydalanuvchi ogohlantirilgandan keyin)."""
        return {
            "summary": self.get_summary(),
            "facts": [f.text for f in self.facts()],
            "health": [h.text for h in self.health()],
            "messages": [{"role": r, "text": t} for r, t in self.recent_messages(10_000)],
            "tasks": [
                {"id": t.id, "text": t.text, "due": t.due, "repeat": t.repeat, "done": t.done}
                for t in self.tasks(include_done=True)
            ],
        }

    def export_json(self) -> str:
        return json.dumps(self.export(), ensure_ascii=False, indent=2)
