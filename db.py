"""Data layer for Daily Record: SQLite + photos on disk.

Everything that touches storage lives here, so swapping to a hosted
database / object store later only means rewriting this module.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import os
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageOps

try:  # iPhone photos (HEIC) — optional dependency
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass

ROOT = Path(__file__).parent
DATA_DIR = Path(os.environ.get("DAILY_RECORD_DATA", ROOT / "data"))
PHOTO_DIR = DATA_DIR / "photos"
DB_PATH = DATA_DIR / "daily_record.db"

PINCH_COOLDOWN_MIN = 5
MAX_PHOTO_PX = 1600
THUMB_PX = 420


def _tz() -> ZoneInfo:
    name = os.environ.get("APP_TIMEZONE")
    if not name:
        try:
            import streamlit as st

            name = st.secrets.get("APP_TIMEZONE")
        except Exception:
            name = None
    try:
        return ZoneInfo(name or "UTC")
    except Exception:
        return ZoneInfo("UTC")


def now() -> dt.datetime:
    return dt.datetime.now(_tz())


def today() -> dt.date:
    return now().date()


# --------------------------------------------------------------------------- #
# Connection / schema
# --------------------------------------------------------------------------- #
@contextmanager
def conn():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    try:
        yield c
        c.commit()
    finally:
        c.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    emoji       TEXT NOT NULL DEFAULT '🔥',
    color       TEXT NOT NULL DEFAULT '#ff6b1a',
    pin_salt    TEXT NOT NULL,
    pin_hash    TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token       TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    emoji        TEXT NOT NULL DEFAULT '✦',
    created_on   TEXT NOT NULL,   -- first day the task counts (YYYY-MM-DD)
    archived_on  TEXT             -- first day it no longer counts
);
CREATE TABLE IF NOT EXISTS checkins (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day         TEXT NOT NULL,
    photo       TEXT NOT NULL,
    thumb       TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    UNIQUE(task_id, day)
);
CREATE TABLE IF NOT EXISTS pinches (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    to_user       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id       INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    message       TEXT,
    status        TEXT NOT NULL DEFAULT 'pending',  -- pending | answered | dismissed
    photo         TEXT,
    thumb         TEXT,
    created_at    TEXT NOT NULL,
    responded_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_checkins_user_day ON checkins(user_id, day);
CREATE INDEX IF NOT EXISTS idx_pinches_to ON pinches(to_user, status);
"""


def init_db() -> None:
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    with conn() as c:
        c.execute("PRAGMA journal_mode = WAL")
        c.executescript(SCHEMA)


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
    with conn() as c:
        try:
            cur = c.execute(
                "INSERT INTO users(name, emoji, color, pin_salt, pin_hash, created_at)"
                " VALUES (?,?,?,?,?,?)",
                (name, emoji, color, salt, _hash_pin(pin, salt), now().isoformat()),
            )
        except sqlite3.IntegrityError:
            raise ValueError(f"“{name}” is taken. Pick another name.")
        return cur.lastrowid


def list_users() -> list[sqlite3.Row]:
    with conn() as c:
        return c.execute("SELECT * FROM users ORDER BY created_at").fetchall()


def get_user(user_id: int) -> sqlite3.Row | None:
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

    A task created today is deleted outright, since it has no history.
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


def tasks_on(user_id: int, day: dt.date | None = None) -> list[sqlite3.Row]:
    d = (day or today()).isoformat()
    with conn() as c:
        return c.execute(
            "SELECT * FROM tasks WHERE user_id=? AND created_on<=?"
            " AND (archived_on IS NULL OR archived_on>?) ORDER BY id",
            (user_id, d, d),
        ).fetchall()


def active_tasks(user_id: int) -> list[sqlite3.Row]:
    """Tasks not yet removed (what the Tasks page manages)."""
    with conn() as c:
        return c.execute(
            "SELECT * FROM tasks WHERE user_id=? AND archived_on IS NULL ORDER BY id", (user_id,)
        ).fetchall()


