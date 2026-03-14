"""
Ruhi Ji - Telegram Bot Main Entry Point
Production-ready bot with PostgreSQL persistence and Hugging Face AI
"""

import asyncio
import logging
import signal
import sys
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler as TelegramCommandHandler,
    MessageHandler as TelegramMessageHandler,
    filters,
    ContextTypes
)

from config import TELEGRAM_BOT_TOKEN, HF_TOKEN, DATABASE_URL
from database import db
from handlers import MessageHandler, CommandHandler, AdminCommandHandler
from web_server import start_web_server, update_status

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Reduce noise from libraries
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)


class RuhiJiBot:
    """Main bot class"""
    
    def __init__(self):
        self.application: Optional[Application] = None
        self._shutdown_event = asyncio.Event()
    
    async def post_init(self, application: Application) -> None:
        """Post-initialization hook"""
        logger.info("Bot post-initialization started")
        
        # Connect to database
        try:
            await db.connect()
            logger.info("Database connected successfully")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
        
        update_status("running")
        logger.info("Ruhi Ji Bot is now running! 👑")
    
    async def post_shutdown(self, application: Application) -> None:
        """Post-shutdown hook"""
        logger.info("Bot shutting down...")
        await db.disconnect()
        update_status("stopped")
        logger.info("Bot shutdown complete")
    
    def setup_handlers(self, application: Application) -> None:
        """Setup all command and message handlers"""
        
        # User Commands
        application.add_handler(TelegramCommandHandler("start", CommandHandler.start))
        application.add_handler(TelegramCommandHandler("help", CommandHandler.help_command))
        application.add_handler(TelegramCommandHandler("profile", CommandHandler.profile))
        application.add_handler(TelegramCommandHandler("clear", CommandHandler.clear))
        application.add_handler(TelegramCommandHandler("reset", CommandHandler.clear))
        application.add_handler(TelegramCommandHandler("lang", CommandHandler.lang))
        application.add_handler(TelegramCommandHandler("personality", CommandHandler.personality))
        application.add_handler(TelegramCommandHandler("usage", CommandHandler.usage))
        application.add_handler(TelegramCommandHandler("summary", CommandHandler.summary))
        
        # Admin Commands
        application.add_handler(TelegramCommandHandler("admin", AdminCommandHandler.admin))
        application.add_handler(TelegramCommandHandler("broadcast", AdminCommandHandler.broadcast))
        application.add_handler(TelegramCommandHandler("totalusers", AdminCommandHandler.totalusers))
        application.add_handler(TelegramCommandHandler("activeusers", AdminCommandHandler.activeusers))
        application.add_handler(TelegramCommandHandler("forceclear", AdminCommandHandler.forceclear))
        application.add_handler(TelegramCommandHandler("ban", AdminCommandHandler.ban))
        application.add_handler(TelegramCommandHandler("unban", AdminCommandHandler.unban))
        application.add_handler(TelegramCommandHandler("badwords", AdminCommandHandler.badwords))
        application.add_handler(TelegramCommandHandler("addbadword", AdminCommandHandler.addbadword))
        application.add_handler(TelegramCommandHandler("removebadword", AdminCommandHandler.removebadword))
        
        # Message handler (must be added last)
        application.add_handler(TelegramMessageHandler(
            filters.TEXT & ~filters.COMMAND,
            MessageHandler.handle_message
        ))
        
        # Error handler
        application.add_error_handler(self.error_handler)
        
        logger.info("All handlers registered successfully")
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors"""
        logger.error(f"Exception while handling an update: {context.error}")
        
        # Try to notify user
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "Oops! Kuch gadbad ho gayi 🥺 Please try again later 💕"
                )
            except Exception:
                pass
    
    def run(self) -> None:
        """Start the bot"""
        # Validate configuration
        if not TELEGRAM_BOT_TOKEN:
            logger.error("TELEGRAM_BOT_TOKEN not set!")
            sys.exit(1)
        
        if not HF_TOKEN:
            logger.error("HF_TOKEN not set!")
            sys.exit(1)
        
        if not DATABASE_URL:
            logger.error("DATABASE_URL not set!")
            sys.exit(1)
        
        # Start web server for Render health checks
        start_web_server()
        update_status("starting")
        
        # Build application
        self.application = (
            Application.builder()
            .token(TELEGRAM_BOT_TOKEN)
            .post_init(self.post_init)
            .post_shutdown(self.post_shutdown)
            .build()
        )
        
        # Setup handlers
        self.setup_handlers(self.application)
        
        # Run the bot
        logger.info("Starting Ruhi Ji Bot... 👑")
        
        # Use run_polling with proper shutdown handling
        self.application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            close_loop=False
        )


def main():
    """Main entry point"""
    bot = RuhiJiBot()
    
    # Handle graceful shutdown
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
