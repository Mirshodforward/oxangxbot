import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from app.config import settings
from app.database.connection import init_db, close_db
from app.services.fastsaver_api import api
from app.bot.middlewares import DatabaseMiddleware, UserMiddleware, ThrottlingMiddleware, SubscriptionMiddleware
from app.bot.handlers import common, download, music, voice, admin


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)

logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    """Startup tasks"""
    logger.info("Bot starting up...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Get bot info
    bot_info = await bot.get_me()
    logger.info(f"Bot: @{bot_info.username} ({bot_info.id})")
    
    # Check API health
    try:
        stats = await api.get_usage_stats()
        if not stats.error:
            logger.info(f"API Points: {stats.points}")
    except Exception as e:
        logger.warning(f"Could not check API status: {e}")
        
    # Set bot commands menu
    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="Botni ishga tushirish (Start bot)"),
            BotCommand(command="help", description="Yordam va qoidalar (Help)"),
            BotCommand(command="shazam", description="Qo'shiqni aniqlash (Identify song)"),
            BotCommand(command="search", description="Musiqa qidirish yoki chatga yozing (Search)"),
            BotCommand(command="top", description="Top musiqalar (Top charts)"),
            BotCommand(command="stats", description="Bot statistikasi (Statistics)"),
            BotCommand(command="language", description="Tilni o'zgartirish (Change language)"),
        ])
        logger.info("Bot commands menu updated")
    except Exception as e:
        logger.warning(f"Could not set bot commands: {e}")


async def on_shutdown(bot: Bot):
    """Shutdown tasks"""
    logger.info("Bot shutting down...")
    
    # Close API session
    await api.close()
    
    # Close database connections
    await close_db()
    
    logger.info("Cleanup complete")


def setup_routers(dp: Dispatcher):
    """Register all routers"""
    # Order matters! More specific routers first
    dp.include_router(admin.router)  # Admin first (highest priority)
    dp.include_router(common.router)
    dp.include_router(music.router)
    dp.include_router(voice.router)  # Voice commands after music (lower priority)
    dp.include_router(download.router)


def setup_middlewares(dp: Dispatcher):
    """Register middlewares"""
    # Order matters! Database first, then user, then subscription
    dp.message.middleware(ThrottlingMiddleware(rate_limit=0.3))
    dp.message.middleware(DatabaseMiddleware())
    dp.message.middleware(UserMiddleware())
    dp.message.middleware(SubscriptionMiddleware())
    
    dp.callback_query.middleware(ThrottlingMiddleware(rate_limit=0.3))
    dp.callback_query.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(UserMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

async def main():
    """Main function to start the bot"""
    # Create bot instance
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Create dispatcher with memory storage for FSM
    dp = Dispatcher(storage=MemoryStorage())
    
    # Setup middlewares and routers
    setup_middlewares(dp)
    setup_routers(dp)
    
    # Register startup/shutdown handlers
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    try:
        logger.info("Starting polling...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
