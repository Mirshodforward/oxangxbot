import asyncio
import logging
import sys

from app.config import settings
from app.database.connection import init_db, close_db
from app.services.fastsaver_api import api
from app.bot.telegram_app import run_bot_instance

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot_taronja.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)


async def _run() -> None:
    token = (settings.TARONJA_BOT_TOKEN or "").strip()
    if not token:
        logger.error("TARONABOT_TOKEN .env da topilmadi")
        sys.exit(1)

    await init_db()
    logger.info("Database initialized [taronja]")
    try:
        await run_bot_instance(token, taronja=True, label="taronja")
    finally:
        await api.close()
        await close_db()
        logger.info("Cleanup complete [taronja]")


def main() -> None:
    logger.info("Taronja bot ishga tushmoqda (TARONABOT_TOKEN)")
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("Taronja to'xtatildi (Ctrl+C)")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Chiqildi")
    except Exception as e:
        logger.error("Fatal error: %s", e)
        sys.exit(1)
