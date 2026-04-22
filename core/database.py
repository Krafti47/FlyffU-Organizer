from __future__ import annotations

import aiosqlite
from enum import Enum
from typing import Optional

from config import DB_PATH


class RegisterResult(Enum):
    OK = "ok"
    WAITLISTED = "waitlisted"
    ALREADY_REGISTERED = "already_registered"
    ROLE_FULL = "role_full"


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type    TEXT NOT NULL CHECK(event_type IN ('pvp','pve')),
                title         TEXT NOT NULL,
                description   TEXT,
                event_date    TEXT NOT NULL,
                channel_id    INTEGER NOT NULL,
                message_id    INTEGER UNIQUE,
                creator_id    INTEGER NOT NULL,
                creator_name  TEXT,
                created_at    TEXT NOT NULL DEFAULT (datetime('now')),
                is_open       INTEGER NOT NULL DEFAULT 1,
                max_slots     INTEGER NOT NULL DEFAULT 15,
                slots_tank    INTEGER,
                slots_support INTEGER,
                slots_1v1     INTEGER,
                slots_aoe     INTEGER
            );

            CREATE TABLE IF NOT EXISTS registrations (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id      INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                user_id       INTEGER NOT NULL,
                user_name     TEXT NOT NULL,
                class_id      INTEGER NOT NULL,
                class_name    TEXT NOT NULL,
                role          TEXT CHECK(role IN ('Tank','Support','1v1','AOE')),
                is_waitlist   INTEGER NOT NULL DEFAULT 0,
                position      INTEGER NOT NULL,
                registered_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(event_id, user_id)
            );
        """)
        # Migrate existing databases that predate the creator_name column
        try:
            await db.execute("ALTER TABLE events ADD COLUMN creator_name TEXT")
        except Exception:
            pass
        await db.commit()


async def create_event(
    event_type: str,
    title: str,
    description: str,
    event_date: str,
    channel_id: int,
    creator_id: int,
    creator_name: str = "",
    max_slots: int = 15,
    slots_tank: Optional[int] = None,
    slots_support: Optional[int] = None,
    slots_1v1: Optional[int] = None,
    slots_aoe: Optional[int] = None,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO events
                (event_type, title, description, event_date, channel_id,
                 creator_id, creator_name, max_slots, slots_tank, slots_support, slots_1v1, slots_aoe)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (event_type, title, description, event_date, channel_id,
             creator_id, creator_name, max_slots, slots_tank, slots_support, slots_1v1, slots_aoe),
        )
        await db.commit()
        return cursor.lastrowid


async def update_event_message_id(event_id: int, message_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE events SET message_id = ? WHERE id = ?",
            (message_id, event_id),
        )
        await db.commit()


async def get_event_by_id(event_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM events WHERE id = ?", (event_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_event_by_message_id(message_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM events WHERE message_id = ?", (message_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_all_open_events() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM events WHERE is_open = 1 AND message_id IS NOT NULL"
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def close_event(event_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE events SET is_open = 0 WHERE id = ?", (event_id,))
        await db.commit()


async def delete_events_older_than_one_month() -> int:
    """Deletes events (and their registrations via CASCADE) older than 1 month. Returns count."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            DELETE FROM events
            WHERE datetime(event_date) < datetime('now', '-1 month')
            """
        )
        await db.commit()
        return cursor.rowcount


async def get_registrations(event_id: int) -> tuple[list[dict], list[dict]]:
    """Returns (confirmed, waitlist) sorted by position."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM registrations WHERE event_id = ? ORDER BY position ASC",
            (event_id,),
        ) as cur:
            rows = [dict(r) for r in await cur.fetchall()]
    confirmed = [r for r in rows if not r["is_waitlist"]]
    waitlist = [r for r in rows if r["is_waitlist"]]
    return confirmed, waitlist


async def is_user_registered(event_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM registrations WHERE event_id = ? AND user_id = ?",
            (event_id, user_id),
        ) as cur:
            return await cur.fetchone() is not None


async def _next_position(db: aiosqlite.Connection, event_id: int) -> int:
    async with db.execute(
        "SELECT COALESCE(MAX(position), 0) + 1 FROM registrations WHERE event_id = ?",
        (event_id,),
    ) as cur:
        row = await cur.fetchone()
        return row[0]


