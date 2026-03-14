"""
bot.py — Ruhi Ji Telegram Bot  🥀
Main execution file: handlers, middleware, session logic, admin panel
"""

import asyncio
import logging
import time
from typing import Optional

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode, ChatType
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, BotCommand, BotCommandScopeDefault
)
from aiogram.utils.markdown import hcode

import database as db
from config import (
    BOT_TOKEN, OWNER_ID, OWNER_USERNAME,
    WAKE_PHRASES, SESSION_DURATION_MINUTES, RATE_LIMIT_SECONDS,
    START_ASCII, HELP_ASCII, HF_MODEL,
)
from llm import get_llm_reply, get_summary

# ─────────────────────────────────────────────────────────────
#  LOGGING SETUP
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
#  BOT & DISPATCHER
# ─────────────────────────────────────────────────────────────
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# In-memory rate-limit tracker  {user_id: last_call_timestamp}
_rate_limit: dict[int, float] = {}

# Bot active flag
_bot_active: bool = True


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
    now = time.time()
    last = _rate_limit.get(user_id, 0)
    if now - last < RATE_LIMIT_SECONDS:
        return True
    _rate_limit[user_id] = now
    return False


async def _contains_bad_word(text: str) -> bool:
    bad_words = await db.get_bad_words()
    text_lower = text.lower()
    return any(bw in text_lower for bw in bad_words)


async def _ensure_user(msg: Message):
    """Upsert user and chat records silently."""
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
    text = START_ASCII.replace("{model}", _model_name())
    await msg.answer(text)


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

    is_own = _is_owner(u.id)
    is_adm = await db.is_admin(u.id)
    role_label = "👑 Owner" if is_own else ("🛡 Admin" if is_adm else "👤 User")
    lang = user_row.get("lang_pref", "hinglish")
    msgs = user_row.get("msg_count", 0)
    relation = "Mera Owner-sama 🥺💕" if is_own else "Mera Regular User 😏"

    text = (
        f"╭───────────────────⦿\n"
        f"│ 👤 <b>{u.full_name or u.username}</b>\n"
        f"│ 🆔 <code>{u.id}</code>\n"
        f"│ 🎭 {role_label}\n"
        f"│ 💬 Messages: {msgs}\n"
        f"│ 🌐 Language: {lang}\n"
        f"│ 💞 Relation: {relation}\n"
        f"╰───────────────────⦿"
    )
    await msg.answer(text)


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
    current = user_row.get("lang_pref", "hinglish") if user_row else "hinglish"
    new_lang = "hindi" if current == "hinglish" else "hinglish"
    await db.set_user_lang(u.id, new_lang)
    await msg.answer(
        f"Language switch ho gayi! Ab meri language: <b>{new_lang}</b> ✨\n"
        f"(Abhi mostly Hinglish hi use hoti hai 😅)"
    )


@router.message(Command("personality"))
async def cmd_personality(msg: Message):
    await _ensure_user(msg)
    mood = await db.get_setting("bot_mood") or "savage"
    active = await db.get_setting("bot_active") or "true"
    status = "Online 🟢" if active == "true" else "Offline 🔴"
    await msg.answer(
        f"╭───────────────────⦿\n"
        f"│ 🎭 Current Mood: <b>{mood}</b>\n"
        f"│ ⚡ Status: {status}\n"
        f"│ 💅 Persona: Savage Queen\n"
        f"│ 👑 Owner: @{OWNER_USERNAME}\n"
        f"╰───────────────────⦿"
    )


