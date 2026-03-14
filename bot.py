"""
bot.py — Ruhi Ji Telegram Bot  🥀
Webhook mode + aiohttp server — optimised for Render Free Web Service
"""

import asyncio
import logging
import time
import os
from typing import Optional

from aiohttp import web, ClientSession
from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode, ChatType
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, BotCommand, BotCommandScopeDefault
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

import database as db
from config import (
    BOT_TOKEN, OWNER_ID, OWNER_USERNAME,
    WAKE_PHRASES, SESSION_DURATION_MINUTES, RATE_LIMIT_SECONDS,
    START_ASCII, HELP_ASCII, HF_MODEL,
)
from llm import get_llm_reply, get_summary

# ─────────────────────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
#  WEBHOOK / SERVER CONFIG
# ─────────────────────────────────────────────────────────────
# Render injects PORT automatically; 8080 for local testing
PORT: int = int(os.getenv("PORT", 8080))

# Render sets this automatically — e.g. https://ruhi-ji-bot.onrender.com
WEBHOOK_BASE: str = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
WEBHOOK_PATH: str = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL:  str = f"{WEBHOOK_BASE}{WEBHOOK_PATH}"

# ─────────────────────────────────────────────────────────────
#  BOT & DISPATCHER
# ─────────────────────────────────────────────────────────────
bot    = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp     = Dispatcher()
router = Router()
dp.include_router(router)

# In-memory state
_rate_limit: dict[int, float] = {}
_bot_active: bool = True
_bot_id: Optional[int] = None   # cached at startup


# ─────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────

def _model_name() -> str:
    return HF_MODEL.split("/")[-1]

def _is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

async def _is_admin_or_owner(user_id: int) -> bool:
    return _is_owner(user_id) or await db.is_admin(user_id)

def _rate_limited(user_id: int) -> bool:
    now  = time.time()
    last = _rate_limit.get(user_id, 0)
    if now - last < RATE_LIMIT_SECONDS:
        return True
    _rate_limit[user_id] = now
    return False

async def _contains_bad_word(text: str) -> bool:
    return any(bw in text.lower() for bw in await db.get_bad_words())

async def _ensure_user(msg: Message):
    u = msg.from_user
    if u:
        await db.upsert_user(u.id, u.username or "", u.full_name or "")
    await db.upsert_chat(msg.chat.id, msg.chat.type)

def _user_display(msg: Message) -> str:
    u = msg.from_user
    if not u:
        return "Koi"
    return u.first_name or u.username or "Bhai"


# ─────────────────────────────────────────────────────────────
#  USER COMMANDS
# ─────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(msg: Message):
    await _ensure_user(msg)
    await msg.answer(START_ASCII.replace("{model}", _model_name()))

@router.message(Command("help"))
async def cmd_help(msg: Message):
    await _ensure_user(msg)
    await msg.answer(HELP_ASCII)

@router.message(Command("profile"))
async def cmd_profile(msg: Message):
    await _ensure_user(msg)
    u = msg.from_user
    if not u:
        return
    user_row = await db.get_user(u.id)
    if not user_row:
        await msg.answer("Profile nahi mila yaar 😭")
        return
    is_own     = _is_owner(u.id)
    is_adm     = await db.is_admin(u.id)
    role_label = "👑 Owner" if is_own else ("🛡 Admin" if is_adm else "👤 User")
    relation   = "Mera Owner-sama 🥺💕" if is_own else "Mera Regular User 😏"
    await msg.answer(
        f"╭───────────────────⦿\n"
        f"│ 👤 <b>{u.full_name or u.username}</b>\n"
        f"│ 🆔 <code>{u.id}</code>\n"
        f"│ 🎭 {role_label}\n"
        f"│ 💬 Messages: {user_row.get('msg_count', 0)}\n"
        f"│ 🌐 Language: {user_row.get('lang_pref', 'hinglish')}\n"
        f"│ 💞 Relation: {relation}\n"
        f"╰───────────────────⦿"
    )

@router.message(Command(commands=["clear", "reset"]))
async def cmd_clear(msg: Message):
    await _ensure_user(msg)
    await db.clear_history(msg.chat.id)
    await db.clear_session(msg.chat.id)
    await msg.answer("Memory clear ho gayi! ✨ Fresh start bestie 🌸")

