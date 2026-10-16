import aiosqlite
from datetime import datetime, timedelta

DB_NAME = "ftcl_bot.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id INTEGER PRIMARY KEY,
                expires_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                warnings INTEGER DEFAULT 0,
                is_blocked INTEGER DEFAULT 0
            )
        """)
        await db.commit()
        
        async with db.execute("SELECT value FROM settings WHERE key = 'ai_status'") as cursor:
            if not await cursor.fetchone():
                await db.execute("INSERT INTO settings (key, value) VALUES ('ai_status', '1')")
                await db.commit()

async def get_ai_status():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT value FROM settings WHERE key = 'ai_status'") as cursor:
            row = await cursor.fetchone()
            return row[0] == '1' if row else True

async def set_ai_status(status: bool):
    async with aiosqlite.connect(DB_NAME) as db:
        val = '1' if status else '0'
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('ai_status', ?)", (val,))
        await db.commit()

async def check_subscription(user_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT expires_at FROM subscriptions WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False
            return datetime.now() < datetime.fromisoformat(row[0])

async def grant_subscription(user_id: int, days: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT expires_at FROM subscriptions WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
        now = datetime.now()
        if row and datetime.fromisoformat(row[0]) > now:
            new_expires = datetime.fromisoformat(row[0]) + timedelta(days=days)
        else:
            new_expires = now + timedelta(days=days)
        await db.execute("INSERT OR REPLACE INTO subscriptions (user_id, expires_at) VALUES (?, ?)", (user_id, new_expires.isoformat()))
        await db.commit()

async def get_user_status(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT warnings, is_blocked FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await db.execute("INSERT INTO users (user_id, warnings, is_blocked) VALUES (?, 0, 0)", (user_id,))
                await db.commit()
                return 0, 0
            return row[0], row[1]

async def add_warning(user_id: int):
    warnings, is_blocked = await get_user_status(user_id)
    warnings += 1
    blocked = 1 if warnings >= 3 else 0
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO users (user_id, warnings, is_blocked) VALUES (?, ?, ?)", (user_id, warnings, blocked))
        await db.commit()
    return warnings, blocked == 1
