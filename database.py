"""
Database module for Ruhi Ji Bot
Handles PostgreSQL connection and operations with retry logic
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

import asyncpg
from asyncpg.pool import Pool

from config import DATABASE_URL, GROUP_MEMORY_LIMIT, PRIVATE_MEMORY_LIMIT, SESSION_TIMEOUT_MINUTES

logger = logging.getLogger(__name__)


class Database:
    """PostgreSQL database handler with connection pooling and retry logic"""
    
    def __init__(self):
        self.pool: Optional[Pool] = None
        self._retry_count = 3
        self._retry_delay = 1.0
    
    async def connect(self) -> None:
        """Initialize database connection pool with retry logic"""
        for attempt in range(self._retry_count):
            try:
                self.pool = await asyncpg.create_pool(
                    DATABASE_URL,
                    min_size=2,
                    max_size=10,
                    command_timeout=60,
                    statement_cache_size=0  # Disable statement caching for NeonDB compatibility
                )
                await self._create_tables()
                logger.info("Database connected successfully!")
                return
            except Exception as e:
                logger.error(f"Database connection attempt {attempt + 1} failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay * (attempt + 1))
                else:
                    raise
    
    async def disconnect(self) -> None:
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database disconnected")
    
    @asynccontextmanager
    async def get_connection(self):
        """Get a connection from pool with retry logic"""
        for attempt in range(self._retry_count):
            try:
                async with self.pool.acquire() as conn:
                    yield conn
                    return
            except Exception as e:
                logger.error(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                    # Try to reconnect pool if needed
                    if self.pool._closed:
                        await self.connect()
                else:
                    raise
    
    async def _create_tables(self) -> None:
        """Create all required database tables"""
        async with self.get_connection() as conn:
            # Users table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    role VARCHAR(50) DEFAULT 'user',
                    mood VARCHAR(50) DEFAULT 'neutral',
                    preferred_lang VARCHAR(10) DEFAULT 'hinglish',
                    is_banned BOOLEAN DEFAULT FALSE,
                    message_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Chats table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS chats (
                    chat_id BIGINT PRIMARY KEY,
                    chat_type VARCHAR(50),
                    chat_title VARCHAR(255),
                    active_session_expiry TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Messages table (for sliding window memory)
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    chat_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    message_text TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (chat_id) REFERENCES chats(chat_id) ON DELETE CASCADE
                )
            ''')
            
            # Create index for faster message queries
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_messages_chat_timestamp 
                ON messages(chat_id, timestamp DESC)
            ''')
            
            # Settings table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key VARCHAR(255) PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Bad words table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS bad_words (
                    id SERIAL PRIMARY KEY,
                    word VARCHAR(255) UNIQUE NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Initialize default settings
            await conn.execute('''
                INSERT INTO settings (key, value) 
                VALUES ('bot_mood', 'savage')
                ON CONFLICT (key) DO NOTHING
            ''')
            
            logger.info("Database tables created/verified successfully")
    
    # ==================== USER OPERATIONS ====================
    
    async def get_or_create_user(self, user_id: int, username: str = None, 
                                  first_name: str = None) -> Dict[str, Any]:
        """Get or create a user record"""
        async with self.get_connection() as conn:
            user = await conn.fetchrow(
                'SELECT * FROM users WHERE user_id = $1', user_id
            )
            
            if user:
                # Update last active and username if changed
                await conn.execute('''
                    UPDATE users 
                    SET last_active = CURRENT_TIMESTAMP,
                        username = COALESCE($2, username),
                        first_name = COALESCE($3, first_name)
                    WHERE user_id = $1
                ''', user_id, username, first_name)
                return dict(user)
            else:
                # Create new user
                await conn.execute('''
                    INSERT INTO users (user_id, username, first_name)
                    VALUES ($1, $2, $3)
                ''', user_id, username, first_name)
                return {
                    'user_id': user_id,
                    'username': username,
                    'first_name': first_name,
                    'role': 'user',
                    'mood': 'neutral',
                    'preferred_lang': 'hinglish',
                    'is_banned': False,
                    'message_count': 0
                }
    
    async def is_user_banned(self, user_id: int) -> bool:
        """Check if user is banned"""
        async with self.get_connection() as conn:
            result = await conn.fetchval(
                'SELECT is_banned FROM users WHERE user_id = $1', user_id
            )
            return result or False
    
    async def ban_user(self, user_id: int) -> bool:
        """Ban a user"""
        async with self.get_connection() as conn:
            result = await conn.execute(
                'UPDATE users SET is_banned = TRUE WHERE user_id = $1', user_id
            )
            return 'UPDATE 1' in result
    
    async def unban_user(self, user_id: int) -> bool:
        """Unban a user"""
        async with self.get_connection() as conn:
            result = await conn.execute(
                'UPDATE users SET is_banned = FALSE WHERE user_id = $1', user_id
            )
            return 'UPDATE 1' in result
    
    async def get_user_stats(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user statistics"""
        async with self.get_connection() as conn:
            user = await conn.fetchrow('''
                SELECT user_id, username, first_name, role, mood, 
                       preferred_lang, message_count, created_at, last_active
                FROM users WHERE user_id = $1
            ''', user_id)
            return dict(user) if user else None
    
    async def increment_message_count(self, user_id: int) -> None:
        """Increment user's message count"""
        async with self.get_connection() as conn:
            await conn.execute('''
                UPDATE users 
                SET message_count = message_count + 1,
                    last_active = CURRENT_TIMESTAMP
                WHERE user_id = $1
            ''', user_id)
    
    async def get_total_users(self) -> int:
        """Get total user count"""
        async with self.get_connection() as conn:
            return await conn.fetchval('SELECT COUNT(*) FROM users')
    
    async def get_active_users(self, hours: int = 24) -> int:
        """Get active users in last N hours"""
        async with self.get_connection() as conn:
            return await conn.fetchval('''
                SELECT COUNT(*) FROM users 
                WHERE last_active > CURRENT_TIMESTAMP - INTERVAL '%s hours'
            ''' % hours)
    
    async def get_all_user_ids(self) -> List[int]:
        """Get all user IDs for broadcast"""
        async with self.get_connection() as conn:
            rows = await conn.fetch(
                'SELECT user_id FROM users WHERE is_banned = FALSE'
            )
            return [row['user_id'] for row in rows]
    
    async def update_user_lang(self, user_id: int, lang: str) -> None:
        """Update user's preferred language"""
        async with self.get_connection() as conn:
            await conn.execute(
                'UPDATE users SET preferred_lang = $2 WHERE user_id = $1',
                user_id, lang
            )
    
    # ==================== CHAT OPERATIONS ====================
    
    async def get_or_create_chat(self, chat_id: int, chat_type: str, 
                                  chat_title: str = None) -> Dict[str, Any]:
        """Get or create a chat record"""
        async with self.get_connection() as conn:
            chat = await conn.fetchrow(
                'SELECT * FROM chats WHERE chat_id = $1', chat_id
            )
            
            if chat:
                await conn.execute('''
                    UPDATE chats 
                    SET last_active = CURRENT_TIMESTAMP,
                        chat_title = COALESCE($2, chat_title)
                    WHERE chat_id = $1
                ''', chat_id, chat_title)
                return dict(chat)
            else:
                await conn.execute('''
                    INSERT INTO chats (chat_id, chat_type, chat_title)
                    VALUES ($1, $2, $3)
                ''', chat_id, chat_type, chat_title)
                return {
                    'chat_id': chat_id,
                    'chat_type': chat_type,
                    'chat_title': chat_title,
                    'active_session_expiry': None,
                    'is_active': True
                }
    
    async def is_session_active(self, chat_id: int) -> bool:
        """Check if chat has an active session"""
        async with self.get_connection() as conn:
            expiry = await conn.fetchval(
                'SELECT active_session_expiry FROM chats WHERE chat_id = $1',
                chat_id
            )
            if expiry and expiry > datetime.utcnow():
                return True
            return False
    
    async def activate_session(self, chat_id: int) -> None:
        """Activate a 10-minute session for the chat"""
        expiry = datetime.utcnow() + timedelta(minutes=SESSION_TIMEOUT_MINUTES)
        async with self.get_connection() as conn:
            await conn.execute('''
                UPDATE chats 
                SET active_session_expiry = $2
                WHERE chat_id = $1
            ''', chat_id, expiry)
    
    async def deactivate_session(self, chat_id: int) -> None:
        """Deactivate session for the chat"""
        async with self.get_connection() as conn:
            await conn.execute('''
                UPDATE chats 
                SET active_session_expiry = NULL
                WHERE chat_id = $1
            ''', chat_id)
    
    async def get_all_chat_ids(self) -> List[int]:
        """Get all chat IDs for broadcast"""
        async with self.get_connection() as conn:
            rows = await conn.fetch(
                'SELECT chat_id FROM chats WHERE is_active = TRUE'
            )
            return [row['chat_id'] for row in rows]
    
    # ==================== MESSAGE OPERATIONS ====================
    
    async def save_message(self, chat_id: int, user_id: int, role: str, 
                           message_text: str) -> None:
        """Save a message to the conversation history"""
        async with self.get_connection() as conn:
            # Insert the new message
            await conn.execute('''
                INSERT INTO messages (chat_id, user_id, role, message_text)
                VALUES ($1, $2, $3, $4)
            ''', chat_id, user_id, role, message_text)
            
            # Get chat type to determine limit
            chat = await conn.fetchrow(
                'SELECT chat_type FROM chats WHERE chat_id = $1', chat_id
            )
            
            limit = PRIVATE_MEMORY_LIMIT if chat and chat['chat_type'] == 'private' else GROUP_MEMORY_LIMIT
            
            # Enforce sliding window - delete old messages beyond limit
            await conn.execute('''
                DELETE FROM messages 
                WHERE chat_id = $1 
                AND id NOT IN (
                    SELECT id FROM messages 
                    WHERE chat_id = $1 
                    ORDER BY timestamp DESC 
                    LIMIT $2
                )
            ''', chat_id, limit)
    
    async def get_conversation_history(self, chat_id: int) -> List[Dict[str, str]]:
        """Get conversation history for a chat (sliding window)"""
        async with self.get_connection() as conn:
            # Get chat type to determine limit
            chat = await conn.fetchrow(
                'SELECT chat_type FROM chats WHERE chat_id = $1', chat_id
            )
            
            limit = PRIVATE_MEMORY_LIMIT if chat and chat['chat_type'] == 'private' else GROUP_MEMORY_LIMIT
            
            rows = await conn.fetch('''
                SELECT role, message_text FROM messages
                WHERE chat_id = $1
                ORDER BY timestamp ASC
                LIMIT $2
            ''', chat_id, limit)
            
            return [{'role': row['role'], 'content': row['message_text']} for row in rows]
    
    async def clear_conversation(self, chat_id: int) -> None:
        """Clear conversation history for a chat"""
        async with self.get_connection() as conn:
            await conn.execute(
                'DELETE FROM messages WHERE chat_id = $1', chat_id
            )
    
    async def clear_user_context(self, user_id: int) -> int:
        """Clear all messages from a specific user across all chats"""
        async with self.get_connection() as conn:
            result = await conn.execute(
                'DELETE FROM messages WHERE user_id = $1', user_id
            )
            # Extract number of deleted rows
            return int(result.split()[-1]) if result else 0
    
    async def get_recent_messages_summary(self, chat_id: int, limit: int = 10) -> str:
        """Get recent messages for summary generation"""
        async with self.get_connection() as conn:
            rows = await conn.fetch('''
                SELECT role, message_text, timestamp FROM messages
                WHERE chat_id = $1
                ORDER BY timestamp DESC
                LIMIT $2
            ''', chat_id, limit)
            
            if not rows:
                return "No recent messages found."
            
            summary_parts = []
            for row in reversed(rows):
                role = "User" if row['role'] == 'user' else "Ruhi Ji"
                summary_parts.append(f"{role}: {row['message_text'][:100]}")
            
            return "\n".join(summary_parts)
    
    # ==================== SETTINGS OPERATIONS ====================
    
    async def get_setting(self, key: str) -> Optional[str]:
        """Get a setting value"""
        async with self.get_connection() as conn:
            return await conn.fetchval(
                'SELECT value FROM settings WHERE key = $1', key
            )
    
    async def set_setting(self, key: str, value: str) -> None:
        """Set a setting value"""
        async with self.get_connection() as conn:
            await conn.execute('''
                INSERT INTO settings (key, value, updated_at)
                VALUES ($1, $2, CURRENT_TIMESTAMP)
                ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = CURRENT_TIMESTAMP
            ''', key, value)
    
    async def get_bot_mood(self) -> str:
        """Get current bot mood"""
        mood = await self.get_setting('bot_mood')
        return mood or 'savage'
    
    # ==================== BAD WORDS OPERATIONS ====================
    
    async def add_bad_word(self, word: str) -> bool:
        """Add a word to the bad words filter"""
        async with self.get_connection() as conn:
            try:
                await conn.execute(
                    'INSERT INTO bad_words (word) VALUES ($1)', word.lower()
                )
                return True
            except asyncpg.UniqueViolationError:
                return False
    
    async def remove_bad_word(self, word: str) -> bool:
        """Remove a word from the bad words filter"""
        async with self.get_connection() as conn:
            result = await conn.execute(
                'DELETE FROM bad_words WHERE word = $1', word.lower()
            )
            return 'DELETE 1' in result
    
    async def get_bad_words(self) -> List[str]:
        """Get all bad words"""
        async with self.get_connection() as conn:
            rows = await conn.fetch('SELECT word FROM bad_words')
            return [row['word'] for row in rows]
    
    async def contains_bad_word(self, text: str) -> bool:
        """Check if text contains any bad words"""
        bad_words = await self.get_bad_words()
        text_lower = text.lower()
        return any(word in text_lower for word in bad_words)


# Global database instance
db = Database()
