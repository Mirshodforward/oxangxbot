import asyncio
import atexit
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

# Taronja subprocess — Ctrl+C / exit da to'xtatish uchun
_taronja_proc: multiprocessing.Process | None = None


def _stop_taronja_process(proc: multiprocessing.Process | None = None) -> None:
    """Taronja alohida jarayonini to'xtatish (Ctrl+C yoki Oxang tugaganda)."""
    p = proc if proc is not None else _taronja_proc
    if p is None or not p.is_alive():
        return
    logger.info("Taronja jarayoni to'xtatilmoqda (pid=%s)...", p.pid)
    p.terminate()
    p.join(timeout=12)
    if p.is_alive():
        logger.warning("Taronja SIGKILL...")
        p.kill()
        p.join(timeout=5)
    logger.info("Taronja to'xtatildi")


async def _run_single_bot(token: str, *, taronja: bool, label: str) -> None:
    await init_db()
    logger.info("Database initialized [%s]", label)
    try:
        await run_bot_instance(token, taronja=taronja, label=label)
    finally:
        await api.close()
        await close_db()
        logger.info("Cleanup complete [%s]", label)


async def _run_oxang_with_optional_taronja(
    taronja_process: multiprocessing.Process | None,
) -> None:
    try:
        await _run_single_bot(
            settings.BOT_TOKEN.strip(),
            taronja=False,
            label="oxang",
        )
    finally:
        _stop_taronja_process(taronja_process)


def _register_shutdown_hooks(taronja_process: multiprocessing.Process | None) -> None:
    """Chiqishda (Ctrl+C ham) Taronja subprocess to'xtasin."""
    if taronja_process is None:
        return
    atexit.register(_stop_taronja_process, taronja_process)


def main() -> None:
    global _taronja_proc

    mode = settings.BOT_RUN_MODE
    tar_tok = (settings.TARONJA_BOT_TOKEN or "").strip()
    tar_proc: multiprocessing.Process | None = None

    if mode == "taronja":
        if not tar_tok:
            logger.error("BOT_RUN_MODE=taronja lekin TARONABOT_TOKEN .env da yo'q")
            sys.exit(1)
        logger.info("Faqat Taronja bot (BOT_RUN_MODE=taronja)")
        try:
            asyncio.run(_run_single_bot(tar_tok, taronja=True, label="taronja"))
        except KeyboardInterrupt:
            logger.info("Taronja to'xtatildi (Ctrl+C)")
        return

    if mode == "oxang":
        logger.info("Faqat Oxang bot (BOT_RUN_MODE=oxang)")
        try:
            asyncio.run(_run_single_bot(settings.BOT_TOKEN.strip(), taronja=False, label="oxang"))
        except KeyboardInterrupt:
            logger.info("Oxang to'xtatildi (Ctrl+C)")
        return

    # both — Oxang asosiy jarayon + Taronja alohida subprocess
    if tar_tok:
        ctx = multiprocessing.get_context("spawn")
        tar_proc = ctx.Process(
            target=run_bot_process,
            args=(tar_tok, True, "taronja"),
            name="oxangxbot-taronja",
        )
        tar_proc.start()
        _taronja_proc = tar_proc
        _register_shutdown_hooks(tar_proc)
        logger.info("Taronja alohida jarayonda ishga tushdi (pid=%s)", tar_proc.pid)
    else:
        logger.warning("TARONABOT_TOKEN yo'q — faqat Oxang ishlaydi")

    try:
        asyncio.run(_run_oxang_with_optional_taronja(tar_proc))
    except KeyboardInterrupt:
        logger.info("Ikkala bot to'xtatildi (Ctrl+C)")
    finally:
        _stop_taronja_process(tar_proc)
        _taronja_proc = None


if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        main()
    except KeyboardInterrupt:
        _stop_taronja_process()
        logger.info("Chiqildi")
    except Exception as e:
        _stop_taronja_process()
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
