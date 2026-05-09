import asyncio
import logging
import multiprocessing
import sys

from app.config import settings
from app.database.connection import init_db, close_db
from app.services.fastsaver_api import api
from app.bot.telegram_app import run_bot_instance
from app.bot.subprocess_entry import run_bot_process


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)


async def _run_oxang_only(taronja_process: multiprocessing.Process | None) -> None:
    await init_db()
    logger.info("Database initialized")
    try:
        await run_bot_instance(
            settings.BOT_TOKEN.strip(),
            taronja=False,
            label="oxang",
        )
    finally:
        await api.close()
        await close_db()
        logger.info("Cleanup complete [oxang]")
        if taronja_process is not None:
            if taronja_process.is_alive():
                taronja_process.terminate()
                taronja_process.join(timeout=15)
            if taronja_process.is_alive():
                taronja_process.kill()


def main() -> None:
    tar_tok = (settings.TARONJA_BOT_TOKEN or "").strip()
    tar_proc: multiprocessing.Process | None = None

    if tar_tok:
        ctx = multiprocessing.get_context("spawn")
        tar_proc = ctx.Process(
            target=run_bot_process,
            args=(tar_tok, True, "taronja"),
            name="oxangxbot-taronja",
        )
        tar_proc.start()
        logger.info("Taronja alohida jarayonda ishga tushdi (pid=%s)", tar_proc.pid)

    try:
        asyncio.run(_run_oxang_only(tar_proc))
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        if tar_proc is not None and tar_proc.is_alive():
            tar_proc.terminate()
            tar_proc.join(timeout=10)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        main()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
