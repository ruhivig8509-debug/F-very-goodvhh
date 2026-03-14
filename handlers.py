"""
Telegram handlers for Ruhi Ji Bot
All command and message handlers
"""

import logging
from typing import Optional

from telegram import Update, Chat
from telegram.ext import ContextTypes
from telegram.constants import ParseMode, ChatAction

from config import (
    START_MESSAGE, HELP_MESSAGE, ADMIN_DASHBOARD,
    OWNER_USERNAME
)
from database import db
from ai_client import ai_client
from utils import (
    is_owner, contains_wake_phrase, format_profile,
    format_stats, extract_user_id, sanitize_username
)

logger = logging.getLogger(__name__)


class MessageHandler:
    """Handler for all message processing"""
    
    @staticmethod
    async def should_respond(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Determine if bot should respond to this message"""
        message = update.message
        if not message or not message.text:
            return False
        
        chat_type = message.chat.type
        
        # Always respond in private chats
        if chat_type == 'private':
            return True
        
        # In groups, check for wake phrase or reply to bot
        text = message.text.lower()
        
        # Check if it's a reply to the bot
        if message.reply_to_message:
            bot_username = (await context.bot.get_me()).username
            if message.reply_to_message.from_user.username == bot_username:
                # Activate session on reply
                await db.activate_session(message.chat_id)
                return True
        
        # Check for wake phrase
        if contains_wake_phrase(message.text):
            await db.activate_session(message.chat_id)
            return True
        
        # Check if session is active
        if await db.is_session_active(message.chat_id):
            return True
        
        return False
    
    @staticmethod
    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Main message handler"""
        message = update.message
        if not message or not message.text:
            return
        
        user = message.from_user
        chat = message.chat
        
        # Get or create user and chat
        user_data = await db.get_or_create_user(
            user.id, 
            user.username, 
            user.first_name
        )
        
        await db.get_or_create_chat(
            chat.id,
            chat.type,
            chat.title if hasattr(chat, 'title') else None
        )
        
        # Check if user is banned
        if await db.is_user_banned(user.id):
            return
        
        # Check if contains bad words
        if await db.contains_bad_word(message.text):
            await message.reply_text(
                "Aye aye aye! Language beta 😏 Ye allowed nahi hai yahan 🚫"
            )
            return
        
        # Check if should respond
        if not await MessageHandler.should_respond(update, context):
            return
        
        # Send typing action
        await context.bot.send_chat_action(
            chat_id=chat.id, 
            action=ChatAction.TYPING
        )
        
        # Get conversation history
        history = await db.get_conversation_history(chat.id)
        
        # Determine if user is owner
        user_is_owner = is_owner(user.username)
        
        # Generate AI response
        response = await ai_client.generate_response(
            user_message=message.text,
            conversation_history=history,
            username=user.username,
            first_name=user.first_name,
            is_owner=user_is_owner
        )
        
        # Save messages to database
        await db.save_message(chat.id, user.id, "user", message.text)
        await db.save_message(chat.id, 0, "assistant", response)
        
        # Increment message count
        await db.increment_message_count(user.id)
        
        # Send response
        await message.reply_text(response)


class CommandHandler:
    """Handler for all commands"""
    
    @staticmethod
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        user = update.effective_user
        await db.get_or_create_user(user.id, user.username, user.first_name)
        
        if update.effective_chat.type == 'private':
            await db.get_or_create_chat(
                update.effective_chat.id,
                'private'
            )
        
        await update.message.reply_text(START_MESSAGE)
    
    @staticmethod
    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command"""
        await update.message.reply_text(HELP_MESSAGE)
    
    @staticmethod
    async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /profile command"""
        user = update.effective_user
        user_data = await db.get_user_stats(user.id)
        
        if user_data:
            await update.message.reply_text(format_profile(user_data))
        else:
            await update.message.reply_text(
                "Profile nahi mila beta 🥺 /start karo pehle"
            )
    
    @staticmethod
    async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /clear or /reset command"""
        chat_id = update.effective_chat.id
        await db.clear_conversation(chat_id)
        await db.deactivate_session(chat_id)
        
        await update.message.reply_text(
            "✨ Memory cleared bestie! Fresh start 🌸\n"
            "Ab bolo 'Ruhi Ji' aur naya session shuru karo 💅"
        )
    
    @staticmethod
    async def lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /lang command"""
        user = update.effective_user
        current = await db.get_user_stats(user.id)
        
        if current:
            new_lang = 'english' if current.get('preferred_lang') == 'hinglish' else 'hinglish'
            await db.update_user_lang(user.id, new_lang)
            await update.message.reply_text(
                f"Language switched to: {new_lang.upper()} ✨\n"
                "Par main toh Hinglish hi bolungi mostly 😏💅"
            )
        else:
            await update.message.reply_text("Pehle /start karo na beta 🥺")
    
    @staticmethod
    async def personality(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /personality command"""
        mood = await db.get_bot_mood()
        
        mood_descriptions = {
            'savage': "😏 SAVAGE MODE ON - Respect se Bezzati ready hai 💅",
            'sweet': "🥺 SWEET MODE - Aaj pyaar baatne ka mann hai 💕",
            'neutral': "😌 NEUTRAL MODE - Dekho kaise mood hai 🌸",
            'chaotic': "🔥 CHAOTIC MODE - Anything can happen 💀"
        }
        
        description = mood_descriptions.get(mood, mood_descriptions['savage'])
        await update.message.reply_text(
            f"╭───────────────────⦿\n"
            f"│ 🎭 ᴄᴜʀʀᴇɴᴛ ᴍᴏᴏᴅ\n"
            f"├───────────────────⦿\n"
            f"│ {description}\n"
            f"╰───────────────────⦿"
        )
    
    @staticmethod
    async def usage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /usage command"""
        user = update.effective_user
        user_data = await db.get_user_stats(user.id)
        
        if user_data:
            await update.message.reply_text(
                f"📊 ᴛᴏᴛᴀʟ ᴍᴇssᴀɢᴇs: {user_data.get('message_count', 0)}\n"
                f"🕐 ʟᴀsᴛ ᴀᴄᴛɪᴠᴇ: {user_data.get('last_active', 'N/A')}"
            )
        else:
            await update.message.reply_text("Stats nahi mila 🥺")
    
    @staticmethod
    async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /summary command"""
        chat_id = update.effective_chat.id
        
        await context.bot.send_chat_action(
            chat_id=chat_id, 
            action=ChatAction.TYPING
        )
        
        messages_text = await db.get_recent_messages_summary(chat_id)
        summary = await ai_client.generate_summary(messages_text)
        
        await update.message.reply_text(
            f"📝 ʀᴇᴄᴇɴᴛ ᴄʜᴀᴛ sᴜᴍᴍᴀʀʏ:\n\n{summary}"
        )


class AdminCommandHandler:
    """Handler for admin-only commands"""
    
    @staticmethod
    def _check_owner(update: Update) -> bool:
        """Check if user is owner"""
        username = update.effective_user.username
        return is_owner(username)
    
    @staticmethod
    async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /admin command"""
        if not AdminCommandHandler._check_owner(update):
            await update.message.reply_text(
                "Arre beta, ye toh sirf Owner ke liye hai 😏💅"
            )
            return
        
        await update.message.reply_text(ADMIN_DASHBOARD)
    
    @staticmethod
    async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /broadcast command"""
        if not AdminCommandHandler._check_owner(update):
            await update.message.reply_text("Owner-only command hai ye 😏")
            return
        
        if not context.args:
            await update.message.reply_text(
                "Usage: /broadcast <message>\nExample: /broadcast Hello everyone! 🎉"
            )
            return
        
        broadcast_message = ' '.join(context.args)
        user_ids = await db.get_all_user_ids()
        chat_ids = await db.get_all_chat_ids()
        
        success_count = 0
        fail_count = 0
        
        # Broadcast to all users
        all_targets = set(user_ids + chat_ids)
        
        for target_id in all_targets:
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=f"📢 ʙʀᴏᴀᴅᴄᴀsᴛ ғʀᴏᴍ ᴏᴡɴᴇʀ:\n\n{broadcast_message}"
                )
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to send to {target_id}: {e}")
                fail_count += 1
        
        await update.message.reply_text(
            f"✅ Broadcast complete!\n"
            f"▸ Sent: {success_count}\n"
            f"▸ Failed: {fail_count}"
        )
    
    @staticmethod
    async def totalusers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /totalusers command"""
        if not AdminCommandHandler._check_owner(update):
            await update.message.reply_text("Owner-only hai ye 😏")
            return
        
        total = await db.get_total_users()
        await update.message.reply_text(f"📊 Total Users: {total}")
    
    @staticmethod
    async def activeusers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /activeusers command"""
        if not AdminCommandHandler._check_owner(update):
            await update.message.reply_text("Owner-only hai ye 😏")
            return
        
        active = await db.get_active_users(hours=24)
        await update.message.reply_text(f"📊 Active Users (24h): {active}")
    
    @staticmethod
    async def forceclear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /forceclear command"""
        if not AdminCommandHandler._check_owner(update):
            await update.message.reply_text("Owner-only hai ye 😏")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /forceclear <user_id>")
            return
        
        user_id = extract_user_id(context.args[0])
        if not user_id:
            await update.message.reply_text("Invalid user ID")
            return
        
        deleted = await db.clear_user_context(user_id)
        await update.message.reply_text(
            f"✅ Cleared {deleted} messages for user {user_id}"
        )
    
    @staticmethod
    async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /ban command"""
        if not AdminCommandHandler._check_owner(update):
            await update.message.reply_text("Owner-only hai ye 😏")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /ban <user_id>")
            return
        
        user_id = extract_user_id(context.args[0])
        if not user_id:
            await update.message.reply_text("Invalid user ID")
            return
        
        success = await db.ban_user(user_id)
        if success:
            await update.message.reply_text(f"🚫 User {user_id} banned!")
        else:
            await update.message.reply_text("User not found")
    
    @staticmethod
    async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /unban command"""
        if not AdminCommandHandler._check_owner(update):
            await update.message.reply_text("Owner-only hai ye 😏")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /unban <user_id>")
            return
        
        user_id = extract_user_id(context.args[0])
        if not user_id:
            await update.message.reply_text("Invalid user ID")
            return
        
        success = await db.unban_user(user_id)
        if success:
            await update.message.reply_text(f"✅ User {user_id} unbanned!")
        else:
            await update.message.reply_text("User not found")
    
    @staticmethod
    async def badwords(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /badwords command"""
        if not AdminCommandHandler._check_owner(update):
            await update.message.reply_text("Owner-only hai ye 😏")
            return
        
        words = await db.get_bad_words()
        if words:
            word_list = "\n".join([f"▸ {w}" for w in words])
            await update.message.reply_text(
                f"🚫 Bad Words List:\n{word_list}"
            )
        else:
            await update.message.reply_text("No bad words configured yet")
    
    @staticmethod
    async def addbadword(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /addbadword command"""
        if not AdminCommandHandler._check_owner(update):
            await update.message.reply_text("Owner-only hai ye 😏")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /addbadword <word>")
            return
        
        word = ' '.join(context.args)
        success = await db.add_bad_word(word)
        
        if success:
            await update.message.reply_text(f"✅ Added '{word}' to bad words list")
        else:
            await update.message.reply_text("Word already exists in list")
    
    @staticmethod
    async def removebadword(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /removebadword command"""
        if not AdminCommandHandler._check_owner(update):
            await update.message.reply_text("Owner-only hai ye 😏")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /removebadword <word>")
            return
        
        word = ' '.join(context.args)
        success = await db.remove_bad_word(word)
        
        if success:
            await update.message.reply_text(f"✅ Removed '{word}' from bad words list")
        else:
            await update.message.reply_text("Word not found in list")
