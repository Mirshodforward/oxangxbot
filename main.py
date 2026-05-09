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
from app.bot.middlewares import (
    DatabaseMiddleware,
    UserMiddleware,
    ThrottlingMiddleware,
    SubscriptionMiddleware,
)
from app.bot.handlers import common, download, music, voice, admin


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    logger.info("Bot starting up...")
    bot_info = await bot.get_me()
    logger.info(f"Bot: @{bot_info.username} ({bot_info.id})")

    try:
        stats = await api.get_usage_stats()
        if not stats.error:
            logger.info(f"API Points: {stats.points}")
    except Exception as e:
        logger.warning(f"Could not check API status: {e}")

    try:
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Botni ishga tushirish (Start bot)"),
                BotCommand(command="help", description="Yordam va buyruqlar (Help)"),
                BotCommand(command="shazam", description="Qo'shiqni aniqlash (Identify song)"),
                BotCommand(command="search", description="Musiqa qidirish (Search)"),
                BotCommand(command="top", description="Top musiqalar (Top charts)"),
                BotCommand(command="lyrics", description="Qo'shiq matni (Lyrics)"),
                BotCommand(command="stats", description="Statistika (Statistics)"),
                BotCommand(command="settings", description="Sozlamalar (Settings)"),
                BotCommand(command="language", description="Tilni o'zgartirish (Change language)"),
                BotCommand(command="cancel", description="Joriy amalni bekor qilish (Cancel)"),
            ]
        )
        logger.info("Bot commands menu updated")
    except Exception as e:
        logger.warning(f"Could not set bot commands: {e}")


def setup_routers(dp: Dispatcher):
    dp.include_router(admin.router)
    dp.include_router(common.router)
    dp.include_router(music.router)
    dp.include_router(voice.router)
    dp.include_router(download.router)


def setup_middlewares(dp: Dispatcher, *, taronja: bool = False):
    dp.message.middleware(ThrottlingMiddleware(rate_limit=0.3))
    dp.message.middleware(DatabaseMiddleware())
    dp.message.middleware(UserMiddleware(taronja=taronja))
    dp.message.middleware(SubscriptionMiddleware())

    dp.callback_query.middleware(ThrottlingMiddleware(rate_limit=0.3))
    dp.callback_query.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(UserMiddleware(taronja=taronja))
    dp.callback_query.middleware(SubscriptionMiddleware())


async def run_bot_instance(token: str, *, taronja: bool, label: str):
    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    setup_middlewares(dp, taronja=taronja)
    setup_routers(dp)
    dp.startup.register(on_startup)

    logger.info("[%s] Polling ishga tushmoqda...", label)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


async def main():
    await init_db()
    logger.info("Database initialized")

    tasks = [
        asyncio.create_task(
            run_bot_instance(settings.BOT_TOKEN.strip(), taronja=False, label="oxang")
        )
    ]

    tar_tok = (settings.TARONJA_BOT_TOKEN or "").strip()
    if tar_tok:
        tasks.append(
            asyncio.create_task(
                run_bot_instance(tar_tok, taronja=True, label="taronja")
            )
        )

    try:
        await asyncio.gather(*tasks)
    finally:
        await api.close()
        await close_db()
        logger.info("Cleanup complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