@router.message(Command("lang"))
async def cmd_lang(msg: Message):
    await _ensure_user(msg)
    u = msg.from_user
    if not u:
        return
    user_row = await db.get_user(u.id)
    current  = user_row.get("lang_pref", "hinglish") if user_row else "hinglish"
    new_lang = "hindi" if current == "hinglish" else "hinglish"
    await db.set_user_lang(u.id, new_lang)
    await msg.answer(f"Language switch! Ab: <b>{new_lang}</b> ✨")

@router.message(Command("personality"))
async def cmd_personality(msg: Message):
    await _ensure_user(msg)
    mood   = await db.get_setting("bot_mood")   or "savage"
    active = await db.get_setting("bot_active") or "true"
    await msg.answer(
        f"╭───────────────────⦿\n"
        f"│ 🎭 Mood: <b>{mood}</b>\n"
        f"│ ⚡ Status: {'Online 🟢' if active == 'true' else 'Offline 🔴'}\n"
        f"│ 💅 Persona: Savage Queen\n"
        f"│ 👑 Owner: @{OWNER_USERNAME}\n"
        f"╰───────────────────⦿"
    )

@router.message(Command(commands=["usage", "summary"]))
async def cmd_summary(msg: Message):
    await _ensure_user(msg)
    history = await db.get_history(msg.chat.id, msg.chat.type)
    summary = await get_summary(history)
    await msg.answer(f"📋 <b>Chat Summary:</b>\n\n{summary}")


# ─────────────────────────────────────────────────────────────
#  ADMIN COMMANDS
# ─────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(msg: Message):
    await _ensure_user(msg)
    if not await _is_admin_or_owner(msg.from_user.id):
        await msg.answer("Tu admin nahi hai beta 😂 apni aukaat mein reh 💅")
        return
    total      = await db.get_total_users()
    active     = await db.get_active_users()
    mood       = await db.get_setting("bot_mood")   or "savage"
    bot_active = await db.get_setting("bot_active") or "true"
    admins     = await db.get_admin_list()
    admin_names = ", ".join(f"@{a['username']}" for a in admins if a.get("username")) or "None"
    await msg.answer(
        f"╭───────────────────⦿\n"
        f"│ 👑 OWNER DASHBOARD\n"
        f"├───────────────────⦿\n"
        f"│ 👥 Total Users : {total}\n"
        f"│ 🟢 Active (7d) : {active}\n"
        f"│ 🎭 Bot Mood    : {mood}\n"
        f"│ ⚡ Bot Active  : {bot_active}\n"
        f"│ 🛡 Admins      : {admin_names}\n"
        f"╰───────────────────⦿\n\n"
        f"Use /addadmin /removeadmin /broadcast\n"
        f"/ban /unban /forceclear /badwords\n"
        f"/shutdown /restart /setphrase"
    )

@router.message(Command("addadmin"))
async def cmd_addadmin(msg: Message):
    await _ensure_user(msg)
    if not _is_owner(msg.from_user.id):
        await msg.answer("Sirf Owner hi admins add kar sakta hai 👑")
        return
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        await msg.answer("Usage: /addadmin &lt;user_id&gt;")
        return
    try:
        target_id  = int(args[1].strip())
        target_row = await db.get_user(target_id)
        username   = target_row["username"] if target_row else "unknown"
        await db.add_admin(target_id, username)
        await msg.answer(f"✅ <code>{target_id}</code> (@{username}) admin ban gaya! 🛡")
    except ValueError:
        await msg.answer("Valid user_id daal beta 😂")

@router.message(Command("removeadmin"))
async def cmd_removeadmin(msg: Message):
    await _ensure_user(msg)
    if not _is_owner(msg.from_user.id):
        await msg.answer("Sirf Owner hi admins remove kar sakta hai 👑")
        return
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        await msg.answer("Usage: /removeadmin &lt;user_id&gt;")
        return
    try:
        target_id = int(args[1].strip())
        await db.remove_admin(target_id)
        await msg.answer(f"🗑 <code>{target_id}</code> admin se remove ho gaya")
    except ValueError:
        await msg.answer("Valid user_id daal beta 😂")

