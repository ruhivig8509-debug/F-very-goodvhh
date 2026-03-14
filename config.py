import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
#  TELEGRAM
# ─────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# ─────────────────────────────────────────────
#  OWNER
# ─────────────────────────────────────────────
OWNER_USERNAME: str = "RUHI_VIG_QNR"
OWNER_ID: int = int(os.getenv("OWNER_ID", "0"))

# ─────────────────────────────────────────────
#  DATABASE  (NeonDB — set in .env / Render env)
# ─────────────────────────────────────────────
DATABASE_URL: str = os.getenv("DATABASE_URL", "")

# ─────────────────────────────────────────────
#  LLM — HuggingFace Router → Kimi-K2 via Groq
# ─────────────────────────────────────────────
HF_TOKEN: str    = os.getenv("HF_TOKEN", "")
HF_BASE_URL: str = "https://router.huggingface.co/v1"
HF_MODEL: str    = "moonshotai/Kimi-K2-Instruct-0905:groq"

# ─────────────────────────────────────────────
#  BOT BEHAVIOUR
# ─────────────────────────────────────────────
WAKE_PHRASES: list[str] = ["ruhi ji", "ruhi", "रुही जी", "ruhi jii"]
SESSION_DURATION_MINUTES: int = 10
GROUP_MEMORY_SIZE: int = 20
PRIVATE_MEMORY_SIZE: int = 50
RATE_LIMIT_SECONDS: int = 3
MAX_LLM_CONTEXT_CHARS: int = 12_000
LLM_MAX_TOKENS: int = 512

# ─────────────────────────────────────────────
#  ASCII UI STRINGS
# ─────────────────────────────────────────────
START_ASCII = """╭───────────────────⦿
│ ▸ ʜᴇʏ 
│ ▸ ɪ ᴀᴍ ˹ ᏒᏬᏂᎥ ꭙ ᏗᎥ ˼ 🧠 
├───────────────────⦿
│ ▸ sᴀᴠᴀɢᴇ ɢɪʀʟ ᴘᴇʀsᴏɴᴀ
│ ▸ ʀᴇsᴘᴇᴄᴛ sᴇ ʙᴇᴢᴢᴀᴛɪ 😏
├───────────────────⦿
│ ▸ ɢʀᴏᴜᴘ: 20 ᴍsɢ ᴍᴇᴍᴏʀʏ
│ ▸ ᴘʀɪᴠᴀᴛᴇ: 50 ᴍsɢ ᴍᴇᴍᴏʀʏ
│ ▸ ɴᴀᴍᴇ sᴇ ʙᴜʟᴀᴛɪ ʜᴀɪ
│ ▸ ʀᴏᴀsᴛ + ᴍᴀsᴛɪ + ᴄᴀʀᴇ
│ ▸ ᴏᴡɴᴇʀ ᴋᴏ ғᴜʟʟ ʀᴇsᴘᴇᴄᴛ
│ ▸ 24x7 ᴏɴʟɪɴᴇ
├───────────────────⦿
│ sᴀʏ "ʀᴜʜɪ ᴊɪ" ᴛᴏ ᴡᴀᴋᴇ ᴍᴇ
│ ᴍᴀᴅᴇ ʙʏ...@RUHI_VIG_QNR
╰───────────────────⦿

ʜᴇʏ ᴅᴇᴀʀ, 🥀
๏ ɪ ᴀᴍ ʀᴜʜɪ ᴊɪ — sᴀᴠᴀɢᴇ ǫᴜᴇᴇɴ 👑
๏ ʀᴏᴀsᴛ + ᴍᴀsᴛɪ + ᴘʏᴀᴀʀ
๏ ᴍᴏᴅᴇʟ: {model}
•── ⋅ ⋅ ────── ⋅ ────── ⋅ ⋅ ──•
๏ sᴀʏ "ʀᴜʜɪ ᴊɪ" ᴛᴏ sᴛᴀʀᴛ 🌹"""

HELP_ASCII = """╭───────────────────⦿
│ ʀᴜʜɪ ᴊɪ - ʜᴇʟᴘ
├───────────────────⦿
│ sᴀʏ "ʀᴜʜɪ ᴊɪ" → 10ᴍɪɴ sᴇssɪᴏɴ
│ ᴇx: "ʀᴜʜɪ ᴊɪ ᴋᴀɪsɪ ʜᴏ?"
├───────────────────⦿
│ /start /help /profile
│ /clear /lang /personality
│ /usage /summary /reset
├───────────────────⦿
│ ᴀᴅᴍɪɴ:
│ /admin /addadmin /removeadmin
│ /broadcast /totalusers
│ /activeusers /forceclear
│ /shutdown /restart /ban
│ /unban /badwords /addbadword
│ /removebadword /setphrase
╰───────────────────⦿"""
