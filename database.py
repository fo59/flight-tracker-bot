import sqlite3
from contextlib import contextmanager
from typing import Optional

from config import DB_PATH


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                language TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS flights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                flight_number TEXT NOT NULL,
                destination_icao TEXT NOT NULL,
                origin_icao TEXT,
                status TEXT DEFAULT 'scheduled',
                icao24 TEXT,
                notified_takeoff INTEGER DEFAULT 0,
                notified_30min INTEGER DEFAULT 0,
                notified_landed INTEGER DEFAULT 0,
                notified_delay INTEGER DEFAULT 0,
                last_lat REAL,
                last_lon REAL,
                last_check DATETIME,
                added_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                pref_takeoff INTEGER DEFAULT 1,
                pref_30min INTEGER DEFAULT 1,
                pref_landed INTEGER DEFAULT 1,
                pref_delay INTEGER DEFAULT 1,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                UNIQUE(user_id, flight_number)
            )
        """)
        try:
            conn.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        for col in ("pref_takeoff", "pref_30min", "pref_landed", "pref_delay"):
            try:
                conn.execute(f"ALTER TABLE flights ADD COLUMN {col} INTEGER DEFAULT 1")
            except sqlite3.OperationalError:
                pass
        try:
            conn.execute("ALTER TABLE flights ADD COLUMN origin_icao TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE flights ADD COLUMN dest_auto INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        for col in ("sched_departure", "sched_arrival", "dep_icao"):
            try:
                conn.execute(f"ALTER TABLE flights ADD COLUMN {col} TEXT")
            except sqlite3.OperationalError:
                pass
        for col in (("pref_position", "INTEGER DEFAULT 0"), ("last_position_notification", "TEXT")):
            try:
                conn.execute(f"ALTER TABLE flights ADD COLUMN {col[0]} {col[1]}")
            except sqlite3.OperationalError:
                pass


def upsert_user(user_id: int, username: Optional[str]):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (user_id, username) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username",
            (user_id, username),
        )


def set_language(user_id: int, lang: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET language = ? WHERE user_id = ?",
            (lang, user_id),
        )


def get_user_language(user_id: int) -> Optional[str]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT language FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        lang = row["language"] if row else None
        return lang if lang else None


def add_flight(user_id: int, flight_number: str, destination_icao: str = "", origin_icao: Optional[str] = None, dest_auto: int = 0, sched_departure: Optional[str] = None, sched_arrival: Optional[str] = None):
    try:
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO flights (user_id, flight_number, destination_icao, origin_icao, dest_auto, sched_departure, sched_arrival) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, flight_number.upper(), destination_icao.upper() if destination_icao else "", origin_icao.upper() if origin_icao else None, dest_auto, sched_departure, sched_arrival),
            )
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return False


def remove_flight(user_id: int, flight_number: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM flights WHERE user_id = ? AND flight_number = ?",
            (user_id, flight_number.upper()),
        )
        return cur.rowcount > 0


def list_flights(user_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM flights WHERE user_id = ? ORDER BY added_date DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_flight(flight_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM flights WHERE id = ?", (flight_id,)
        ).fetchone()
        return dict(row) if row else None


def update_pref(flight_id: int, pref: str, value: int):
    with get_conn() as conn:
        conn.execute(
            f"UPDATE flights SET {pref} = ? WHERE id = ?",
            (value, flight_id),
        )


def get_all_tracked_flights():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM flights WHERE status != 'landed'"
        ).fetchall()
        return [dict(r) for r in rows]


def update_flight(flight_id: int, **fields):
    if not fields:
        return
    from datetime import datetime, timezone
    fields["last_check"] = datetime.now(timezone.utc).isoformat()
    columns = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [flight_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE flights SET {columns} WHERE id = ?", values)


def get_user(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()


def get_user_flight_count(user_id: int) -> int:
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM flights WHERE user_id = ?", (user_id,)
        ).fetchone()[0]


def get_flights_with_position_updates():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM flights WHERE pref_position = 1 AND status = 'airborne'"
        ).fetchall()
        return [dict(r) for r in rows]


def update_position_notification_time(flight_id: int):
    from datetime import datetime, timezone
    with get_conn() as conn:
        conn.execute(
            "UPDATE flights SET last_position_notification = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), flight_id),
        )


def cleanup_old_flights() -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM flights WHERE status = 'landed' AND last_check IS NOT NULL "
            "AND datetime(last_check) < datetime('now', '-1 day')"
        )
        return cur.rowcount


def get_stats():
    with get_conn() as conn:
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM flights").fetchone()[0]
        airborne = conn.execute("SELECT COUNT(*) FROM flights WHERE status='airborne'").fetchone()[0]
        scheduled = conn.execute("SELECT COUNT(*) FROM flights WHERE status='scheduled'").fetchone()[0]
        landed = conn.execute("SELECT COUNT(*) FROM flights WHERE status='landed'").fetchone()[0]
        return {
            "users": users,
            "total_flights": total,
            "airborne": airborne,
            "scheduled": scheduled,
            "landed": landed,
        }
