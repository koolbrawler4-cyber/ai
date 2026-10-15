import aiosqlite
from datetime import datetime, timedelta

DB_NAME = "ftcl_bot.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # Таблица пользователей и подписок
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                sub_expires TEXT,
                is_admin BOOLEAN DEFAULT 0
            )
        """)
        # Таблица глобальных настроек (включение/выключение ИИ)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS global_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        # Устанавливаем ИИ включенным по умолчанию (value = "1")
        await db.execute("""
            INSERT OR IGNORE INTO global_settings (key, value) VALUES ('ai_enabled', '1')
        """)
        await db.commit()

async def get_ai_status() -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT value FROM global_settings WHERE key = 'ai_enabled'") as cursor:
            row = await cursor.fetchone()
            return row[0] == "1" if row else True

async def set_ai_status(status: bool):
    val = "1" if status else "0"
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE global_settings SET value = ? WHERE key = 'ai_enabled'", (val,))
        await db.commit()

async def check_subscription(user_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT sub_expires, is_admin FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False
            sub_expires, is_admin = row
            if is_admin:
                return True
            if not sub_expires:
                return False
            return datetime.now() < datetime.fromisoformat(sub_expires)

async def grant_subscription(user_id: int, days: int):
    expire_date = datetime.now() + timedelta(days=days)
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO users (user_id, sub_expires) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET sub_expires = ?
        """, (user_id, expire_date.isoformat(), expire_date.isoformat()))
        await db.commit()
