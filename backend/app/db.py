import sqlite3
import time
from pathlib import Path

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tg_id INTEGER UNIQUE,
  name TEXT,
  username TEXT,
  created_at INTEGER,
  expires_at INTEGER,
  uuid TEXT,
  config_json TEXT,
  config_uri TEXT,
  server_active INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS payments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  amount INTEGER,
  plan TEXT,
  provider TEXT,
  status TEXT,
  created_at INTEGER,
  confirmed_at INTEGER
);
"""


def _connect():
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        conn.executescript(SCHEMA)


def get_or_create_user(tg_id: int, name: str, username: str | None) -> dict:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,)).fetchone()
        if row:
            if (row["name"], row["username"]) != (name, username):
                conn.execute("UPDATE users SET name = ?, username = ? WHERE tg_id = ?", (name, username, tg_id))
            return dict(row)
        cur = conn.execute(
            "INSERT INTO users (tg_id, name, username, created_at) VALUES (?, ?, ?, ?)",
            (tg_id, name, username, int(time.time())),
        )
        conn.commit()
        return get_or_create_user(tg_id, name, username)


def get_user(tg_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def save_config(tg_id: int, uuid: str, config_json: str, config_uri: str):
    with _connect() as conn:
        conn.execute("UPDATE users SET uuid = ?, config_json = ?, config_uri = ?, server_active = 1 WHERE tg_id = ?",
                     (uuid, config_json, config_uri, tg_id))
        conn.commit()


def set_server_active(tg_id: int, active: bool):
    with _connect() as conn:
        conn.execute("UPDATE users SET server_active = ? WHERE tg_id = ?", (1 if active else 0, tg_id))
        conn.commit()


def extend_user(tg_id: int, days: int):
    with _connect() as conn:
        row = conn.execute("SELECT expires_at FROM users WHERE tg_id = ?", (tg_id,)).fetchone()
        if not row:
            return False
        now = int(time.time())
        base = row["expires_at"] if row["expires_at"] and row["expires_at"] > now else now
        conn.execute("UPDATE users SET expires_at = ? WHERE tg_id = ?", (base + days * 86400, tg_id))
        conn.commit()
        return True


def revoke_user(tg_id: int):
    with _connect() as conn:
        conn.execute("UPDATE users SET server_active = 0 WHERE tg_id = ?", (tg_id,))
        conn.commit()


def get_expired_active() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM users WHERE server_active = 1 AND expires_at IS NOT NULL AND expires_at < ?",
            (int(time.time()),),
        ).fetchall()
        return [dict(r) for r in rows]


def create_payment(user_id: int, amount: int, plan: str, provider: str) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO payments (user_id, amount, plan, provider, status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
            (user_id, amount, plan, provider, int(time.time())),
        )
        conn.commit()
        return cur.lastrowid


def get_payment(payment_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
        return dict(row) if row else None


def set_payment_status(payment_id: int, status: str):
    with _connect() as conn:
        conn.execute("UPDATE payments SET status = ?, confirmed_at = ? WHERE id = ?",
                     (status, int(time.time()) if status == "paid" else None, payment_id))
        conn.commit()


def stats() -> dict:
    with _connect() as conn:
        now = int(time.time())
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        active = conn.execute("SELECT COUNT(*) FROM users WHERE server_active = 1 AND expires_at > ?", (now,)).fetchone()[0]
        paid = conn.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM payments WHERE status = 'paid'").fetchone()
        return {"users": users, "active": active, "paid_count": paid[0], "revenue": paid[1]}


def list_payments(limit: int = 20) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT p.*, u.tg_id AS tg_id, u.username FROM payments p LEFT JOIN users u ON u.id = p.user_id "
            "ORDER BY p.id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]