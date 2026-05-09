"""
Ikkinchi bot uchun multiprocessing spawn — har bir jarayonda yangi Router() lar yaratiladi
(aiogram: bir Router faqat bitta Dispatcherga ulanishi mumkin).
"""
from __future__ import annotations

import asyncio
import logging
import sys


def run_bot_process(token: str, taronja: bool, label: str) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("bot.log", encoding="utf-8"),
        ],
    )
    log = logging.getLogger(__name__)

    from app.database.connection import init_db, close_db
    from app.services.fastsaver_api import api
    from app.bot.telegram_app import run_bot_instance

    async def _go() -> None:
        await init_db()
        log.info("Database initialized [%s]", label)
        try:
            await run_bot_instance(token, taronja=taronja, label=label)
        finally:
            await api.close()
            await close_db()
            log.info("Cleanup complete [%s]", label)

    asyncio.run(_go())
