"""
database.py — Ruhi Ji Bot
PostgreSQL via asyncpg (NeonDB compatible)
"""

import asyncio
import asyncpg
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from config import DATABASE_URL, GROUP_MEMORY_SIZE, PRIVATE_MEMORY_SIZE

logger = logging.getLogger(__name__)
pool: Optional[asyncpg.Pool] = None


# ─────────────────────────────────────────────────────────────
#  POOL MANAGEMENT
# ─────────────────────────────────────────────────────────────

async def create_pool() -> asyncpg.Pool:
    """Create DB connection pool with retry logic for NeonDB cold-starts."""
    global pool
    for attempt in range(5):
        try:
            pool = await asyncpg.create_pool(
                DATABASE_URL,
                min_size=1,
                max_size=5,
                command_timeout=30,
                ssl="require",
            )
            await _create_tables()
            logger.info("✅ Database connected successfully.")
            return pool
        except Exception as e:
            logger.warning(f"DB connect attempt {attempt + 1}/5 failed: {e}")
            if attempt < 4:
                await asyncio.sleep(3 * (attempt + 1))
    raise RuntimeError("❌ Could not connect to PostgreSQL after 5 attempts.")


async def close_pool():
    global pool
    if pool:
        await pool.close()
        logger.info("DB pool closed.")


async def _execute(query: str, *args, fetch: str = "none") -> Any:
    """Safe wrapper around pool queries with auto-retry on connection loss."""
    global pool
    for attempt in range(3):
        try:
            async with pool.acquire() as conn:
                if fetch == "row":
                    return await conn.fetchrow(query, *args)
                elif fetch == "all":
                    return await conn.fetch(query, *args)
                elif fetch == "val":
                    return await conn.fetchval(query, *args)
                else:
                    return await conn.execute(query, *args)
        except (asyncpg.PostgresConnectionError, asyncpg.TooManyConnectionsError) as e:
            logger.warning(f"DB retry {attempt + 1}/3: {e}")
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"DB error: {e}")
            raise
    raise RuntimeError("DB not reachable after retries.")


# ─────────────────────────────────────────────────────────────
#  TABLE CREATION
# ─────────────────────────────────────────────────────────────

