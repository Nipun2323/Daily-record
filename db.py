"""Data layer for Daily Record.

Two backends, same code:
  * Postgres (e.g. Supabase) when DATABASE_URL is set in env or st.secrets.
    Use this for a shared deployment: data survives restarts and redeploys.
  * SQLite in ./data otherwise, for local development.

Photos are stored in the database itself (as JPEG bytes), so a deployment
needs exactly one external service.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import os
import secrets
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageOps

try:  # iPhone photos (HEIC), optional dependency
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass

ROOT = Path(__file__).parent
DATA_DIR = Path(os.environ.get("DAILY_RECORD_DATA", ROOT / "data"))
SQLITE_PATH = DATA_DIR / "daily_record.db"

PINCH_COOLDOWN_MIN = 5
MAX_PHOTO_PX = 1280
THUMB_PX = 420


def _setting(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    try:
        import streamlit as st

        return st.secrets.get(name)
    except Exception:
        return None


DATABASE_URL = _setting("DATABASE_URL")
IS_PG = bool(DATABASE_URL)


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(_setting("APP_TIMEZONE") or "UTC")
    except Exception:
        return ZoneInfo("UTC")


def now() -> dt.datetime:
    return dt.datetime.now(_tz())


def today() -> dt.date:
    return now().date()


# --------------------------------------------------------------------------- #
# Connection
# --------------------------------------------------------------------------- #
_pool = None
_pool_lock = threading.Lock()


def _pg_pool():
    global _pool
    with _pool_lock:
        if _pool is None:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool

            _pool = ConnectionPool(
                DATABASE_URL,
                min_size=1,
                max_size=6,
                # prepare_threshold=None keeps it compatible with PgBouncer poolers.
                kwargs={"row_factory": dict_row, "prepare_threshold": None},
                check=ConnectionPool.check_connection,
                open=True,
            )
            import atexit

            atexit.register(_pool.close)
        return _pool


class _Conn:
    """Minimal wrapper so the rest of the module writes '?' placeholders
    and gets dict-style rows on both backends."""

    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql: str, params: tuple = ()):
        if IS_PG:
            sql = sql.replace("?", "%s")
        return self.raw.execute(sql, params)


@contextmanager
def conn():
    if IS_PG:
        with _pg_pool().connection() as raw:  # commits on success, rolls back on error
            yield _Conn(raw)
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    raw = sqlite3.connect(SQLITE_PATH, timeout=15)
    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA foreign_keys = ON")
    try:
        yield _Conn(raw)
        raw.commit()
    finally:
        raw.close()


def _is_unique_violation(e: Exception) -> bool:
    return isinstance(e, sqlite3.IntegrityError) or type(e).__name__ in {"UniqueViolation", "IntegrityError"}


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #
def _schema() -> list[str]:
    pk = "SERIAL PRIMARY KEY" if IS_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
    blob = "BYTEA" if IS_PG else "BLOB"
    return [
        f"""CREATE TABLE IF NOT EXISTS users (
            id          {pk},
            name        TEXT NOT NULL,
            emoji       TEXT NOT NULL DEFAULT '🔥',
            color       TEXT NOT NULL DEFAULT '#ff6b1a',
            pin_salt    TEXT NOT NULL,
            pin_hash    TEXT NOT NULL,
            created_at  TEXT NOT NULL)""",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_name ON users (lower(name))",
        """CREATE TABLE IF NOT EXISTS sessions (
            token       TEXT PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at  TEXT NOT NULL)""",
        f"""CREATE TABLE IF NOT EXISTS tasks (
            id           {pk},
            user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title        TEXT NOT NULL,
            emoji        TEXT NOT NULL DEFAULT '✦',
            created_on   TEXT NOT NULL,
            archived_on  TEXT)""",
        f"""CREATE TABLE IF NOT EXISTS checkins (
            id          {pk},
            task_id     INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            day         TEXT NOT NULL,
            photo       TEXT NOT NULL,
            thumb       TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            UNIQUE(task_id, day))""",
        f"""CREATE TABLE IF NOT EXISTS pinches (
            id            {pk},
            from_user     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            to_user       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            task_id       INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
            message       TEXT,
            status        TEXT NOT NULL DEFAULT 'pending',
            photo         TEXT,
            thumb         TEXT,
            created_at    TEXT NOT NULL,
            responded_at  TEXT)""",
        f"""CREATE TABLE IF NOT EXISTS photos (
            name        TEXT PRIMARY KEY,
            data        {blob} NOT NULL,
            created_at  TEXT NOT NULL)""",
        "CREATE INDEX IF NOT EXISTS idx_checkins_user_day ON checkins(user_id, day)",
        "CREATE INDEX IF NOT EXISTS idx_pinches_to ON pinches(to_user, status)",
    ]


_initialised = False


def init_db() -> None:
    global _initialised
    if _initialised:
        return
    with conn() as c:
        if not IS_PG:
            c.execute("PRAGMA journal_mode = WAL")
        for stmt in _schema():
            c.execute(stmt)
    _initialised = True


# --------------------------------------------------------------------------- #
# Users & sessions
# --------------------------------------------------------------------------- #
def _hash_pin(pin: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt.encode(), 120_000).hex()


def create_user(name: str, pin: str, emoji: str, color: str) -> int:
    name = name.strip()
    if not name:
        raise ValueError("Name can't be empty.")
    if not (pin.isdigit() and 4 <= len(pin) <= 8):
        raise ValueError("PIN must be 4–8 digits.")
    salt = secrets.token_hex(8)
    try:
        with conn() as c:
            row = c.execute(
                "INSERT INTO users(name, emoji, color, pin_salt, pin_hash, created_at)"
                " VALUES (?,?,?,?,?,?) RETURNING id",
                (name, emoji, color, salt, _hash_pin(pin, salt), now().isoformat()),
            ).fetchone()
    except Exception as e:
        if _is_unique_violation(e):
            raise ValueError(f"“{name}” is taken. Pick another name.") from None
        raise
    return row["id"]


def list_users() -> list:
    with conn() as c:
        return c.execute("SELECT * FROM users ORDER BY created_at").fetchall()


def get_user(user_id: int):
    with conn() as c:
        return c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()


def verify_pin(user_id: int, pin: str) -> bool:
    u = get_user(user_id)
    return bool(u) and secrets.compare_digest(_hash_pin(pin, u["pin_salt"]), u["pin_hash"])


def start_session(user_id: int) -> str:
    token = secrets.token_urlsafe(24)
    with conn() as c:
        c.execute(
            "INSERT INTO sessions(token, user_id, created_at) VALUES (?,?,?)",
            (token, user_id, now().isoformat()),
        )
    return token


def user_for_session(token: str | None) -> int | None:
    if not token:
        return None
    with conn() as c:
        row = c.execute("SELECT user_id FROM sessions WHERE token=?", (token,)).fetchone()
    return row["user_id"] if row else None


def end_session(token: str | None) -> None:
    if token:
        with conn() as c:
            c.execute("DELETE FROM sessions WHERE token=?", (token,))


# --------------------------------------------------------------------------- #
# Tasks
# --------------------------------------------------------------------------- #
def add_task(user_id: int, title: str, emoji: str = "✦") -> None:
    title = title.strip()
    if not title:
        raise ValueError("Give the task a name.")
    with conn() as c:
        c.execute(
            "INSERT INTO tasks(user_id, title, emoji, created_on) VALUES (?,?,?,?)",
            (user_id, title, emoji or "✦", today().isoformat()),
        )


def archive_task(task_id: int, user_id: int) -> None:
    """Stop a task counting from tomorrow on (today's proof still stands).

    A task created today with no proof is deleted outright.
    """
    t = today()
    with conn() as c:
        row = c.execute(
            "SELECT created_on FROM tasks WHERE id=? AND user_id=?", (task_id, user_id)
        ).fetchone()
        if not row:
            return
        done_today = c.execute(
            "SELECT 1 FROM checkins WHERE task_id=? AND day=?", (task_id, t.isoformat())
        ).fetchone()
        if row["created_on"] == t.isoformat() and not done_today:
            c.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        else:
            cutoff = t + dt.timedelta(days=1) if done_today else t
            c.execute("UPDATE tasks SET archived_on=? WHERE id=?", (cutoff.isoformat(), task_id))


def tasks_on(user_id: int, day: dt.date | None = None) -> list:
    d = (day or today()).isoformat()
    with conn() as c:
        return c.execute(
            "SELECT * FROM tasks WHERE user_id=? AND created_on<=?"
            " AND (archived_on IS NULL OR archived_on>?) ORDER BY id",
            (user_id, d, d),
        ).fetchall()


def active_tasks(user_id: int) -> list:
    """Tasks not yet removed (what the Tasks page manages)."""
    with conn() as c:
        return c.execute(
            "SELECT * FROM tasks WHERE user_id=? AND archived_on IS NULL ORDER BY id", (user_id,)
        ).fetchall()


# --------------------------------------------------------------------------- #
# Photos
# --------------------------------------------------------------------------- #
def _encode(img: Image.Image, quality: int) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def _save_photo(data: bytes, prefix: str) -> tuple[str, str]:
    """Normalise orientation, downscale, store full + thumbnail JPEGs."""
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception as e:
        raise ValueError("That file isn't a readable image.") from e
    big = img.copy()
    big.thumbnail((MAX_PHOTO_PX, MAX_PHOTO_PX))
    stem = f"{prefix}_{uuid.uuid4().hex[:12]}"
    full, thumb = f"{stem}.jpg", f"{stem}_t.jpg"
    with conn() as c:
        for name, blob in ((full, _encode(big, 82)), (thumb, _encode(ImageOps.fit(img, (THUMB_PX, THUMB_PX)), 78))):
            c.execute(
                "INSERT INTO photos(name, data, created_at) VALUES (?,?,?)",
                (name, blob, now().isoformat()),
            )
    return full, thumb


@lru_cache(maxsize=256)
def photo_bytes(name: str) -> bytes:
    """Photo names are unique and never rewritten, so caching is safe."""
    with conn() as c:
        row = c.execute("SELECT data FROM photos WHERE name=?", (name,)).fetchone()
    return bytes(row["data"]) if row else b""


def _delete_photos(c, *names: str) -> None:
    for n in names:
        if n:
            c.execute("DELETE FROM photos WHERE name=?", (n,))


# --------------------------------------------------------------------------- #
# Check-ins
# --------------------------------------------------------------------------- #
def check_in(user_id: int, task_id: int, image: bytes) -> None:
    d = today().isoformat()
    if task_id not in {t["id"] for t in tasks_on(user_id)}:
        raise ValueError("That task isn't on today's list.")
    full, thumb = _save_photo(image, f"u{user_id}_t{task_id}")
    with conn() as c:
        old = c.execute(
            "SELECT photo, thumb FROM checkins WHERE task_id=? AND day=?", (task_id, d)
        ).fetchone()
        c.execute(
            "INSERT INTO checkins(task_id, user_id, day, photo, thumb, created_at)"
            " VALUES (?,?,?,?,?,?)"
            " ON CONFLICT(task_id, day) DO UPDATE SET photo=excluded.photo,"
            " thumb=excluded.thumb, created_at=excluded.created_at",
            (task_id, user_id, d, full, thumb, now().isoformat()),
        )
        if old:  # retake: drop the replaced images
            _delete_photos(c, old["photo"], old["thumb"])


def checkins_on(user_id: int, day: dt.date | None = None) -> dict:
    d = (day or today()).isoformat()
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM checkins WHERE user_id=? AND day=?", (user_id, d)
        ).fetchall()
    return {r["task_id"]: r for r in rows}


def recent_proofs(limit: int = 12) -> list:
    with conn() as c:
        return c.execute(
            "SELECT ch.*, t.title, t.emoji AS task_emoji, u.name, u.emoji, u.color"
            " FROM checkins ch JOIN tasks t ON t.id=ch.task_id JOIN users u ON u.id=ch.user_id"
            " ORDER BY ch.created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()


# --------------------------------------------------------------------------- #
# Streaks
# --------------------------------------------------------------------------- #
def _history(user_id: int):
    with conn() as c:
        tasks = c.execute(
            "SELECT id, created_on, archived_on FROM tasks WHERE user_id=?", (user_id,)
        ).fetchall()
        done = c.execute("SELECT task_id, day FROM checkins WHERE user_id=?", (user_id,)).fetchall()
    return tasks, {(r["task_id"], r["day"]) for r in done}


def _active_ids(tasks, d: str) -> list[int]:
    return [t["id"] for t in tasks if t["created_on"] <= d and (t["archived_on"] is None or t["archived_on"] > d)]


def _day_complete(tasks, done_set, day: dt.date) -> bool:
    d = day.isoformat()
    active = _active_ids(tasks, d)
    return bool(active) and all((tid, d) in done_set for tid in active)


def stats(user_id: int) -> dict:
    """Current streak, best streak, and today's progress.

    A day counts when every task active that day has a photo. Today being
    unfinished doesn't break the streak until the day is over.
    """
    tasks, done_set = _history(user_id)
    t = today()
    todays = _active_ids(tasks, t.isoformat())
    done_today = sum((tid, t.isoformat()) in done_set for tid in todays)
    if not tasks:
        return {"current": 0, "best": 0, "done": 0, "total": 0, "complete_days": 0}

    start = min(dt.date.fromisoformat(x["created_on"]) for x in tasks)
    complete = []
    d = start
    while d <= t:
        complete.append(_day_complete(tasks, done_set, d))
        d += dt.timedelta(days=1)

    best = run = 0
    for ok in complete:
        run = run + 1 if ok else 0
        best = max(best, run)

    current = 0
    idx = len(complete) - 1
    if not complete[idx]:  # today still in progress -> count back from yesterday
        idx -= 1
    while idx >= 0 and complete[idx]:
        current += 1
        idx -= 1

    return {"current": current, "best": best, "done": done_today, "total": len(todays), "complete_days": sum(complete)}


def last_7(user_id: int) -> list:
    """Completion for the last 7 days (oldest first). None = no tasks that day."""
    tasks, done_set = _history(user_id)
    out = []
    for i in range(6, -1, -1):
        d = today() - dt.timedelta(days=i)
        out.append(_day_complete(tasks, done_set, d) if _active_ids(tasks, d.isoformat()) else None)
    return out


# --------------------------------------------------------------------------- #
# Pinches
# --------------------------------------------------------------------------- #
def pinch(from_user: int, to_user: int, task_id: int | None, message: str) -> None:
    if from_user == to_user:
        raise ValueError("You can't pinch yourself.")
    cutoff = (now() - dt.timedelta(minutes=PINCH_COOLDOWN_MIN)).isoformat()
    with conn() as c:
        recent = c.execute(
            "SELECT 1 FROM pinches WHERE from_user=? AND to_user=? AND created_at>?",
            (from_user, to_user, cutoff),
        ).fetchone()
        if recent:
            raise ValueError(f"Easy. One pinch per person every {PINCH_COOLDOWN_MIN} minutes.")
        c.execute(
            "INSERT INTO pinches(from_user, to_user, task_id, message, created_at) VALUES (?,?,?,?,?)",
            (from_user, to_user, task_id, (message or "").strip()[:140], now().isoformat()),
        )


def incoming_pinches(user_id: int) -> list:
    with conn() as c:
        return c.execute(
            "SELECT p.*, u.name AS from_name, u.emoji AS from_emoji, u.color AS from_color,"
            " t.title AS task_title"
            " FROM pinches p JOIN users u ON u.id=p.from_user"
            " LEFT JOIN tasks t ON t.id=p.task_id"
            " WHERE p.to_user=? AND p.status='pending' ORDER BY p.created_at DESC",
            (user_id,),
        ).fetchall()


def sent_pinches(user_id: int, limit: int = 6) -> list:
    with conn() as c:
        return c.execute(
            "SELECT p.*, u.name AS to_name, u.emoji AS to_emoji, u.color AS to_color,"
            " t.title AS task_title"
            " FROM pinches p JOIN users u ON u.id=p.to_user"
            " LEFT JOIN tasks t ON t.id=p.task_id"
            " WHERE p.from_user=? ORDER BY p.created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()


def answer_pinch(pinch_id: int, user_id: int, image: bytes) -> None:
    """Reply to a pinch with a live photo. If the pinch named a task that
    isn't done yet today, the photo also checks it off."""
    with conn() as c:
        p = c.execute("SELECT * FROM pinches WHERE id=? AND to_user=?", (pinch_id, user_id)).fetchone()
    if not p:
        raise ValueError("Pinch not found.")
    full, thumb = _save_photo(image, f"pinch{pinch_id}")
    with conn() as c:
        c.execute(
            "UPDATE pinches SET status='answered', photo=?, thumb=?, responded_at=? WHERE id=?",
            (full, thumb, now().isoformat(), pinch_id),
        )
    if p["task_id"] and p["task_id"] not in checkins_on(user_id):
        try:
            check_in(user_id, p["task_id"], image)
        except ValueError:
            pass


def dismiss_pinch(pinch_id: int, user_id: int) -> None:
    with conn() as c:
        c.execute(
            "UPDATE pinches SET status='dismissed', responded_at=? WHERE id=? AND to_user=?",
            (now().isoformat(), pinch_id, user_id),
        )
