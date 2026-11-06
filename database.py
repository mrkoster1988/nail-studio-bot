"""Слой доступа к данным: SQLite и вспомогательные функции."""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id         INTEGER UNIQUE NOT NULL,
    name          TEXT,
    phone         TEXT,
    username      TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS services (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    price       INTEGER NOT NULL DEFAULT 0,
    duration    INTEGER NOT NULL DEFAULT 60,
    category    TEXT NOT NULL DEFAULT 'Общее',
    description TEXT,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bookings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    service_id  INTEGER NOT NULL,
    slot_start  TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    comment     TEXT,
    calendar_event_id TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS broadcasts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    text         TEXT NOT NULL,
    audience     TEXT NOT NULL DEFAULT 'all',
    sent_count   INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reminders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id  INTEGER NOT NULL,
    kind        TEXT NOT NULL,
    sent_at     TEXT NOT NULL,
    UNIQUE (booking_id, kind)
);

CREATE INDEX IF NOT EXISTS idx_bookings_slot   ON bookings (slot_start);
CREATE INDEX IF NOT EXISTS idx_bookings_user   ON bookings (user_id);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings (status);
CREATE INDEX IF NOT EXISTS idx_services_cat   ON services (category, is_active);
CREATE INDEX IF NOT EXISTS idx_reminders_bk   ON reminders (booking_id);
CREATE TABLE IF NOT EXISTS reviews (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id  INTEGER UNIQUE NOT NULL,
    user_id     INTEGER NOT NULL,
    rating      INTEGER NOT NULL,
    text        TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS points_ledger (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    delta       INTEGER NOT NULL,
    reason      TEXT NOT NULL DEFAULT "",
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS referrals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER UNIQUE NOT NULL,
    referrer_id INTEGER NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_points_user  ON points_ledger (user_id);
CREATE INDEX IF NOT EXISTS idx_reviews_user ON reviews (user_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_bookings_active_slot
    ON bookings (slot_start) WHERE status != "cancelled";

"""

STATUS_PENDING = "pending"
STATUS_CONFIRMED = "confirmed"
STATUS_CANCELLED = "cancelled"
STATUS_DONE = "done"

STATUS_TITLES = {
    STATUS_PENDING: "⏳ Ожидает",
    STATUS_CONFIRMED: "✅ Подтверждена",
    STATUS_CANCELLED: "❌ Отменена",
    STATUS_DONE: "🏁 Завершена",
}

STATUS_ICONS = {
    STATUS_PENDING: "⏳",
    STATUS_CONFIRMED: "✅",
    STATUS_CANCELLED: "❌",
    STATUS_DONE: "🏁",
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    folder = os.path.dirname(config.DB_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.executescript(SCHEMA)
    seed_services()


def seed_services() -> None:
    """Наполняет каталог услугами при первом запуске."""
    defaults = [
        ("Классический маникюр", 1800, 60, "Маникюр", "Классическое покрытие, уход за кутикулой"),
        ("Маникюр с покрытием гель-лак", 2600, 90, "Маникюр", "Аппаратный маникюр и гель-лак на выбор"),
        ("Маникюр с укреплением и гель-лаком", 3200, 120, "Маникюр", "Укрепление пластины и покрытие гель-лаком"),
        ("Дизайн на ногтях", 500, 20, "Дизайн", "Дополнительно к любому маникюру"),
        ("Снятие покрытия", 500, 20, "Доп. услуги", "Снятие гель-лака или полимерного покрытия"),
        ("Педикюр классический", 2000, 60, "Педикюр", "Обработка стоп, уход за ногтями"),
        ("Педикюр с покрытием гель-лак", 2800, 90, "Педикюр", "Аппаратный педикюр и гель-лак"),
        ("SPA-педикюр", 3500, 90, "Педикюр", "Педикюр с пилингом и массажем стоп"),
    ]
    with db() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM services").fetchone()["c"]
        if count:
            return
        conn.executemany(
            "INSERT INTO services (title, price, duration, category, description, is_active, created_at)"
            " VALUES (?,?,?,?,?,1,?)",
            [(t, p, d, c, desc, now_iso()) for t, p, d, c, desc in defaults],
        )


# --- Пользователи ---------------------------------------------------------

def upsert_user(tg_id: int, name: str = None, username: str = None) -> int:
    with db() as conn:
        row = conn.execute("SELECT id FROM users WHERE tg_id = ?", (tg_id,)).fetchone()
        if row:
            conn.execute(
                "UPDATE users SET name = COALESCE(?, name), username = COALESCE(?, username) WHERE id = ?",
                (name, username, row["id"]),
            )
            return row["id"]
        cur = conn.execute(
            "INSERT INTO users (tg_id, name, username, created_at) VALUES (?,?,?,?)",
            (tg_id, name, username, now_iso()),
        )
        return cur.lastrowid


def set_user_phone(user_id: int, phone: str) -> None:
    with db() as conn:
        conn.execute("UPDATE users SET phone = ? WHERE id = ?", (phone, user_id))


def get_user_by_tg(tg_id: int) -> Optional[sqlite3.Row]:
    with db() as conn:
        return conn.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,)).fetchone()


def all_users() -> list:
    with db() as conn:
        return conn.execute("SELECT * FROM users ORDER BY id").fetchall()


# --- Услуги ---------------------------------------------------------------

def add_service(title, price, duration, category, description) -> int:
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO services (title, price, duration, category, description, is_active, created_at)"
            " VALUES (?,?,?,?,?,1,?)",
            (title, int(price), int(duration), category, description, now_iso()),
        )
        return cur.lastrowid


def list_services(only_active: bool = True) -> list:
    sql = "SELECT * FROM services"
    if only_active:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY category, price"
    with db() as conn:
        return conn.execute(sql).fetchall()


def get_service(service_id: int) -> Optional[sqlite3.Row]:
    with db() as conn:
        return conn.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()


def update_service(service_id: int, **fields) -> None:
    allowed = {"title", "price", "duration", "category", "description", "is_active"}
    sets = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not sets:
        return
    clause = ", ".join(f"{k} = ?" for k in sets)
    with db() as conn:
        conn.execute(f"UPDATE services SET {clause} WHERE id = ?", (*sets.values(), service_id))


def delete_service(service_id: int) -> None:
    with db() as conn:
        conn.execute("UPDATE services SET is_active = 0 WHERE id = ?", (service_id,))


def service_categories() -> list:
    with db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT category FROM services WHERE is_active = 1 ORDER BY category"
        ).fetchall()
    return [r["category"] for r in rows]


# --- Записи ---------------------------------------------------------------

def add_booking(user_id: int, service_id: int, slot_start: str, comment: str = None) -> int:
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO bookings (user_id, service_id, slot_start, status, comment, created_at)"
            " VALUES (?,?,?,?,?,?)",
            (user_id, service_id, slot_start, STATUS_PENDING, comment, now_iso()),
        )
        return cur.lastrowid


BOOKING_SELECT = (
    "SELECT b.*, u.tg_id, u.name, u.phone, u.username,"
    " s.title AS service_title, s.price AS service_price, s.duration AS service_duration"
    " FROM bookings b"
    " JOIN users u ON u.id = b.user_id"
    " JOIN services s ON s.id = b.service_id"
)


def get_booking(booking_id: int) -> Optional[sqlite3.Row]:
    with db() as conn:
        return conn.execute(BOOKING_SELECT + " WHERE b.id = ?", (booking_id,)).fetchone()


def set_booking_status(booking_id: int, status: str) -> None:
    with db() as conn:
        conn.execute("UPDATE bookings SET status = ? WHERE id = ?", (status, booking_id))


def cancel_booking(booking_id: int) -> None:
    set_booking_status(booking_id, STATUS_CANCELLED)


def user_bookings(user_id: int, active_only: bool = False) -> list:
    sql = (
        "SELECT b.*, s.title AS service_title, s.price AS service_price"
        " FROM bookings b JOIN services s ON s.id = b.service_id"
        " WHERE b.user_id = ?"
    )
    if active_only:
        sql += f" AND b.status IN ('{STATUS_PENDING}', '{STATUS_CONFIRMED}')"
    sql += " ORDER BY b.slot_start DESC"
    with db() as conn:
        return conn.execute(sql, (user_id,)).fetchall()


def active_booking_count(user_id: int) -> int:
    with db() as conn:
        row = conn.execute(
            f"SELECT COUNT(*) AS c FROM bookings WHERE user_id = ?"
            f" AND status IN ('{STATUS_PENDING}', '{STATUS_CONFIRMED}')",
            (user_id,),
        ).fetchone()
    return row["c"]


def bookings_for_date(day: str) -> list:
    """Все неотменённые записи на дату (YYYY-MM-DD)."""
    with db() as conn:
        return conn.execute(
            BOOKING_SELECT + " WHERE DATE(b.slot_start) = ? AND b.status != 'cancelled'"
            " ORDER BY b.slot_start",
            (day,),
        ).fetchall()


def all_bookings(status: str = None, limit: int = 100) -> list:
    sql = BOOKING_SELECT
    args = []
    if status:
        sql += " WHERE b.status = ?"
        args.append(status)
    sql += " ORDER BY b.slot_start DESC LIMIT ?"
    args.append(limit)
    with db() as conn:
        return conn.execute(sql, args).fetchall()


def is_slot_busy(slot_start: str, duration: int) -> bool:
    """Проверяет пересечение слота с существующей активной записью."""
    start = datetime.fromisoformat(slot_start)
    end = start + timedelta(minutes=duration)
    with db() as conn:
        rows = conn.execute(
            "SELECT b.slot_start, s.duration FROM bookings b"
            " JOIN services s ON s.id = b.service_id"
            " WHERE b.status IN ('pending','confirmed')"
        ).fetchall()
    for r in rows:
        s = datetime.fromisoformat(r["slot_start"])
        e = s + timedelta(minutes=r["duration"])
        if start < e and s < end:
            return True
    return False


# --- Напоминания ----------------------------------------------------------

def reminder_sent(booking_id: int, kind: str) -> bool:
    """Было ли уже отправлено напоминание этого вида для этой записи."""
    with db() as conn:
        row = conn.execute(
            "SELECT 1 FROM reminders WHERE booking_id = ? AND kind = ?",
            (booking_id, kind),
        ).fetchone()
    return row is not None


def mark_reminder_sent(booking_id: int, kind: str) -> None:
    """Отмечает напоминание отправленным. Повторный вызов не создаёт дубль."""
    with db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO reminders (booking_id, kind, sent_at) VALUES (?,?,?)",
            (booking_id, kind, now_iso()),
        )


def clear_reminders(booking_id: int) -> None:
    """Снимает отметки — нужно при переносе записи на другое время."""
    with db() as conn:
        conn.execute("DELETE FROM reminders WHERE booking_id = ?", (booking_id,))


# --- Рассылки -------------------------------------------------------------

def save_broadcast(text: str, audience: str, sent: int, failed: int) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO broadcasts (text, audience, sent_count, failed_count, created_at)"
            " VALUES (?,?,?,?,?)",
            (text, audience, sent, failed, now_iso()),
        )


def broadcasts_history(limit: int = 20) -> list:
    with db() as conn:
        return conn.execute(
            "SELECT * FROM broadcasts ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()


# --- Статистика -----------------------------------------------------------

def stats() -> dict:
    with db() as conn:
        total_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        total_bookings = conn.execute("SELECT COUNT(*) AS c FROM bookings").fetchone()["c"]
        active = conn.execute(
            "SELECT COUNT(*) AS c FROM bookings WHERE status IN ('pending','confirmed')"
        ).fetchone()["c"]
        done = conn.execute(
            "SELECT COUNT(*) AS c FROM bookings WHERE status = 'done'"
        ).fetchone()["c"]
        revenue = conn.execute(
            "SELECT COALESCE(SUM(s.price), 0) AS total FROM bookings b"
            " JOIN services s ON s.id = b.service_id WHERE b.status = 'done'"
        ).fetchone()["total"]
        top = conn.execute(
            "SELECT s.title, COUNT(b.id) AS cnt FROM bookings b"
            " JOIN services s ON s.id = b.service_id"
            " GROUP BY s.title ORDER BY cnt DESC LIMIT 5"
        ).fetchall()
        upcoming = conn.execute(
            "SELECT COUNT(*) AS c FROM bookings"
            " WHERE status = 'confirmed' AND slot_start >= ?",
            (now_iso(),),
        ).fetchone()["c"]
    return {
        "total_users": total_users,
        "total_bookings": total_bookings,
        "active": active,
        "done": done,
        "revenue": revenue,
        "upcoming": upcoming,
        "top_services": top,
    }


# --- Бонусные баллы --------------------------------------------------------

POINTS_PER_VISIT = 10
POINTS_PER_REFERRAL = 50


def add_points(user_id: int, delta: int, reason: str = "") -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO points_ledger (user_id, delta, reason, created_at) VALUES (?,?,?,?)",
            (user_id, delta, reason, now_iso()),
        )


def get_points(user_id: int) -> int:
    with db() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(delta), 0) AS p FROM points_ledger WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return row["p"]


# --- Отзывы ----------------------------------------------------------------

def add_review(booking_id: int, user_id: int, rating: int, text: str = None) -> None:
    with db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO reviews (booking_id, user_id, rating, text, created_at)"
            " VALUES (?,?,?,?,?)",
            (booking_id, user_id, rating, text, now_iso()),
        )


def reviews_stats() -> dict:
    with db() as conn:
        avg = conn.execute("SELECT AVG(rating) AS a, COUNT(*) AS c FROM reviews").fetchone()
    return {"avg": round(avg["a"] or 0, 2), "count": avg["c"]}


def list_reviews(limit: int = 20) -> list:
    with db() as conn:
        return conn.execute(
            "SELECT r.*, u.name FROM reviews r JOIN users u ON u.id = r.user_id"
            " ORDER BY r.id DESC LIMIT ?",
            (limit,),
        ).fetchall()


# --- Рефералы --------------------------------------------------------------

def set_referrer(user_id: int, referrer_tg_id: int) -> bool:
    with db() as conn:
        if conn.execute(
            "SELECT 1 FROM referrals WHERE user_id = ?", (user_id,)
        ).fetchone():
            return False
        referrer = conn.execute(
            "SELECT id FROM users WHERE tg_id = ?", (referrer_tg_id,)
        ).fetchone()
        if not referrer or referrer["id"] == user_id:
            return False
        conn.execute(
            "INSERT INTO referrals (user_id, referrer_id, created_at) VALUES (?,?,?)",
            (user_id, referrer["id"], now_iso()),
        )
        return True


def get_referrer_id(user_id: int):
    with db() as conn:
        row = conn.execute(
            "SELECT referrer_id FROM referrals WHERE user_id = ?", (user_id,)
        ).fetchone()
    return row["referrer_id"] if row else None


def has_any_booking(user_id: int) -> bool:
    with db() as conn:
        row = conn.execute(
            "SELECT 1 FROM bookings WHERE user_id = ? LIMIT 1", (user_id,)
        ).fetchone()
    return row is not None


# --- Google Calendar синхронизация -----------------------------------------

def set_calendar_event(booking_id: int, event_id) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE bookings SET calendar_event_id = ? WHERE id = ?",
            (event_id, booking_id),
        )


def get_calendar_event(booking_id: int):
    row = get_booking(booking_id)
    return row["calendar_event_id"] if row else None


# --- Защита от двойной записи ------------------------------------------------

import sqlite3 as _sqlite3


def try_add_booking(user_id: int, service_id: int, slot_start: str, comment=None):
    """Создает запись; None если слот уже занят (уникальный индекс активных записей)."""
    try:
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO bookings (user_id, service_id, slot_start, status, comment, created_at)"
                " VALUES (?,?,?,?,?,?)",
                (user_id, service_id, slot_start, STATUS_PENDING, comment, now_iso()),
            )
            return cur.lastrowid
    except _sqlite3.IntegrityError:
        return None


# --- Баллы -> скидка -----------------------------------------------------------

POINTS_TO_RUB = 1  # 1 балл = 1 рубль скидки


def spend_points(user_id: int, amount: int) -> bool:
    """Списывает баллы, если их хватает. False — не хватает."""
    if get_points(user_id) < amount:
        return False
    with db() as conn:
        conn.execute(
            "INSERT INTO points_ledger (user_id, delta, reason, created_at) VALUES (?,?,?,?)",
            (user_id, -amount, "discount", now_iso()),
        )
    return True


# --- Отмена напоминаний -------------------------------------------------------

def cancel_reminders(booking_id: int) -> None:
    """Помечает все несработавшие напоминания записи как отменённые."""
    with db() as conn:
        conn.execute(
            "UPDATE reminders SET sent = 1 WHERE booking_id = ? AND sent = 0",
            (booking_id,),
        )