async def _create_tables():
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     BIGINT  PRIMARY KEY,
                username    TEXT,
                full_name   TEXT,
                role        TEXT    DEFAULT 'user',
                lang_pref   TEXT    DEFAULT 'hinglish',
                is_banned   BOOLEAN DEFAULT FALSE,
                msg_count   INTEGER DEFAULT 0,
                first_seen  TIMESTAMP DEFAULT NOW(),
                last_seen   TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS admins (
                user_id    BIGINT PRIMARY KEY,
                username   TEXT,
                added_at   TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS chats (
                chat_id               BIGINT PRIMARY KEY,
                chat_type             TEXT,
                active_session_expiry TIMESTAMP,
                created_at            TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS messages (
                id           SERIAL PRIMARY KEY,
                chat_id      BIGINT   NOT NULL,
                user_id      BIGINT,
                role         TEXT     NOT NULL,
                message_text TEXT     NOT NULL,
                timestamp    TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id, timestamp DESC);
        """)

        # Seed default settings
        await conn.execute("""
            INSERT INTO settings (key, value) VALUES
                ('bad_words',     ''),
                ('bot_mood',      'savage'),
                ('bot_active',    'true'),
                ('trigger_phrase','ruhi ji')
            ON CONFLICT (key) DO NOTHING;
        """)

        # ── MIGRATIONS — safely add missing columns to existing tables ──
        migrations = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS username   TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name  TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS role       TEXT    DEFAULT 'user'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS lang_pref  TEXT    DEFAULT 'hinglish'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned  BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS msg_count  INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS first_seen TIMESTAMP DEFAULT NOW()",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen  TIMESTAMP DEFAULT NOW()",
            "ALTER TABLE admins ADD COLUMN IF NOT EXISTS username  TEXT",
            "ALTER TABLE admins ADD COLUMN IF NOT EXISTS added_at  TIMESTAMP DEFAULT NOW()",
            "ALTER TABLE chats ADD COLUMN IF NOT EXISTS chat_type             TEXT",
            "ALTER TABLE chats ADD COLUMN IF NOT EXISTS active_session_expiry TIMESTAMP",
            "ALTER TABLE chats ADD COLUMN IF NOT EXISTS created_at            TIMESTAMP DEFAULT NOW()",
        ]
        for sql in migrations:
            await conn.execute(sql)
        logger.info("✅ DB migrations applied.")


# ─────────────────────────────────────────────────────────────
#  USER HELPERS
# ─────────────────────────────────────────────────────────────

async def upsert_user(user_id: int, username: str, full_name: str):
    await _execute("""
        INSERT INTO users (user_id, username, full_name, last_seen)
        VALUES ($1, $2, $3, NOW())
        ON CONFLICT (user_id) DO UPDATE
            SET username  = EXCLUDED.username,
                full_name = EXCLUDED.full_name,
                last_seen = NOW();
    """, user_id, username or "", full_name or "")


async def get_user(user_id: int) -> Optional[asyncpg.Record]:
    return await _execute("SELECT * FROM users WHERE user_id = $1", user_id, fetch="row")


async def increment_msg_count(user_id: int):
    await _execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = $1", user_id)


async def set_user_lang(user_id: int, lang: str):
    await _execute("UPDATE users SET lang_pref = $1 WHERE user_id = $2", lang, user_id)


async def is_banned(user_id: int) -> bool:
    val = await _execute("SELECT is_banned FROM users WHERE user_id = $1", user_id, fetch="val")
    return bool(val)


async def ban_user(user_id: int):
    await _execute("UPDATE users SET is_banned = TRUE WHERE user_id = $1", user_id)


async def unban_user(user_id: int):
    await _execute("UPDATE users SET is_banned = FALSE WHERE user_id = $1", user_id)


async def get_total_users() -> int:
    return await _execute("SELECT COUNT(*) FROM users", fetch="val") or 0


async def get_active_users(days: int = 7) -> int:
    # FIX: was missing $1 param, always used hardcoded 7 days
    cutoff = datetime.utcnow() - timedelta(days=days)
    return await _execute(
        "SELECT COUNT(*) FROM users WHERE last_seen > $1",
        cutoff, fetch="val"
    ) or 0


async def get_all_user_ids() -> List[int]:
    rows = await _execute("SELECT user_id FROM users", fetch="all")
    return [r["user_id"] for r in rows] if rows else []


# ─────────────────────────────────────────────────────────────
#  ADMIN HELPERS
# ─────────────────────────────────────────────────────────────

async def add_admin(user_id: int, username: str):
    await _execute("""
        INSERT INTO admins (user_id, username) VALUES ($1, $2)
        ON CONFLICT (user_id) DO NOTHING;
    """, user_id, username or "")


async def remove_admin(user_id: int):
    await _execute("DELETE FROM admins WHERE user_id = $1", user_id)


async def is_admin(user_id: int) -> bool:
    val = await _execute("SELECT user_id FROM admins WHERE user_id = $1", user_id, fetch="val")
    return val is not None


async def get_admin_list() -> List[asyncpg.Record]:
    return await _execute("SELECT * FROM admins", fetch="all") or []


# ─────────────────────────────────────────────────────────────
#  CHAT / SESSION HELPERS
# ─────────────────────────────────────────────────────────────

async def upsert_chat(chat_id: int, chat_type: str):
    await _execute("""
        INSERT INTO chats (chat_id, chat_type)
        VALUES ($1, $2)
        ON CONFLICT (chat_id) DO NOTHING;
    """, chat_id, chat_type)


async def set_session(chat_id: int, minutes: int = 10):
    expiry = datetime.utcnow() + timedelta(minutes=minutes)
    await _execute("""
        INSERT INTO chats (chat_id, chat_type, active_session_expiry)
        VALUES ($1, 'group', $2)
        ON CONFLICT (chat_id) DO UPDATE SET active_session_expiry = EXCLUDED.active_session_expiry;
    """, chat_id, expiry)


async def is_session_active(chat_id: int) -> bool:
    expiry = await _execute(
        "SELECT active_session_expiry FROM chats WHERE chat_id = $1",
        chat_id, fetch="val"
    )
    if not expiry:
        return False
    return datetime.utcnow() < expiry


async def clear_session(chat_id: int):
    await _execute(
        "UPDATE chats SET active_session_expiry = NULL WHERE chat_id = $1",
        chat_id
    )


# ─────────────────────────────────────────────────────────────
#  MESSAGE / MEMORY HELPERS
# ─────────────────────────────────────────────────────────────

async def add_message(chat_id: int, user_id: Optional[int], role: str, text: str):
    await _execute("""
        INSERT INTO messages (chat_id, user_id, role, message_text)
        VALUES ($1, $2, $3, $4);
    """, chat_id, user_id, role, text)


async def get_history(chat_id: int, chat_type: str) -> List[Dict[str, str]]:
    """Return sliding-window history as list of {role, content} dicts for LLM."""
    limit = PRIVATE_MEMORY_SIZE if chat_type == "private" else GROUP_MEMORY_SIZE
    rows = await _execute("""
        SELECT role, message_text
        FROM (
            SELECT role, message_text, timestamp
            FROM messages
            WHERE chat_id = $1
            ORDER BY timestamp DESC
            LIMIT $2
        ) sub
        ORDER BY timestamp ASC;
    """, chat_id, limit, fetch="all")
    if not rows:
        return []
    return [{"role": r["role"], "content": r["message_text"]} for r in rows]


async def clear_history(chat_id: int):
    await _execute("DELETE FROM messages WHERE chat_id = $1", chat_id)


async def clear_user_history(user_id: int):
    await _execute("DELETE FROM messages WHERE user_id = $1", user_id)


# ─────────────────────────────────────────────────────────────
#  SETTINGS HELPERS
# ─────────────────────────────────────────────────────────────

async def get_setting(key: str) -> Optional[str]:
    return await _execute("SELECT value FROM settings WHERE key = $1", key, fetch="val")


async def set_setting(key: str, value: str):
    await _execute("""
        INSERT INTO settings (key, value) VALUES ($1, $2)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
    """, key, value)


async def get_bad_words() -> List[str]:
    val = await get_setting("bad_words")
    if not val:
        return []
    return [w.strip().lower() for w in val.split(",") if w.strip()]


async def add_bad_word(word: str):
    words = await get_bad_words()
    words.append(word.lower().strip())
    await set_setting("bad_words", ",".join(set(words)))


async def remove_bad_word(word: str):
    words = await get_bad_words()
    words = [w for w in words if w != word.lower().strip()]
    await set_setting("bad_words", ",".join(words))