@router.message(Command(commands=["usage", "summary"]))
async def cmd_summary(msg: Message):
    await _ensure_user(msg)
    chat_type = msg.chat.type
    history = await db.get_history(msg.chat.id, chat_type)
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

    total = await db.get_total_users()
    active = await db.get_active_users()
    mood = await db.get_setting("bot_mood") or "savage"
    bot_active = await db.get_setting("bot_active") or "true"
    admins = await db.get_admin_list()
    admin_names = ", ".join(f"@{a['username']}" for a in admins if a.get("username")) or "None"

    text = (
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
    await msg.answer(text)


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
        target_id = int(args[1].strip())
        target_row = await db.get_user(target_id)
        username = target_row["username"] if target_row else "unknown"
        await db.add_admin(target_id, username)
        await msg.answer(f"✅ User <code>{target_id}</code> (@{username}) ko admin bana diya! 🛡")
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
        await msg.answer(f"🗑 User <code>{target_id}</code> ko admin se remove kar diya")
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

    bcast_text = args[1]
    user_ids = await db.get_all_user_ids()
    sent, failed = 0, 0
    for uid in user_ids:
        try:
            await bot.send_message(uid, f"📢 <b>Broadcast:</b>\n\n{bcast_text}")
            sent += 1
            await asyncio.sleep(0.05)  # Telegram rate limit
        except Exception:
            failed += 1
    await msg.answer(f"📢 Broadcast done! ✅ Sent: {sent} | ❌ Failed: {failed}")


@router.message(Command("totalusers"))
async def cmd_totalusers(msg: Message):
    await _ensure_user(msg)
    if not await _is_admin_or_owner(msg.from_user.id):
        return
    total = await db.get_total_users()
    await msg.answer(f"👥 Total registered users: <b>{total}</b>")


@router.message(Command("activeusers"))
async def cmd_activeusers(msg: Message):
    await _ensure_user(msg)
    if not await _is_admin_or_owner(msg.from_user.id):
        return
    active = await db.get_active_users()
    await msg.answer(f"🟢 Active users (last 7 days): <b>{active}</b>")


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
        await msg.answer(f"🗑 User <code>{target_id}</code> ki memory forcefully clear kar di!")
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
        await msg.answer(f"🚫 User <code>{target_id}</code> banned! Ab yeh mujhse baat nahi kar sakta 😏")
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
        await msg.answer(f"✅ User <code>{target_id}</code> unban kar diya! Ek aur mauka mila hai 🥀")
    except ValueError:
        await msg.answer("Valid user_id daal beta 😂")


@router.message(Command("badwords"))
async def cmd_badwords(msg: Message):
    await _ensure_user(msg)
    if not await _is_admin_or_owner(msg.from_user.id):
        return
    words = await db.get_bad_words()
    if not words:
        await msg.answer("📋 Bad words list abhi empty hai ✨")
        return
    await msg.answer(f"📋 <b>Bad Words List:</b>\n<code>{', '.join(words)}</code>")


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
    await msg.answer(f"✅ '<code>{word}</code>' add ho gaya bad words mein 🚫")


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
    await msg.answer(f"🗑 '<code>{word}</code>' remove ho gaya bad words se ✨")


@router.message(Command("setphrase"))
async def cmd_setphrase(msg: Message):
    await _ensure_user(msg)
    if not await _is_admin_or_owner(msg.from_user.id):
        return
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        await msg.answer(
            "Usage: /setphrase mood:&lt;value&gt;\n"
            "Example: /setphrase mood:happy\n"
            "Moods: savage | happy | sad | flirty | chill"
        )
        return
    parts = args[1].strip()
    if parts.startswith("mood:"):
        new_mood = parts.split("mood:", 1)[1].strip()
        await db.set_setting("bot_mood", new_mood)
        await msg.answer(f"✅ Bot mood set to <b>{new_mood}</b> 🎭")
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
    await msg.answer("✨ Ruhi Ji waapas aa gayi! Kya missed kiya mujhe? 😏")


# ─────────────────────────────────────────────────────────────
#  MAIN MESSAGE HANDLER  (wake phrase + session logic)
# ─────────────────────────────────────────────────────────────

@router.message(F.text)
async def handle_message(msg: Message):
    global _bot_active

    if not msg.from_user or not msg.text:
        return

    await _ensure_user(msg)

    user_id = msg.from_user.id
    chat_id = msg.chat.id
    chat_type = msg.chat.type
    text = msg.text.strip()
    text_lower = text.lower()

    # ── Check bot active status ──────────────────────────────
    if not _bot_active and not _is_owner(user_id):
        return

    # ── Check ban ───────────────────────────────────────────
    if await db.is_banned(user_id):
        return

    # ── Bad word filter ──────────────────────────────────────
    if await _contains_bad_word(text):
        await msg.reply("Yeh sab mat bola kar yaar 🚫 thoda tameez seekh 💅")
        return

    # ── Determine if we should reply ────────────────────────
    is_private = chat_type == ChatType.PRIVATE
    is_reply_to_bot = (
        msg.reply_to_message
        and msg.reply_to_message.from_user
        and msg.reply_to_message.from_user.id == (await bot.get_me()).id
    )
    wake_triggered = any(phrase in text_lower for phrase in WAKE_PHRASES)

    should_reply = False

    if is_private:
        should_reply = True  # always reply in DM
    elif is_reply_to_bot:
        should_reply = True  # someone replied to bot
    elif wake_triggered:
        should_reply = True
        await db.set_session(chat_id, SESSION_DURATION_MINUTES)
    elif await db.is_session_active(chat_id):
        should_reply = True  # within 10-min session window

    if not should_reply:
        return

    # ── Rate limiting ────────────────────────────────────────
    if _rate_limited(user_id):
        return  # silently ignore, don't spam user

    # ── Store user message ───────────────────────────────────
    await db.add_message(chat_id, user_id, "user", text)
    await db.increment_msg_count(user_id)

    # ── Get LLM reply ────────────────────────────────────────
    history = await db.get_history(chat_id, chat_type)
    bot_mood = await db.get_setting("bot_mood") or "savage"
    user_name = _user_display(msg)
    owner = _is_owner(user_id)

    # Typing indicator
    await bot.send_chat_action(chat_id, "typing")

    reply_text = await get_llm_reply(
        user_msg=text,
        history=history[:-1],   # exclude the message we just saved
        is_owner=owner,
        user_name=user_name,
        bot_mood=bot_mood,
    )

    # ── Store bot reply ──────────────────────────────────────
    await db.add_message(chat_id, None, "assistant", reply_text)

    await msg.reply(reply_text)


# ─────────────────────────────────────────────────────────────
#  BOT COMMANDS REGISTRATION
# ─────────────────────────────────────────────────────────────

async def set_bot_commands():
    commands = [
        BotCommand(command="start",        description="Ruhi Ji ko wake up karo 🌸"),
        BotCommand(command="help",         description="Help menu dekho"),
        BotCommand(command="profile",      description="Apna profile dekho"),
        BotCommand(command="clear",        description="Memory clear karo"),
        BotCommand(command="reset",        description="Context reset karo"),
        BotCommand(command="lang",         description="Language toggle"),
        BotCommand(command="personality",  description="Bot ka mood dekho"),
        BotCommand(command="usage",        description="Chat summary lo"),
        BotCommand(command="summary",      description="Chat summary lo"),
        BotCommand(command="admin",        description="[Admin] Dashboard"),
        BotCommand(command="addadmin",     description="[Admin] Admin add karo"),
        BotCommand(command="removeadmin",  description="[Admin] Admin remove karo"),
        BotCommand(command="broadcast",    description="[Admin] Sab ko message bhejo"),
        BotCommand(command="ban",          description="[Admin] User ban karo"),
        BotCommand(command="unban",        description="[Admin] User unban karo"),
        BotCommand(command="totalusers",   description="[Admin] Total users dekho"),
        BotCommand(command="activeusers",  description="[Admin] Active users dekho"),
        BotCommand(command="forceclear",   description="[Admin] Kisi ki memory clear karo"),
        BotCommand(command="badwords",     description="[Admin] Bad words list dekho"),
        BotCommand(command="addbadword",   description="[Admin] Bad word add karo"),
        BotCommand(command="removebadword", description="[Admin] Bad word remove karo"),
        BotCommand(command="setphrase",    description="[Admin] Bot mood set karo"),
        BotCommand(command="shutdown",     description="[Admin] Bot sulate jao"),
        BotCommand(command="restart",      description="[Admin] Bot jagao"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())


# ─────────────────────────────────────────────────────────────
#  STARTUP / SHUTDOWN HOOKS
# ─────────────────────────────────────────────────────────────

async def on_startup():
    logger.info("🚀 Starting Ruhi Ji Bot...")
    await db.create_pool()
    await set_bot_commands()
    me = await bot.get_me()
    logger.info(f"✅ Bot running as @{me.username}")

    # Notify owner
    if OWNER_ID:
        try:
            await bot.send_message(
                OWNER_ID,
                "✨ Ruhi Ji online ho gayi hai Owner-sama! 🥺💕\n/admin se dashboard dekho."
            )
        except Exception:
            pass


async def on_shutdown():
    logger.info("Shutting down Ruhi Ji Bot...")
    await db.close_pool()
    await bot.session.close()


# ─────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
