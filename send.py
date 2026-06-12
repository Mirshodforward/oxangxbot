"""
oxangxbot DB zaxirasini (.sql) Telegram chatga yuborish.

`.env`:
  BACKUP_BOT_TOKEN=<zaxira bot tokeni>
  BACKUP_SEND_CHAT_ID=5081646633

Ishlatish:
  python send.py
  python send.py --file backups/oxangxbot_db_20260101_120000.sql
  python send.py --make-backup   # avval backup.py, keyin yuborish

Telegram hujjat limiti: 50 MB.
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

_root = str(Path(__file__).resolve().parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from aiogram import Bot
from aiogram.types import FSInputFile

from app.config import settings

TELEGRAM_MAX_BYTES = 50 * 1024 * 1024


def _resolve_chat_id() -> int:
    raw = (settings.BACKUP_SEND_CHAT_ID or "").strip()
    if not raw:
        raise SystemExit("BACKUP_SEND_CHAT_ID .env da ko'rsatilmagan.")
    try:
        return int(raw)
    except ValueError as exc:
        raise SystemExit("BACKUP_SEND_CHAT_ID butun son bo'lishi kerak.") from exc


def _resolve_token() -> str:
    token = (settings.BACKUP_BOT_TOKEN or "").strip()
    if not token:
        raise SystemExit(
            "BACKUP_BOT_TOKEN .env da bo'sh.\n"
            "Masalan: BACKUP_BOT_TOKEN=123456:ABC..."
        )
    return token


def _latest_backup(backups_dir: Path) -> Path:
    if not backups_dir.is_dir():
        raise SystemExit(f"Zaxira papkasi yo'q: {backups_dir}")
    files = sorted(
        backups_dir.glob("*.sql"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not files:
        raise SystemExit(
            f"{backups_dir} ichida .sql zaxira topilmadi. "
            "Avval: python backup.py"
        )
    return files[0]


def _pick_backup(backups_dir: Path, file_arg: Path | None) -> Path:
    if file_arg is not None:
        path = file_arg.resolve()
        if not path.is_file():
            raise SystemExit(f"Fayl topilmadi: {path}")
        return path
    return _latest_backup(backups_dir.resolve())


async def _send_document(token: str, chat_id: int, path: Path) -> None:
    size = path.stat().st_size
    if size > TELEGRAM_MAX_BYTES:
        mb = size / (1024 * 1024)
        raise SystemExit(
            f"Fayl juda katta ({mb:.1f} MB). Telegram limiti 50 MB.\n"
            "Zaxirani siqing yoki boshqa usuldan foydalaning."
        )

    bot = Bot(token=token)
    try:
        await bot.send_document(
            chat_id=chat_id,
            document=FSInputFile(path),
            caption=(
                f"📦 oxangxbot DB zaxira\n"
                f"<code>{path.name}</code>\n({size:,} bayt)"
            ),
        )
    finally:
        await bot.session.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SQL zaxirani Telegram chatga yuborish.",
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path("backups"),
        help="Zaxira papkasi (default: backups)",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Aniq .sql fayl (berilmasa — eng yangisi)",
    )
    parser.add_argument(
        "--make-backup",
        action="store_true",
        help="Yuborishdan oldin python backup.py ishga tushirish",
    )
    args = parser.parse_args()

    if args.make_backup:
        print("Zaxira olinmoqda (backup.py)...")
        subprocess.run(
            [sys.executable, str(Path(_root) / "backup.py"), "--dir", str(args.dir)],
            check=True,
        )

    path = _pick_backup(args.dir, args.file)
    token = _resolve_token()
    chat_id = _resolve_chat_id()

    print(f"Yuborilmoqda: {path}")
    print(f"Chat ID: {chat_id}")

    asyncio.run(_send_document(token, chat_id, path))
    print("Tayyor: fayl yuborildi.")


if __name__ == "__main__":
    main()