# --------------------------------------------------------------------------- #
# Photos & check-ins
# --------------------------------------------------------------------------- #
def _save_photo(data: bytes, prefix: str) -> tuple[str, str]:
    """Normalise orientation, downscale, and write full + thumbnail JPEGs."""
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception as e:
        raise ValueError("That file isn't a readable image.") from e
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{prefix}_{uuid.uuid4().hex[:12]}"
    full, thumb = f"{stem}.jpg", f"{stem}_t.jpg"
    big = img.copy()
    big.thumbnail((MAX_PHOTO_PX, MAX_PHOTO_PX))
    big.save(PHOTO_DIR / full, "JPEG", quality=86, optimize=True)
    ImageOps.fit(img, (THUMB_PX, THUMB_PX)).save(PHOTO_DIR / thumb, "JPEG", quality=80)
    return full, thumb


def photo_path(name: str) -> Path:
    return PHOTO_DIR / name


def check_in(user_id: int, task_id: int, image: bytes) -> None:
    d = today().isoformat()
    valid = {t["id"] for t in tasks_on(user_id)}
    if task_id not in valid:
        raise ValueError("That task isn't on today's list.")
    full, thumb = _save_photo(image, f"u{user_id}_t{task_id}")
    with conn() as c:
        c.execute(
            "INSERT INTO checkins(task_id, user_id, day, photo, thumb, created_at)"
            " VALUES (?,?,?,?,?,?)"
            " ON CONFLICT(task_id, day) DO UPDATE SET photo=excluded.photo,"
            " thumb=excluded.thumb, created_at=excluded.created_at",
            (task_id, user_id, d, full, thumb, now().isoformat()),
        )


def checkins_on(user_id: int, day: dt.date | None = None) -> dict[int, sqlite3.Row]:
    d = (day or today()).isoformat()
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM checkins WHERE user_id=? AND day=?", (user_id, d)
        ).fetchall()
    return {r["task_id"]: r for r in rows}


def recent_proofs(limit: int = 12) -> list[sqlite3.Row]:
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
    done_set = {(r["task_id"], r["day"]) for r in done}
    return tasks, done_set


def _day_complete(tasks, done_set, day: dt.date) -> bool:
    d = day.isoformat()
    active = [
        t["id"] for t in tasks
        if t["created_on"] <= d and (t["archived_on"] is None or t["archived_on"] > d)
    ]
    return bool(active) and all((tid, d) in done_set for tid in active)


def stats(user_id: int) -> dict:
    """Current streak, best streak, and today's progress.

    A day counts when every task active that day has a photo. Today being
    unfinished doesn't break the streak until the day is over.
    """
    tasks, done_set = _history(user_id)
    t = today()
    todays = [
        x["id"] for x in tasks
        if x["created_on"] <= t.isoformat() and (x["archived_on"] is None or x["archived_on"] > t.isoformat())
    ]
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

    return {
        "current": current,
        "best": best,
        "done": done_today,
        "total": len(todays),
        "complete_days": sum(complete),
    }


def last_7(user_id: int) -> list[bool | None]:
    """Completion for the last 7 days (oldest first). None = no tasks that day."""
    tasks, done_set = _history(user_id)
    out = []
    for i in range(6, -1, -1):
        d = today() - dt.timedelta(days=i)
        ds = d.isoformat()
        has = any(x["created_on"] <= ds and (x["archived_on"] is None or x["archived_on"] > ds) for x in tasks)
        out.append(_day_complete(tasks, done_set, d) if has else None)
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
            "INSERT INTO pinches(from_user, to_user, task_id, message, created_at)"
            " VALUES (?,?,?,?,?)",
            (from_user, to_user, task_id, (message or "").strip()[:140], now().isoformat()),
        )


def incoming_pinches(user_id: int) -> list[sqlite3.Row]:
    with conn() as c:
        return c.execute(
            "SELECT p.*, u.name AS from_name, u.emoji AS from_emoji, u.color AS from_color,"
            " t.title AS task_title"
            " FROM pinches p JOIN users u ON u.id=p.from_user"
            " LEFT JOIN tasks t ON t.id=p.task_id"
            " WHERE p.to_user=? AND p.status='pending' ORDER BY p.created_at DESC",
            (user_id,),
        ).fetchall()


def sent_pinches(user_id: int, limit: int = 6) -> list[sqlite3.Row]:
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
        p = c.execute(
            "SELECT * FROM pinches WHERE id=? AND to_user=?", (pinch_id, user_id)
        ).fetchone()
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
