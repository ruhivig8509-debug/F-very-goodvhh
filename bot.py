"""
bot.py - Main entry point for Ruhi Ji Telegram Bot.
Includes:
  - All Telegram command & message handlers
  - Hugging Face LLM integration
  - Lightweight aiohttp web server for Render health checks
  - Wake-phrase logic & session management
"""

import os
import re
import asyncio
import logging
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from aiohttp import web

from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode, ChatType

import database as db
import llm_client as llm
from personality import build_system_prompt

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("ruhi_ji")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OWNER_USERNAME = os.environ.get("OWNER_USERNAME", "RUHI_VIG_QNR")
PORT = int(os.environ.get("PORT", 10000))

WAKE_PATTERN = re.compile(r"\bruhi\s*ji\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# ASCII UI Menus
# ---------------------------------------------------------------------------

START_TEXT = """╭───────────────────⦿
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
๏  ᴍᴏᴅᴇʟ: Kimi-K2-Instruct
•── ⋅ ⋅ ────── ⋅ ────── ⋅ ⋅ ──•
๏ sᴀʏ "ʀᴜʜɪ ᴊɪ" ᴛᴏ sᴛᴀʀᴛ 🌹"""

HELP_TEXT = """╭───────────────────⦿
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

ADMIN_DASHBOARD = """╭───────────────────⦿
│ 👑 ʀᴜʜɪ ᴊɪ — ᴏᴡɴᴇʀ ᴅᴀsʜʙᴏᴀʀᴅ
├───────────────────⦿
│ /broadcast <msg> — sᴇɴᴅ ᴛᴏ ᴀʟʟ
│ /totalusers — ᴛᴏᴛᴀʟ ᴜsᴇʀs
│ /activeusers — ᴀᴄᴛɪᴠᴇ (1ʜ)
│ /forceclear <uid> — ᴡɪᴘᴇ ᴜsᴇʀ
│ /ban <uid> — ʙᴀɴ ᴜsᴇʀ
│ /unban <uid> — ᴜɴʙᴀɴ ᴜsᴇʀ
│ /addbadword <w> — ᴀᴅᴅ ғɪʟᴛᴇʀ
│ /removebadword <w> — ʀᴇᴍᴏᴠᴇ
│ /badwords — ʟɪsᴛ ᴀʟʟ
╰───────────────────⦿"""


# ---------------------------------------------------------------------------
# Helper: safe DB wrapper
# ---------------------------------------------------------------------------

def _safe_db(func, *args, default=None, **kwargs):
    """Call a DB function, return default on any exception."""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.warning("DB error in %s: %s", func.__name__, e)
        return default


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def is_owner(user) -> bool:
    return (user.username or "").lower() == OWNER_USERNAME.lower()


def get_display_name(user) -> str:
    if user.first_name:
        return user.first_name
    if user.username:
        return user.username
    return "User"


async def ensure_registered(user, chat=None):
    """Register user and chat in the database. Silently skips on DB error."""
    _safe_db(db.upsert_user, user.id, user.username, user.first_name)
    if chat:
        chat_type = "private" if chat.type == ChatType.PRIVATE else "group"
        _safe_db(db.upsert_chat, chat.id, chat_type, getattr(chat, "title", None))


def contains_bad_word(text: str) -> bool:
    words = _safe_db(db.get_bad_words, default=[])
    if not words:
        return False
    text_lower = text.lower()
    return any(w in text_lower for w in words)


def should_respond(update: Update, chat_type: str) -> bool:
    if chat_type == "private":
        return True
    message = update.message
    if not message or not message.text:
        return False
    if message.reply_to_message and message.reply_to_message.from_user:
        if message.reply_to_message.from_user.is_bot:
            return True
    if WAKE_PATTERN.search(message.text):
        return True
    if _safe_db(db.is_session_active, message.chat_id, default=False):
        return True
    return False


# ---------------------------------------------------------------------------
# Command Handlers
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_registered(update.effective_user, update.effective_chat)
    await update.message.reply_text(START_TEXT)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_registered(update.effective_user, update.effective_chat)
    await update.message.reply_text(HELP_TEXT)


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await ensure_registered(user, update.effective_chat)
    data = _safe_db(db.get_user, user.id)
    if not data:
        txt = (
            f"╭───────────────────⦿\n"
            f"│ 👤 Profile\n"
            f"├───────────────────⦿\n"
            f"│ Name: {user.first_name or 'N/A'}\n"
            f"│ Username: @{user.username or 'N/A'}\n"
            f"│ Role: user\n"
            f"│ Lang: hinglish\n"
            f"╰───────────────────⦿"
        )
    else:
        txt = (
            f"╭───────────────────⦿\n"
            f"│ 👤 Profile\n"
            f"├───────────────────⦿\n"
            f"│ Name: {data['first_name'] or 'N/A'}\n"
            f"│ Username: @{data['username'] or 'N/A'}\n"
            f"│ Role: {data['role']}\n"
            f"│ Lang: {data['preferred_lang']}\n"
            f"│ Banned: {'❌ Yes' if data['is_banned'] else '✅ No'}\n"
            f"│ First Seen: {str(data['first_seen'])[:19]}\n"
            f"│ Last Active: {str(data['last_active'])[:19]}\n"
            f"╰───────────────────⦿"
        )
    await update.message.reply_text(txt)


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_registered(update.effective_user, update.effective_chat)
    _safe_db(db.clear_chat_history, update.effective_chat.id)
    await update.message.reply_text("Memory wiped! Fresh start ✨🧹\nAb kya bologe? 😏")


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_clear(update, context)


async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await ensure_registered(user, update.effective_chat)
    data = _safe_db(db.get_user, user.id)
    current = data["preferred_lang"] if data else "hinglish"
    new_lang = "english" if current == "hinglish" else "hinglish"
    _safe_db(db.set_user_lang, user.id, new_lang)
    await update.message.reply_text(
        f"Language switched to: {new_lang.upper()} ✨\n"
        f"(But Ruhi Ji ka style toh Hinglish hi rahega 💅)"
    )


async def cmd_personality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_registered(update.effective_user, update.effective_chat)
    mood = _safe_db(db.get_setting, "bot_mood", default="savage") or "savage"
    mood_emojis = {
        "savage": "😏🔥 Savage Queen Mode",
        "chill": "😎✌️ Chill Vibes Mode",
        "romantic": "🌹💕 Romantic Shayari Mode",
        "angry": "😤💢 Angry Mode — Don't Mess",
    }
    display = mood_emojis.get(mood, f"🤷 {mood}")
    await update.message.reply_text(f"Current Personality: {display}")


async def cmd_usage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_summary(update, context)


async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_registered(update.effective_user, update.effective_chat)
    chat_id = update.effective_chat.id
    history = _safe_db(db.get_chat_history, chat_id, default=[])
    if not history:
        await update.message.reply_text("Koi chat history nahi hai abhi 🥺 Pehle baat toh karo!")
        return

    await update.message.reply_text("Summary bana rahi hoon... ek sec ✨")

    user = update.effective_user
    owner = is_owner(user)
    mood = _safe_db(db.get_setting, "bot_mood", default="savage") or "savage"
    chat_type = "private" if update.effective_chat.type == ChatType.PRIVATE else "group"

    prompt = build_system_prompt(
        user_name=get_display_name(user),
        user_username=user.username or "",
        is_owner=owner,
        chat_type=chat_type,
        bot_mood=mood,
    )
    summary = llm.generate_summary(prompt, history)
    await update.message.reply_text(f"📝 Chat Summary:\n\n{summary}")


# ---------------------------------------------------------------------------
# Admin Commands
# ---------------------------------------------------------------------------

async def admin_check(update: Update) -> bool:
    if not is_owner(update.effective_user):
        await update.message.reply_text("Ye command sirf mere Owner ke liye hai 😤💅 Tum kaun? 🙄")
        return False
    return True


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update):
        return
    await update.message.reply_text(ADMIN_DASHBOARD)


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    msg = " ".join(context.args)
    chat_ids = _safe_db(db.get_all_chat_ids, default=[])
    success, fail = 0, 0
    for cid in chat_ids:
        try:
            await context.bot.send_message(chat_id=cid, text=f"📢 Broadcast from Ruhi Ji:\n\n{msg}")
            success += 1
        except Exception:
            fail += 1
    await update.message.reply_text(f"Broadcast done ✅\nSent: {success} | Failed: {fail}")


async def cmd_totalusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update):
        return
    count = _safe_db(db.get_total_users, default=0)
    await update.message.reply_text(f"👥 Total Registered Users: {count}")


async def cmd_activeusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update):
        return
    count = _safe_db(db.get_active_users, 60, default=0)
    await update.message.reply_text(f"⚡ Active Users (last 1 hour): {count}")


async def cmd_forceclear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /forceclear <user_id>")
        return
    try:
        uid = int(context.args[0])
        _safe_db(db.clear_user_history, uid)
        await update.message.reply_text(f"✅ Cleared all messages for user {uid}")
    except ValueError:
        await update.message.reply_text("Invalid user ID. Use a number.")


async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /ban <user_id>")
        return
    try:
        uid = int(context.args[0])
        _safe_db(db.set_user_banned, uid, True)
        await update.message.reply_text(f"🚫 User {uid} has been banned!")
    except ValueError:
        await update.message.reply_text("Invalid user ID.")


async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /unban <user_id>")
        return
    try:
        uid = int(context.args[0])
        _safe_db(db.set_user_banned, uid, False)
        await update.message.reply_text(f"✅ User {uid} has been unbanned!")
    except ValueError:
        await update.message.reply_text("Invalid user ID.")


async def cmd_addbadword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /addbadword <word>")
        return
    word = " ".join(context.args).strip().lower()
    _safe_db(db.add_bad_word, word)
    await update.message.reply_text(f"✅ Added '{word}' to bad words filter.")


async def cmd_removebadword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /removebadword <word>")
        return
    word = " ".join(context.args).strip().lower()
    _safe_db(db.remove_bad_word, word)
    await update.message.reply_text(f"✅ Removed '{word}' from bad words filter.")


async def cmd_badwords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update):
        return
    words = _safe_db(db.get_bad_words, default=[])
    if not words:
        await update.message.reply_text("Bad words list is empty ✅")
        return
    word_list = "\n".join(f"• {w}" for w in words)
    await update.message.reply_text(f"🚫 Bad Words Filter:\n{word_list}")


# ---------------------------------------------------------------------------
# Main Message Handler (The Brain)
# ---------------------------------------------------------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Core message handler — processes all non-command text messages."""
    message = update.message
    if not message or not message.text:
        return

    user = update.effective_user
    chat = update.effective_chat
    text = message.text.strip()

    if not text:
        return

    await ensure_registered(user, chat)

    # Check if user is banned
    if _safe_db(db.is_user_banned, user.id, default=False):
        return

    chat_type = "private" if chat.type == ChatType.PRIVATE else "group"

    # --- Group Logic: Wake phrase & session management ---
    if chat_type == "group":
        wake_triggered = bool(WAKE_PATTERN.search(text))

        if wake_triggered:
            _safe_db(db.activate_session, chat.id, 10)

        if not should_respond(update, chat_type):
            _safe_db(db.store_message, chat.id, user.id, "user", f"[{get_display_name(user)}]: {text}")
            return
    else:
        if WAKE_PATTERN.search(text):
            _safe_db(db.activate_session, chat.id, 10)

    # --- Bad word filter ---
    if contains_bad_word(text):
        await message.reply_text(
            "Ew, ye kya bol rahe ho? 🤢 Ruhi Ji ke saamne ye sab nahi chalega. "
            "Seedha ban hoge chomu 😤💅"
        )
        return

    # --- Build context and generate response ---
    owner = is_owner(user)
    mood = _safe_db(db.get_setting, "bot_mood", default="savage") or "savage"

    user_display = get_display_name(user)
    stored_text = f"[{user_display}]: {text}" if chat_type == "group" else text
    _safe_db(db.store_message, chat.id, user.id, "user", stored_text)

    history = _safe_db(db.get_chat_history, chat.id, default=[])

    system_prompt = build_system_prompt(
        user_name=user_display,
        user_username=user.username or "",
        is_owner=owner,
        chat_type=chat_type,
        bot_mood=mood,
    )

    await context.bot.send_chat_action(chat_id=chat.id, action="typing")

    response = llm.generate_response(system_prompt, history[:-1], stored_text)

    _safe_db(db.store_message, chat.id, 0, "assistant", response)

    if chat_type == "group":
        _safe_db(db.activate_session, chat.id, 10)

    await message.reply_text(response)


# ---------------------------------------------------------------------------
# Error Handler
# ---------------------------------------------------------------------------

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception while handling update %s: %s", update, context.error, exc_info=True)
    if update and update.message:
        try:
            await update.message.reply_text(
                "Oops kuch toh gadbad ho gayi 😩🥀 Thodi der baad try karo na..."
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Web Server for Render Health Checks
# ---------------------------------------------------------------------------

async def health_handler(request):
    return web.json_response(
        {
            "status": "alive",
            "bot": "Ruhi Ji",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        status=200,
    )


async def home_handler(request):
    return web.Response(
        text="🌸 Ruhi Ji Bot is running! Say 'Ruhi Ji' on Telegram ✨",
        content_type="text/plain",
        status=200,
    )


async def run_webserver():
    app = web.Application()
    app.router.add_get("/", home_handler)
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info("Web server started on 0.0.0.0:%d", PORT)
    return runner


# ---------------------------------------------------------------------------
# Bot Setup & Main Entry Point
# ---------------------------------------------------------------------------

def build_application():
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set")

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # User Commands
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("profile", cmd_profile))
    application.add_handler(CommandHandler("clear", cmd_clear))
    application.add_handler(CommandHandler("reset", cmd_reset))
    application.add_handler(CommandHandler("lang", cmd_lang))
    application.add_handler(CommandHandler("personality", cmd_personality))
    application.add_handler(CommandHandler("usage", cmd_usage))
    application.add_handler(CommandHandler("summary", cmd_summary))

    # Admin Commands
    application.add_handler(CommandHandler("admin", cmd_admin))
    application.add_handler(CommandHandler("broadcast", cmd_broadcast))
    application.add_handler(CommandHandler("totalusers", cmd_totalusers))
    application.add_handler(CommandHandler("activeusers", cmd_activeusers))
    application.add_handler(CommandHandler("forceclear", cmd_forceclear))
    application.add_handler(CommandHandler("ban", cmd_ban))
    application.add_handler(CommandHandler("unban", cmd_unban))
    application.add_handler(CommandHandler("addbadword", cmd_addbadword))
    application.add_handler(CommandHandler("removebadword", cmd_removebadword))
    application.add_handler(CommandHandler("badwords", cmd_badwords))

    # Message Handler (must be last)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    application.add_error_handler(error_handler)

    return application


async def main():
    logger.info("Initializing database...")
    try:
        db.init_db()
        logger.info("Database ready ✅")
    except Exception as e:
        logger.error("Database init failed: %s — bot will run without persistent storage.", e)

    web_runner = await run_webserver()
    application = build_application()

    try:
        await application.bot.set_my_commands([
            BotCommand("start", "Start the bot"),
            BotCommand("help", "Show help menu"),
            BotCommand("profile", "Your profile stats"),
            BotCommand("clear", "Clear chat memory"),
            BotCommand("reset", "Reset conversation"),
            BotCommand("lang", "Toggle language"),
            BotCommand("personality", "Check bot mood"),
            BotCommand("summary", "Summarize recent chat"),
        ])
    except Exception as e:
        logger.warning("Could not set bot commands: %s", e)

    await application.initialize()
    await application.start()
    await application.updater.start_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )

    logger.info("🌸 Ruhi Ji is now online and ready! ✨")

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        await web_runner.cleanup()
        logger.info("Ruhi Ji has shut down gracefully. 🥀")


if __name__ == "__main__":
    asyncio.run(main())
