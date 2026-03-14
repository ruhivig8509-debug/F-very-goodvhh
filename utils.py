"""
Utility functions for Ruhi Ji Bot
"""

import re
import logging
from typing import Optional
from datetime import datetime

from config import OWNER_USERNAME

logger = logging.getLogger(__name__)


def is_owner(username: str) -> bool:
    """Check if user is the owner"""
    if not username:
        return False
    return username.lower() == OWNER_USERNAME.lower()


def contains_wake_phrase(text: str) -> bool:
    """Check if message contains the wake phrase 'Ruhi Ji'"""
    if not text:
        return False
    
    # Case insensitive check for various spellings
    wake_patterns = [
        r'\bruhi\s*ji\b',
        r'\bruhi\s*g\b',
        r'\bruhiji\b',
        r'\bruhi\b.*\bji\b',
    ]
    
    text_lower = text.lower()
    for pattern in wake_patterns:
        if re.search(pattern, text_lower):
            return True
    return False


def format_timestamp(dt: datetime) -> str:
    """Format datetime for display"""
    if not dt:
        return "N/A"
    return dt.strftime("%Y-%m-%d %H:%M")


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to max length with ellipsis"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def sanitize_username(username: str) -> str:
    """Sanitize username for display"""
    if not username:
        return "Unknown"
    # Remove @ if present
    return username.lstrip('@')


def extract_user_id(text: str) -> Optional[int]:
    """Extract user ID from command arguments"""
    try:
        # Try to find a number in the text
        match = re.search(r'\b(\d{5,})\b', text)
        if match:
            return int(match.group(1))
        return None
    except (ValueError, AttributeError):
        return None


def format_profile(user_data: dict) -> str:
    """Format user profile for display"""
    return f"""╭───────────────────⦿
│ 📊 ʏᴏᴜʀ ᴘʀᴏғɪʟᴇ
├───────────────────⦿
│ ▸ ɴᴀᴍᴇ: {user_data.get('first_name', 'Unknown')}
│ ▸ ᴜsᴇʀɴᴀᴍᴇ: @{user_data.get('username', 'N/A')}
│ ▸ ʀᴏʟᴇ: {user_data.get('role', 'user').upper()}
│ ▸ ᴍᴏᴏᴅ: {user_data.get('mood', 'neutral')} 
│ ▸ ʟᴀɴɢ: {user_data.get('preferred_lang', 'hinglish')}
│ ▸ ᴍsɢs: {user_data.get('message_count', 0)}
│ ▸ ᴊᴏɪɴᴇᴅ: {format_timestamp(user_data.get('created_at'))}
│ ▸ ʟᴀsᴛ ᴀᴄᴛɪᴠᴇ: {format_timestamp(user_data.get('last_active'))}
╰───────────────────⦿"""


def format_stats(total_users: int, active_users: int, total_chats: int = 0) -> str:
    """Format bot statistics for display"""
    return f"""╭───────────────────⦿
│ 📈 ʙᴏᴛ sᴛᴀᴛs
├───────────────────⦿
│ ▸ ᴛᴏᴛᴀʟ ᴜsᴇʀs: {total_users}
│ ▸ ᴀᴄᴛɪᴠᴇ (24ʜ): {active_users}
│ ▸ ᴛᴏᴛᴀʟ ᴄʜᴀᴛs: {total_chats}
╰───────────────────⦿"""


def get_greeting_by_time() -> str:
    """Get appropriate greeting based on time of day"""
    hour = datetime.now().hour
    
    if 5 <= hour < 12:
        return "Good Morning ☀️"
    elif 12 <= hour < 17:
        return "Good Afternoon 🌤️"
    elif 17 <= hour < 21:
        return "Good Evening 🌅"
    else:
        return "Good Night 🌙"
