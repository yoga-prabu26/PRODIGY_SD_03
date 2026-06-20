"""
database.py — SQLite persistence layer for ContactVault.
"""

import sqlite3
import shutil
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from models import Contact, Category, ActivityLog, ActivityType, AppStats


DB_PATH = Path(__file__).parent / "database" / "contacts.db"


class Database:
    """Thread-safe SQLite database layer."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ── internal ──────────────────────────────────────────────────
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS contacts (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name   TEXT    NOT NULL,
                    mobile      TEXT    NOT NULL,
                    email       TEXT    DEFAULT '',
                    address     TEXT    DEFAULT '',
                    company     TEXT    DEFAULT '',
                    job_title   TEXT    DEFAULT '',
                    notes       TEXT    DEFAULT '',
                    category    TEXT    DEFAULT 'Personal',
                    tags        TEXT    DEFAULT '',
                    is_favorite INTEGER DEFAULT 0,
                    avatar_path TEXT    DEFAULT '',
                    created_at  TEXT    NOT NULL,
                    updated_at  TEXT    NOT NULL
                );

                CREATE TABLE IF NOT EXISTS activity_log (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    action       TEXT NOT NULL,
                    contact_name TEXT NOT NULL,
                    detail       TEXT DEFAULT '',
                    timestamp    TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_contacts_name
                    ON contacts(full_name COLLATE NOCASE);
                CREATE INDEX IF NOT EXISTS idx_contacts_category
                    ON contacts(category);
                CREATE INDEX IF NOT EXISTS idx_contacts_favorite
                    ON contacts(is_favorite);
            """)

    # ── CRUD ──────────────────────────────────────────────────────
    def add_contact(self, c: Contact) -> int:
        sql = """
            INSERT INTO contacts
                (full_name, mobile, email, address, company, job_title,
                 notes, category, tags, is_favorite, avatar_path,
                 created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """
        now = datetime.now().isoformat()
        with self._connect() as conn:
            cur = conn.execute(sql, (
                c.full_name, c.mobile, c.email, c.address, c.company,
                c.job_title, c.notes, c.category.value, c.tags,
                int(c.is_favorite), c.avatar_path, now, now
            ))
            cid = cur.lastrowid
        self._log(ActivityType.ADDED, c.full_name)
        return cid

    def update_contact(self, c: Contact) -> bool:
        sql = """
            UPDATE contacts SET
                full_name=?, mobile=?, email=?, address=?, company=?,
                job_title=?, notes=?, category=?, tags=?, is_favorite=?,
                avatar_path=?, updated_at=?
            WHERE id=?
        """
        now = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(sql, (
                c.full_name, c.mobile, c.email, c.address, c.company,
                c.job_title, c.notes, c.category.value, c.tags,
                int(c.is_favorite), c.avatar_path, now, c.id
            ))
        self._log(ActivityType.EDITED, c.full_name)
        return True

    def delete_contact(self, contact_id: int, name: str = "") -> bool:
        with self._connect() as conn:
            conn.execute("DELETE FROM contacts WHERE id=?", (contact_id,))
        self._log(ActivityType.DELETED, name or f"ID:{contact_id}")
        return True

    def get_contact(self, contact_id: int) -> Optional[Contact]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM contacts WHERE id=?", (contact_id,)
            ).fetchone()
        return self._row_to_contact(row) if row else None

    def get_all_contacts(self, sort_by: str = "full_name",
                          order: str = "ASC") -> list:
        allowed_sort = {"full_name", "company", "created_at",
                        "updated_at", "category"}
        if sort_by not in allowed_sort:
            sort_by = "full_name"
        order = "DESC" if order.upper() == "DESC" else "ASC"
        sql = f"SELECT * FROM contacts ORDER BY {sort_by} {order}"
        with self._connect() as conn:
            rows = conn.execute(sql).fetchall()
        return [self._row_to_contact(r) for r in rows]

    def search_contacts(self, query: str) -> list:
        q = f"%{query}%"
        sql = """
            SELECT * FROM contacts
            WHERE full_name LIKE ? OR mobile LIKE ?
               OR email LIKE ? OR company LIKE ?
               OR job_title LIKE ? OR tags LIKE ?
            ORDER BY full_name
        """
        with self._connect() as conn:
            rows = conn.execute(sql, (q, q, q, q, q, q)).fetchall()
        return [self._row_to_contact(r) for r in rows]

    def get_by_category(self, category: Category) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM contacts WHERE category=? ORDER BY full_name",
                (category.value,)
            ).fetchall()
        return [self._row_to_contact(r) for r in rows]

    def get_favorites(self) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM contacts WHERE is_favorite=1 ORDER BY full_name"
            ).fetchall()
        return [self._row_to_contact(r) for r in rows]

    def toggle_favorite(self, contact_id: int) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT is_favorite, full_name FROM contacts WHERE id=?",
                (contact_id,)
            ).fetchone()
            if not row:
                return False
            new_val = 0 if row["is_favorite"] else 1
            conn.execute(
                "UPDATE contacts SET is_favorite=? WHERE id=?",
                (new_val, contact_id)
            )
        self._log(ActivityType.FAVORITED, row["full_name"],
                  "Added to favorites" if new_val else "Removed from favorites")
        return bool(new_val)

    # ── duplicate detection ───────────────────────────────────────
    def find_duplicates(self, name: str = "", mobile: str = "",
                         exclude_id: int = None) -> list:
        conditions, params = [], []
        if name.strip():
            conditions.append("LOWER(full_name)=LOWER(?)")
            params.append(name.strip())
        if mobile.strip():
            conditions.append("mobile=?")
            params.append(mobile.strip())
        if not conditions:
            return []
        where = " OR ".join(conditions)
        if exclude_id:
            where += " AND id!=?"
            params.append(exclude_id)
        sql = f"SELECT * FROM contacts WHERE ({where})"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_contact(r) for r in rows]

    # ── stats ─────────────────────────────────────────────────────
    def get_stats(self) -> AppStats:
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        with self._connect() as conn:
            def count(where="", params=()):
                return conn.execute(
                    f"SELECT COUNT(*) FROM contacts {where}", params
                ).fetchone()[0]

            return AppStats(
                total=count(),
                family=count("WHERE category='Family'"),
                friends=count("WHERE category='Friends'"),
                business=count("WHERE category='Business'"),
                personal=count("WHERE category='Personal'"),
                favorites=count("WHERE is_favorite=1"),
                recent=count("WHERE created_at >= ?", (cutoff,)),
            )

    # ── activity log ──────────────────────────────────────────────
    def _log(self, action: ActivityType, name: str, detail: str = ""):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO activity_log (action,contact_name,detail,timestamp) VALUES (?,?,?,?)",
                (action.value, name, detail, datetime.now().isoformat())
            )

    def get_activity_log(self, limit: int = 50) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM activity_log ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [ActivityLog(
            id=r["id"],
            action=ActivityType(r["action"]),
            contact_name=r["contact_name"],
            detail=r["detail"],
            timestamp=datetime.fromisoformat(r["timestamp"])
        ) for r in rows]

    # ── backup / restore ──────────────────────────────────────────
    def backup(self, dest: Path) -> bool:
        try:
            shutil.copy2(self.db_path, dest)
            return True
        except Exception:
            return False

    def restore(self, src: Path) -> bool:
        try:
            shutil.copy2(src, self.db_path)
            self._init_db()
            return True
        except Exception:
            return False

    # ── helpers ───────────────────────────────────────────────────
    @staticmethod
    def _row_to_contact(row: sqlite3.Row) -> Contact:
        return Contact(
            id=row["id"],
            full_name=row["full_name"],
            mobile=row["mobile"],
            email=row["email"] or "",
            address=row["address"] or "",
            company=row["company"] or "",
            job_title=row["job_title"] or "",
            notes=row["notes"] or "",
            category=Category.from_str(row["category"] or "Personal"),
            tags=row["tags"] or "",
            is_favorite=bool(row["is_favorite"]),
            avatar_path=row["avatar_path"] or "",
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
        )
