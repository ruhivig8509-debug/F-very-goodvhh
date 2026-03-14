"""
database.py - PostgreSQL Connection Pool & Table Management for Ruhi Ji Bot
Handles all persistent storage: users, chats, messages, settings, admin roles.
Implements retry logic and connection pooling for Neon.tech resilience.
"""

import os
import time
import logging
import psycopg2
import psycopg2.pool
import psycopg2.extras
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection Pool Singleton
# ---------------------------------------------------------------------------

_pool = None
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


def get_pool():
    """Return (and lazily create) the global connection-pool."""
    global _pool
    if _pool is None or _pool.closed:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL environment variable is not set")
        for attempt in range(MAX_RETRIES):
            try:
                _pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=2,
                    maxconn=10,
                    dsn=database_url,
                    connect_timeout=10,
                )
                logger.info("PostgreSQL connection pool created successfully.")
                return _pool
            except psycopg2.OperationalError as exc:
                logger.warning(
                    "DB pool creation attempt %d/%d failed: %s",
                    attempt + 1,
                    MAX_RETRIES,
                    exc,
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    raise
    return _pool


@contextmanager
def get_connection():
    """Context manager that borrows a connection from the pool,
    commits on success, rolls back on error, and always returns
    the connection to the pool."""
    pool = get_pool()
    conn = None
    for attempt in range(MAX_RETRIES):
        try:
            conn = pool.getconn()
            conn.autocommit = False
            yield conn
            conn.commit()
            break
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as exc:
            logger.warning("DB connection error (attempt %d): %s", attempt + 1, exc)
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
                try:
                    pool.putconn(conn, close=True)
                except Exception:
                    pass
                conn = None
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
                # Force pool refresh
                global _pool
                _pool = None
                pool = get_pool()
            else:
                raise
        except Exception:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        finally:
            if conn is not None:
                try:
                    pool.putconn(conn)
                except Exception:
                    pass


def _exec(query: str, params=None, fetch=False, fetchone=False):
    """Helper that executes a query with full retry logic."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            if fetchone:
                return cur.fetchone()
            if fetch:
                return cur.fetchall()
            return None


# ---------------------------------------------------------------------------
# Schema Initialization
# ---------------------------------------------------------------------------

def init_db():
    """Create all required tables if they don't exist."""
    schema = """
    CREATE TABLE IF NOT EXISTS users (
        user_id         BIGINT PRIMARY KEY,
        username        TEXT,
        first_name      TEXT,
        role            TEXT DEFAULT 'user',
        preferred_lang  TEXT DEFAULT 'hinglish',
        mood            TEXT DEFAULT 'default',
        is_banned       BOOLEAN DEFAULT FALSE,
        first_seen      TIMESTAMPTZ DEFAULT NOW(),
        last_active     TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS chats (
        chat_id                 BIGINT PRIMARY KEY,
        chat_type               TEXT DEFAULT 'private',
        title                   TEXT,
        active_session_expiry   TIMESTAMPTZ,
        added_at                TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS messages (
        id          BIGSERIAL PRIMARY KEY,
        chat_id     BIGINT NOT NULL,
        user_id     BIGINT,
        role        TEXT NOT NULL DEFAULT 'user',
        message_text TEXT NOT NULL,
        created_at  TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_messages_chat_id_created
        ON messages (chat_id, created_at DESC);

    CREATE TABLE IF NOT EXISTS settings (
        key     TEXT PRIMARY KEY,
        value   TEXT
    );

    CREATE TABLE IF NOT EXISTS bad_words (
        id      SERIAL PRIMARY KEY,
        word    TEXT UNIQUE NOT NULL
    );

    -- Seed default settings if empty
    INSERT INTO settings (key, value)
    VALUES ('bot_mood', 'savage')
    ON CONFLICT (key) DO NOTHING;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(schema)
    logger.info("Database schema initialized.")


# ---------------------------------------------------------------------------
# User Operations
# ---------------------------------------------------------------------------

def upsert_user(user_id: int, username: str = None, first_name: str = None):
    _exec(
        """
        INSERT INTO users (user_id, username, first_name, last_active)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (user_id) DO UPDATE
            SET username    = COALESCE(EXCLUDED.username, users.username),
                first_name  = COALESCE(EXCLUDED.first_name, users.first_name),
                last_active = NOW();
        """,
        (user_id, username, first_name),
    )


def get_user(user_id: int):
    return _exec("SELECT * FROM users WHERE user_id = %s;", (user_id,), fetchone=True)


def set_user_banned(user_id: int, banned: bool):
    _exec("UPDATE users SET is_banned = %s WHERE user_id = %s;", (banned, user_id))


def is_user_banned(user_id: int) -> bool:
    row = _exec("SELECT is_banned FROM users WHERE user_id = %s;", (user_id,), fetchone=True)
    return row["is_banned"] if row else False


def set_user_lang(user_id: int, lang: str):
    _exec("UPDATE users SET preferred_lang = %s WHERE user_id = %s;", (lang, user_id))


def get_total_users() -> int:
    row = _exec("SELECT COUNT(*) AS cnt FROM users;", fetchone=True)
    return row["cnt"] if row else 0


def get_active_users(minutes: int = 60) -> int:
    row = _exec(
        "SELECT COUNT(*) AS cnt FROM users WHERE last_active > NOW() - INTERVAL '%s minutes';",
        (minutes,),
        fetchone=True,
    )
    return row["cnt"] if row else 0


def get_all_chat_ids():
    rows = _exec("SELECT chat_id FROM chats;", fetch=True)
    return [r["chat_id"] for r in rows] if rows else []


def get_user_role(user_id: int) -> str:
    row = _exec("SELECT role FROM users WHERE user_id = %s;", (user_id,), fetchone=True)
    return row["role"] if row else "user"


# ---------------------------------------------------------------------------
# Chat / Session Operations
# ---------------------------------------------------------------------------

def upsert_chat(chat_id: int, chat_type: str = "private", title: str = None):
    _exec(
        """
        INSERT INTO chats (chat_id, chat_type, title)
        VALUES (%s, %s, %s)
        ON CONFLICT (chat_id) DO UPDATE
            SET chat_type = EXCLUDED.chat_type,
                title     = COALESCE(EXCLUDED.title, chats.title);
        """,
        (chat_id, chat_type, title),
    )


def activate_session(chat_id: int, duration_minutes: int = 10):
    expiry = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
    _exec(
        "UPDATE chats SET active_session_expiry = %s WHERE chat_id = %s;",
        (expiry, chat_id),
    )


def is_session_active(chat_id: int) -> bool:
    row = _exec(
        "SELECT active_session_expiry FROM chats WHERE chat_id = %s;",
        (chat_id,),
        fetchone=True,
    )
    if not row or row["active_session_expiry"] is None:
        return False
    return row["active_session_expiry"] > datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Message / Memory Operations
# ---------------------------------------------------------------------------

def store_message(chat_id: int, user_id: int, role: str, text: str):
    """Store a message and enforce the sliding window limit."""
    _exec(
        "INSERT INTO messages (chat_id, user_id, role, message_text) VALUES (%s, %s, %s, %s);",
        (chat_id, user_id, role, text),
    )
    # Determine limit based on chat type
    chat = _exec("SELECT chat_type FROM chats WHERE chat_id = %s;", (chat_id,), fetchone=True)
    limit = 50 if (chat and chat["chat_type"] == "private") else 20
    # Prune messages beyond the sliding window — keep only the newest `limit` rows
    _exec(
        """
        DELETE FROM messages
        WHERE chat_id = %s
          AND id NOT IN (
              SELECT id FROM messages
              WHERE chat_id = %s
              ORDER BY created_at DESC
              LIMIT %s
          );
        """,
        (chat_id, chat_id, limit),
    )


def get_chat_history(chat_id: int) -> list:
    """Return messages ordered oldest->newest for the sliding window."""
    chat = _exec("SELECT chat_type FROM chats WHERE chat_id = %s;", (chat_id,), fetchone=True)
    limit = 50 if (chat and chat["chat_type"] == "private") else 20
    rows = _exec(
        """
        SELECT role, message_text, user_id
        FROM messages
        WHERE chat_id = %s
        ORDER BY created_at DESC
        LIMIT %s;
        """,
        (chat_id, limit),
        fetch=True,
    )
    if not rows:
        return []
    rows.reverse()  # oldest first
    return rows


def clear_chat_history(chat_id: int):
    _exec("DELETE FROM messages WHERE chat_id = %s;", (chat_id,))


def clear_user_history(user_id: int):
    _exec("DELETE FROM messages WHERE user_id = %s;", (user_id,))


# ---------------------------------------------------------------------------
# Settings / Bad-Words Operations
# ---------------------------------------------------------------------------

def get_setting(key: str) -> str | None:
    row = _exec("SELECT value FROM settings WHERE key = %s;", (key,), fetchone=True)
    return row["value"] if row else None


def set_setting(key: str, value: str):
    _exec(
        "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;",
        (key, value),
    )


def get_bad_words() -> list[str]:
    rows = _exec("SELECT word FROM bad_words;", fetch=True)
    return [r["word"] for r in rows] if rows else []


def add_bad_word(word: str):
    _exec(
        "INSERT INTO bad_words (word) VALUES (%s) ON CONFLICT (word) DO NOTHING;",
        (word.lower(),),
    )


def remove_bad_word(word: str):
    _exec("DELETE FROM bad_words WHERE word = %s;", (word.lower(),))