@router.message(Command("broadcast"))
async def cmd_broadcast(msg: Message):
    await _ensure_user(msg)
    if not await _is_admin_or_owner(msg.from_user.id):
        await msg.answer("Teri aukaat nahi hai yeh command use karne ki 💅")
        return
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        await msg.answer("Usage: /broadcast &lt;message&gt;")
        return
    user_ids = await db.get_all_user_ids()
    sent, failed = 0, 0
    for uid in user_ids:
        try:
            await bot.send_message(uid, f"📢 <b>Broadcast:</b>\n\n{args[1]}")
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
    await msg.answer(f"📢 Done! ✅ {sent} | ❌ {failed}")

@router.message(Command("totalusers"))
async def cmd_totalusers(msg: Message):
    await _ensure_user(msg)
    if not await _is_admin_or_owner(msg.from_user.id):
        return
    await msg.answer(f"👥 Total users: <b>{await db.get_total_users()}</b>")

@router.message(Command("activeusers"))
async def cmd_activeusers(msg: Message):
    await _ensure_user(msg)
    if not await _is_admin_or_owner(msg.from_user.id):
        return
    await msg.answer(f"🟢 Active (7d): <b>{await db.get_active_users()}</b>")

@router.message(Command("forceclear"))
async def cmd_forceclear(msg: Message):
    await _ensure_user(msg)
    if not await _is_admin_or_owner(msg.from_user.id):
        await msg.answer("Tu admin nahi hai beta 😂")
        return
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        await msg.answer("Usage: /forceclear &lt;user_id&gt;")
        return
    try:
        target_id = int(args[1].strip())
        await db.clear_user_history(target_id)
        await msg.answer(f"🗑 <code>{target_id}</code> ki memory clear kar di!")
    except ValueError:
        await msg.answer("Valid user_id daal beta 😂")

@router.message(Command("ban"))
async def cmd_ban(msg: Message):
    await _ensure_user(msg)
    if not await _is_admin_or_owner(msg.from_user.id):
        await msg.answer("Tu admin nahi hai beta 😂")
        return
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        await msg.answer("Usage: /ban &lt;user_id&gt;")
        return
    try:
        target_id = int(args[1].strip())
        if _is_owner(target_id):
            await msg.answer("Owner ko ban? 💀 teri himmat toh dekh 😂")
            return
        await db.ban_user(target_id)
        await msg.answer(f"🚫 <code>{target_id}</code> banned! 😏")
    except ValueError:
        await msg.answer("Valid user_id daal beta 😂")

@router.message(Command("unban"))
async def cmd_unban(msg: Message):
    await _ensure_user(msg)
    if not await _is_admin_or_owner(msg.from_user.id):
        await msg.answer("Tu admin nahi hai beta 😂")
        return
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        await msg.answer("Usage: /unban &lt;user_id&gt;")
        return
    try:
        target_id = int(args[1].strip())
        await db.unban_user(target_id)
        await msg.answer(f"✅ <code>{target_id}</code> unban ho gaya! 🥀")
    except ValueError:
        await msg.answer("Valid user_id daal beta 😂")

@router.message(Command("badwords"))
async def cmd_badwords(msg: Message):
    await _ensure_user(msg)
    if not await _is_admin_or_owner(msg.from_user.id):
        return
    words = await db.get_bad_words()
    if not words:
        await msg.answer("📋 Bad words list empty hai ✨")
        return
    await msg.answer(f"📋 <b>Bad Words:</b>\n<code>{', '.join(words)}</code>")

@router.message(Command("addbadword"))
async def cmd_addbadword(msg: Message):
    await _ensure_user(msg)
    if not await _is_admin_or_owner(msg.from_user.id):
        return
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        await msg.answer("Usage: /addbadword &lt;word&gt;")
        return
    word = args[1].strip().lower()
    await db.add_bad_word(word)
    await msg.answer(f"✅ '<code>{word}</code>' add ho gaya 🚫")

@router.message(Command("removebadword"))
async def cmd_removebadword(msg: Message):
    await _ensure_user(msg)
    if not await _is_admin_or_owner(msg.from_user.id):
        return
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        await msg.answer("Usage: /removebadword &lt;word&gt;")
        return
    word = args[1].strip().lower()
    await db.remove_bad_word(word)
    await msg.answer(f"🗑 '<code>{word}</code>' remove ho gaya ✨")