async def register_user(
    event_id: int,
    user_id: int,
    user_name: str,
    class_id: int,
    class_name: str,
    role: Optional[str] = None,
    force_bench: bool = False,
) -> RegisterResult:
    async with aiosqlite.connect(DB_PATH) as db:
        # Fetch event data
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM events WHERE id = ?", (event_id,)) as cur:
            event = dict(await cur.fetchone())

        # Count current confirmed registrations
        async with db.execute(
            "SELECT COUNT(*) FROM registrations WHERE event_id = ? AND is_waitlist = 0",
            (event_id,),
        ) as cur:
            confirmed_count = (await cur.fetchone())[0]

        is_waitlist = 0

        if force_bench:
            is_waitlist = 1
        elif event["event_type"] == "pvp":
            if confirmed_count >= event["max_slots"]:
                is_waitlist = 1
        else:
            # PVE: check per-role slot limit
            role_col = {"Tank": "slots_tank", "Support": "slots_support",
                        "1v1": "slots_1v1", "AOE": "slots_aoe"}.get(role)
            max_for_role = event.get(role_col) if role_col else 0

            if max_for_role is None or max_for_role == 0:
                return RegisterResult.ROLE_FULL

            async with db.execute(
                "SELECT COUNT(*) FROM registrations WHERE event_id = ? AND role = ? AND is_waitlist = 0",
                (event_id, role),
            ) as cur:
                role_count = (await cur.fetchone())[0]

            if role_count >= max_for_role:
                is_waitlist = 1

        position = await _next_position(db, event_id)

        try:
            await db.execute(
                """
                INSERT INTO registrations
                    (event_id, user_id, user_name, class_id, class_name, role, is_waitlist, position)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (event_id, user_id, user_name, class_id, class_name, role, is_waitlist, position),
            )
            await db.commit()
        except aiosqlite.IntegrityError:
            return RegisterResult.ALREADY_REGISTERED

        return RegisterResult.WAITLISTED if is_waitlist else RegisterResult.OK


async def unregister_user(event_id: int, user_id: int) -> bool:
    """
    Removes the user's registration. If the user was confirmed (not waitlisted)
    and there are waitlisted users, promotes the first one.
    Returns True if the user was found and removed, False if not registered.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM registrations WHERE event_id = ? AND user_id = ?",
            (event_id, user_id),
        ) as cur:
            reg = await cur.fetchone()

        if reg is None:
            return False

        reg = dict(reg)
        await db.execute(
            "DELETE FROM registrations WHERE event_id = ? AND user_id = ?",
            (event_id, user_id),
        )

        # Promote first waitlisted entry if the removed user was confirmed
        if not reg["is_waitlist"]:
            role_filter = reg["role"]
            if role_filter:
                # PVE: promote first waitlisted entry for the same role
                async with db.execute(
                    """
                    SELECT id FROM registrations
                    WHERE event_id = ? AND is_waitlist = 1 AND role = ?
                    ORDER BY position ASC LIMIT 1
                    """,
                    (event_id, role_filter),
                ) as cur:
                    next_row = await cur.fetchone()
            else:
                # PVP: promote first waitlisted entry regardless of role
                async with db.execute(
                    """
                    SELECT id FROM registrations
                    WHERE event_id = ? AND is_waitlist = 1
                    ORDER BY position ASC LIMIT 1
                    """,
                    (event_id,),
                ) as cur:
                    next_row = await cur.fetchone()

            if next_row:
                await db.execute(
                    "UPDATE registrations SET is_waitlist = 0 WHERE id = ?",
                    (next_row["id"],),
                )

        await db.commit()
        return True


async def get_role_slot_counts(event_id: int) -> dict[str, tuple[int, int]]:
    """Returns {role: (filled, max)} for a PVE event."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM events WHERE id = ?", (event_id,)) as cur:
            event = dict(await cur.fetchone())

    result = {}
    role_cols = {"Tank": "slots_tank", "Support": "slots_support",
                 "1v1": "slots_1v1", "AOE": "slots_aoe"}

    async with aiosqlite.connect(DB_PATH) as db:
        for role, col in role_cols.items():
            max_slots = event.get(col) or 0
            if max_slots == 0:
                continue
            async with db.execute(
                "SELECT COUNT(*) FROM registrations WHERE event_id = ? AND role = ? AND is_waitlist = 0",
                (event_id, role),
            ) as cur:
                filled = (await cur.fetchone())[0]
            result[role] = (filled, max_slots)

    return result
