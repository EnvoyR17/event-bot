from __future__ import annotations

import aiosqlite

from config import DB_PATH, ROLE_ADMIN, ROLE_NONE


async def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                points INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS staff (
                tg_user_id INTEGER PRIMARY KEY,
                full_name TEXT,
                username TEXT,
                role TEXT NOT NULL DEFAULT 'none',
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS invites (
                code TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_by INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS point_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                participant_id INTEGER NOT NULL,
                delta INTEGER NOT NULL,
                staff_tg_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (participant_id) REFERENCES participants(id)
            );
            """
        )
        await db.commit()


def _row_factory(cursor, row):
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


async def upsert_staff(
    tg_user_id: int,
    full_name: str | None,
    username: str | None,
    *,
    role: str | None = None,
    force_admin: bool = False,
) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = _row_factory
        cur = await db.execute(
            "SELECT role FROM staff WHERE tg_user_id = ?", (tg_user_id,)
        )
        existing = await cur.fetchone()
        if existing:
            new_role = existing["role"]
            if force_admin:
                new_role = ROLE_ADMIN
            elif role is not None and existing["role"] != ROLE_ADMIN:
                new_role = role
            await db.execute(
                """
                UPDATE staff
                SET full_name = ?, username = ?, role = ?,
                    updated_at = datetime('now')
                WHERE tg_user_id = ?
                """,
                (full_name, username, new_role, tg_user_id),
            )
            await db.commit()
            return new_role
        new_role = ROLE_ADMIN if force_admin else (role or ROLE_NONE)
        await db.execute(
            """
            INSERT INTO staff (tg_user_id, full_name, username, role)
            VALUES (?, ?, ?, ?)
            """,
            (tg_user_id, full_name, username, new_role),
        )
        await db.commit()
        return new_role


async def get_staff_role(tg_user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = _row_factory
        cur = await db.execute(
            "SELECT role FROM staff WHERE tg_user_id = ?", (tg_user_id,)
        )
        row = await cur.fetchone()
        return row["role"] if row else ROLE_NONE


async def set_staff_role(tg_user_id: int, role: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE staff SET role = ?, updated_at = datetime('now')
            WHERE tg_user_id = ?
            """,
            (role, tg_user_id),
        )
        await db.commit()


async def list_staff() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = _row_factory
        cur = await db.execute(
            """
            SELECT tg_user_id, full_name, username, role
            FROM staff
            ORDER BY role DESC, full_name
            """
        )
        return await cur.fetchall()


async def get_staff(tg_user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = _row_factory
        cur = await db.execute(
            "SELECT * FROM staff WHERE tg_user_id = ?", (tg_user_id,)
        )
        return await cur.fetchone()


async def create_invite(code: str, role: str, created_by: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO invites (code, role, created_by) VALUES (?, ?, ?)",
            (code, role, created_by),
        )
        await db.commit()


async def get_invite(code: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = _row_factory
        cur = await db.execute("SELECT * FROM invites WHERE code = ?", (code,))
        return await cur.fetchone()


async def list_invites() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = _row_factory
        cur = await db.execute(
            """
            SELECT code, role, active, created_by, created_at
            FROM invites
            ORDER BY created_at DESC
            """
        )
        return await cur.fetchall()


async def set_invite_active(code: str, active: bool) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE invites SET active = ? WHERE code = ?",
            (1 if active else 0, code),
        )
        await db.commit()


async def create_participant(full_name: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = _row_factory
        cur = await db.execute(
            "INSERT INTO participants (full_name) VALUES (?)", (full_name,)
        )
        await db.commit()
        pid = cur.lastrowid
        cur = await db.execute("SELECT * FROM participants WHERE id = ?", (pid,))
        return await cur.fetchone()


async def get_participant(pid: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = _row_factory
        cur = await db.execute("SELECT * FROM participants WHERE id = ?", (pid,))
        return await cur.fetchone()


async def search_participants(query: str) -> list[dict]:
    needle = query.strip().casefold()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = _row_factory
        cur = await db.execute(
            "SELECT * FROM participants ORDER BY id"
        )
        rows = await cur.fetchall()
    if not needle:
        return []
    matched = [r for r in rows if needle in (r["full_name"] or "").casefold()]
    return matched[:200]


async def find_exact_name(full_name: str) -> list[dict]:
    needle = full_name.strip().casefold()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = _row_factory
        cur = await db.execute("SELECT * FROM participants ORDER BY id")
        rows = await cur.fetchall()
    return [r for r in rows if (r["full_name"] or "").casefold() == needle]


async def add_points(pid: int, delta: int, staff_tg_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = _row_factory
        cur = await db.execute("SELECT * FROM participants WHERE id = ?", (pid,))
        row = await cur.fetchone()
        if not row:
            return None
        new_points = row["points"] + delta
        if new_points < 0:
            new_points = 0
        await db.execute(
            "UPDATE participants SET points = ? WHERE id = ?", (new_points, pid)
        )
        await db.execute(
            """
            INSERT INTO point_log (participant_id, delta, staff_tg_id)
            VALUES (?, ?, ?)
            """,
            (pid, delta, staff_tg_id),
        )
        await db.commit()
        cur = await db.execute("SELECT * FROM participants WHERE id = ?", (pid,))
        return await cur.fetchone()


async def set_points(pid: int, points: int, staff_tg_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = _row_factory
        cur = await db.execute("SELECT * FROM participants WHERE id = ?", (pid,))
        row = await cur.fetchone()
        if not row:
            return None
        points = max(0, points)
        delta = points - row["points"]
        await db.execute(
            "UPDATE participants SET points = ? WHERE id = ?", (points, pid)
        )
        if delta:
            await db.execute(
                """
                INSERT INTO point_log (participant_id, delta, staff_tg_id)
                VALUES (?, ?, ?)
                """,
                (pid, delta, staff_tg_id),
            )
        await db.commit()
        cur = await db.execute("SELECT * FROM participants WHERE id = ?", (pid,))
        return await cur.fetchone()


async def rename_participant(pid: int, full_name: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = _row_factory
        cur = await db.execute(
            "UPDATE participants SET full_name = ? WHERE id = ?",
            (full_name, pid),
        )
        await db.commit()
        if cur.rowcount == 0:
            return None
        cur = await db.execute("SELECT * FROM participants WHERE id = ?", (pid,))
        return await cur.fetchone()


async def delete_participant(pid: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = _row_factory
        cur = await db.execute("SELECT * FROM participants WHERE id = ?", (pid,))
        row = await cur.fetchone()
        if not row:
            return None
        await db.execute("DELETE FROM point_log WHERE participant_id = ?", (pid,))
        await db.execute("DELETE FROM participants WHERE id = ?", (pid,))
        await db.commit()
        return row


async def list_participants_by_points() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = _row_factory
        cur = await db.execute(
            """
            SELECT * FROM participants
            ORDER BY points DESC, id
            """
        )
        return await cur.fetchall()