@router.message(Command("setphrase"))
async def cmd_setphrase(msg: Message):
    await _ensure_user(msg)
    if not await _is_admin_or_owner(msg.from_user.id):
        return
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        await msg.answer(
            "Usage: /setphrase mood:&lt;value&gt;\n"
            "Moods: savage | happy | sad | flirty | chill"
        )
        return
    parts = args[1].strip()
    if parts.startswith("mood:"):
        new_mood = parts.split("mood:", 1)[1].strip()
        await db.set_setting("bot_mood", new_mood)
        await msg.answer(f"✅ Mood → <b>{new_mood}</b> 🎭")
    else:
        await msg.answer("Format: /setphrase mood:&lt;value&gt;")

@router.message(Command("shutdown"))
async def cmd_shutdown(msg: Message):
    global _bot_active
    await _ensure_user(msg)
    if not await _is_admin_or_owner(msg.from_user.id):
        await msg.answer("Tu admin nahi hai beta 😂")
        return
    _bot_active = False
    await db.set_setting("bot_active", "false")
    await msg.answer("😴 Ruhi Ji so gayi... /restart se jagaao")

@router.message(Command("restart"))
async def cmd_restart(msg: Message):
    global _bot_active
    await _ensure_user(msg)
    if not await _is_admin_or_owner(msg.from_user.id):
        await msg.answer("Tu admin nahi hai beta 😂")
        return
    _bot_active = True
    await db.set_setting("bot_active", "true")
    await msg.answer("✨ Ruhi Ji waapas! Kya missed kiya mujhe? 😏")


# ─────────────────────────────────────────────────────────────
#  MAIN MESSAGE HANDLER
# ─────────────────────────────────────────────────────────────

@router.message(F.text)
async def handle_message(msg: Message):
    global _bot_active, _bot_id

    if not msg.from_user or not msg.text:
        return

    await _ensure_user(msg)

    user_id    = msg.from_user.id
    chat_id    = msg.chat.id
    chat_type  = msg.chat.type
    text       = msg.text.strip()
    text_lower = text.lower()

    if not _bot_active and not _is_owner(user_id):
        return
    if await db.is_banned(user_id):
        return
    if await _contains_bad_word(text):
        await msg.reply("Yeh sab mat bola kar yaar 🚫 thoda tameez seekh 💅")
        return

    is_private      = chat_type == ChatType.PRIVATE
    is_reply_to_bot = (
        msg.reply_to_message
        and msg.reply_to_message.from_user
        and msg.reply_to_message.from_user.id == _bot_id
    )
    wake_triggered = any(phrase in text_lower for phrase in WAKE_PHRASES)

    should_reply = False
    if is_private:
        should_reply = True
    elif is_reply_to_bot:
        should_reply = True
    elif wake_triggered:
        should_reply = True
        await db.set_session(chat_id, SESSION_DURATION_MINUTES)
    elif await db.is_session_active(chat_id):
        should_reply = True

    if not should_reply:
        return
    if _rate_limited(user_id):
        return

    await db.add_message(chat_id, user_id, "user", text)
    await db.increment_msg_count(user_id)

    history   = await db.get_history(chat_id, chat_type)
    bot_mood  = await db.get_setting("bot_mood") or "savage"
    user_name = _user_display(msg)

    await bot.send_chat_action(chat_id, "typing")

    reply_text = await get_llm_reply(
        user_msg=text,
        history=history[:-1],
        is_owner=_is_owner(user_id),
        user_name=user_name,
        bot_mood=bot_mood,
    )

    await db.add_message(chat_id, None, "assistant", reply_text)
    await msg.reply(reply_text)


# ─────────────────────────────────────────────────────────────
#  SELF-PING  (keeps Render free tier awake every 10 min)
# ─────────────────────────────────────────────────────────────

async def self_ping_loop():
    """Ping /health every 10 min so Render doesn't put the service to sleep."""
    await asyncio.sleep(30)   # let server fully start first
    async with ClientSession() as session:
        while True:
            try:
                url = f"{WEBHOOK_BASE}/health"
                async with session.get(url, timeout=10) as resp:
                    logger.info(f"Self-ping → {resp.status}")
            except Exception as e:
                logger.warning(f"Self-ping failed: {e}")
            await asyncio.sleep(600)   # 10 minutes


# ─────────────────────────────────────────────────────────────
#  AIOHTTP ROUTES
# ─────────────────────────────────────────────────────────────

async def health_handler(request: web.Request) -> web.Response:
    """Health check endpoint — Render pings this to detect liveness."""
    return web.json_response({"status": "ok", "bot": "Ruhi Ji 🥀"})


# ─────────────────────────────────────────────────────────────
#  BOT COMMANDS REGISTRATION
# ─────────────────────────────────────────────────────────────

