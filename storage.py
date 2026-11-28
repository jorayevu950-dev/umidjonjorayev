# -*- coding: utf-8 -*-
"""
SQLite bazasi: foydalanuvchilar, yaratilgan ishlar, kunlik limit va sozlamalar.
"""

import datetime
import os
import sqlite3


class Storage:
    def __init__(self, db_path):
        folder = os.path.dirname(db_path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        cur = self.conn.cursor()
        cur.execute(
            """CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                created_at TEXT,
                last_seen TEXT,
                lang TEXT DEFAULT 'uz',
                works INTEGER DEFAULT 0
            )"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS works (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                kind TEXT,
                topic TEXT,
                file_name TEXT,
                created_at TEXT
            )"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )"""
        )
        # Eski bazalarga ustun qo'shish (migratsiya)
        cols = {r["name"] for r in cur.execute("PRAGMA table_info(users)").fetchall()}
        if "last_seen" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN last_seen TEXT")
        if "lang" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN lang TEXT DEFAULT 'uz'")
        self.conn.commit()

    # ------------------------------------------------------------------
    # Foydalanuvchilar
    # ------------------------------------------------------------------
    def add_user(self, user_id, username, full_name):
        """Yangi foydalanuvchi bo'lsa True, eskisi bo'lsa False qaytaradi."""
        now = datetime.datetime.now().isoformat(timespec="seconds")
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO users (user_id, username, full_name, created_at, last_seen) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, username or "", full_name or "", now, now),
        )
        is_new = cur.rowcount > 0
        if not is_new:
            self.conn.execute(
                "UPDATE users SET username = ?, full_name = ?, last_seen = ? WHERE user_id = ?",
                (username or "", full_name or "", now, user_id),
            )
        self.conn.commit()
        return is_new

    def touch(self, user_id):
        now = datetime.datetime.now().isoformat(timespec="seconds")
        self.conn.execute("UPDATE users SET last_seen = ? WHERE user_id = ?", (now, user_id))
        self.conn.commit()

    def set_lang(self, user_id, lang):
        self.conn.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))
        self.conn.commit()

    def get_lang(self, user_id):
        row = self.conn.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,)).fetchone()
        val = (row["lang"] if row else "") or "uz"
        return val if val in ("uz", "ru", "en") else "uz"

    def today_count(self, user_id):
        today = datetime.date.today().isoformat()
        row = self.conn.execute(
            "SELECT COUNT(*) AS c FROM works WHERE user_id = ? AND substr(created_at, 1, 10) = ?",
            (user_id, today),
        ).fetchone()
        return row["c"] if row else 0

    # ------------------------------------------------------------------
    # Ishlar
    # ------------------------------------------------------------------
    def log_work(self, user_id, kind, topic, file_name):
        now = datetime.datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            "INSERT INTO works (user_id, kind, topic, file_name, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, kind, topic, file_name, now),
        )
        self.conn.execute("UPDATE users SET works = works + 1 WHERE user_id = ?", (user_id,))
        self.conn.commit()

    def user_works(self, user_id, limit=10):
        rows = self.conn.execute(
            "SELECT kind, topic, created_at FROM works WHERE user_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return rows

    # ------------------------------------------------------------------
    # Statistika
    # ------------------------------------------------------------------
    def stats(self):
        """Admin uchun to'liq statistika."""
        today = datetime.date.today()
        today_s = today.isoformat()
        week_s = (today - datetime.timedelta(days=6)).isoformat()
        day_ago = (datetime.datetime.now() - datetime.timedelta(hours=24)).isoformat(
            timespec="seconds"
        )

        def one(sql, args=()):
            row = self.conn.execute(sql, args).fetchone()
            return (row[0] if row else 0) or 0

        users = one("SELECT COUNT(*) FROM users")
        new_today = one("SELECT COUNT(*) FROM users WHERE substr(created_at, 1, 10) = ?", (today_s,))
        active_today = one(
            "SELECT COUNT(*) FROM users WHERE substr(last_seen, 1, 10) = ?", (today_s,)
        )
        active_24h = one("SELECT COUNT(*) FROM users WHERE last_seen >= ?", (day_ago,))
        active_week = one("SELECT COUNT(DISTINCT user_id) FROM users WHERE last_seen >= ?", (week_s,))
        works = one("SELECT COUNT(*) FROM works")
        works_today = one("SELECT COUNT(*) FROM works WHERE substr(created_at, 1, 10) = ?", (today_s,))
        works_week = one(
            "SELECT COUNT(*) FROM works WHERE substr(created_at, 1, 10) >= ?", (week_s,)
        )
        kinds = self.conn.execute(
            "SELECT kind, COUNT(*) AS c FROM works GROUP BY kind ORDER BY c DESC"
        ).fetchall()
        top_users = self.conn.execute(
            "SELECT u.full_name, u.username, u.works FROM users u "
            "WHERE u.works > 0 ORDER BY u.works DESC LIMIT 5"
        ).fetchall()
        return {
            "users": users,
            "new_today": new_today,
            "active_today": active_today,
            "active_24h": active_24h,
            "active_week": active_week,
            "works": works,
            "works_today": works_today,
            "works_week": works_week,
            "today": works_today,
            "kinds": kinds,
            "top_users": top_users,
        }

    def all_user_ids(self):
        rows = self.conn.execute("SELECT user_id FROM users").fetchall()
        return [r["user_id"] for r in rows]

    def recent_users(self, limit=5):
        return self.conn.execute(
            "SELECT user_id, username, full_name, created_at FROM users "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()

    # ------------------------------------------------------------------
    # Sozlamalar (admin ID va h.k.)
    # ------------------------------------------------------------------
    def set_meta(self, key, value):
        self.conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
        self.conn.commit()

    def get_meta(self, key, default=""):
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default