async def set_bot_commands():
    commands = [
        BotCommand(command="start",         description="Ruhi Ji ko wake up karo 🌸"),
        BotCommand(command="help",          description="Help menu dekho"),
        BotCommand(command="profile",       description="Apna profile dekho"),
        BotCommand(command="clear",         description="Memory clear karo"),
        BotCommand(command="reset",         description="Context reset karo"),
        BotCommand(command="lang",          description="Language toggle"),
        BotCommand(command="personality",   description="Bot ka mood dekho"),
        BotCommand(command="usage",         description="Chat summary lo"),
        BotCommand(command="summary",       description="Chat summary lo"),
        BotCommand(command="admin",         description="[Admin] Dashboard"),
        BotCommand(command="addadmin",      description="[Admin] Admin add karo"),
        BotCommand(command="removeadmin",   description="[Admin] Admin remove karo"),
        BotCommand(command="broadcast",     description="[Admin] Sab ko message bhejo"),
        BotCommand(command="ban",           description="[Admin] User ban karo"),
        BotCommand(command="unban",         description="[Admin] User unban karo"),
        BotCommand(command="totalusers",    description="[Admin] Total users dekho"),
        BotCommand(command="activeusers",   description="[Admin] Active users dekho"),
        BotCommand(command="forceclear",    description="[Admin] Kisi ki memory clear karo"),
        BotCommand(command="badwords",      description="[Admin] Bad words list dekho"),
        BotCommand(command="addbadword",    description="[Admin] Bad word add karo"),
        BotCommand(command="removebadword", description="[Admin] Bad word remove karo"),
        BotCommand(command="setphrase",     description="[Admin] Bot mood set karo"),
        BotCommand(command="shutdown",      description="[Admin] Bot sulate jao"),
        BotCommand(command="restart",       description="[Admin] Bot jagao"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())


# ─────────────────────────────────────────────────────────────
#  STARTUP VALIDATION
# ─────────────────────────────────────────────────────────────

def _validate_config():
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if not OWNER_ID:
        missing.append("OWNER_ID")
    if not WEBHOOK_BASE:
        missing.append("RENDER_EXTERNAL_URL")
    if missing:
        raise EnvironmentError(
            f"❌ Missing env vars: {', '.join(missing)}\n"
            "   Copy .env.example → .env and fill values."
        )
    import config as cfg
    if not cfg.HF_TOKEN:
        logger.warning("⚠️  HF_TOKEN not set — LLM replies will fail!")
    if not cfg.DATABASE_URL:
        raise EnvironmentError("❌ DATABASE_URL not set.")


# ─────────────────────────────────────────────────────────────
#  STARTUP / SHUTDOWN LIFECYCLE
# ─────────────────────────────────────────────────────────────

async def on_startup(app: web.Application):
    global _bot_active, _bot_id

    _validate_config()
    logger.info("🚀 Starting Ruhi Ji Bot (webhook mode)...")

    await db.create_pool()

    # Restore active state from DB (survives redeploys)
    saved_active = await db.get_setting("bot_active")
    _bot_active  = (saved_active != "false")

    await set_bot_commands()

    # Register webhook with Telegram
    await bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"],
    )
    logger.info(f"✅ Webhook registered → {WEBHOOK_URL}")

    me      = await bot.get_me()
    _bot_id = me.id
    logger.info(f"✅ Bot ready: @{me.username} (id={me.id})")

    # Launch self-ping background task
    asyncio.create_task(self_ping_loop())
    logger.info("✅ Self-ping loop started (every 10 min)")

    # Notify owner
    if OWNER_ID:
        try:
            await bot.send_message(
                OWNER_ID,
                "✨ Ruhi Ji online ho gayi hai Owner-sama! 🥺💕\n"
                "/admin se dashboard dekho."
            )
        except Exception:
            pass


async def on_shutdown(app: web.Application):
    logger.info("Shutting down Ruhi Ji Bot...")
    await bot.delete_webhook()
    await db.close_pool()
    await bot.session.close()


# ─────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────

def main():
    app = web.Application()

    # Health + root route (Render health checks)
    app.router.add_get("/",       health_handler)
    app.router.add_get("/health", health_handler)

    # Telegram webhook route
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    # Lifecycle hooks
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    logger.info(f"🌐 Web server on port {PORT}")
    web.run_app(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
