"""
Barcha SQLAlchemy modellari bo‘yicha jadvallarni bazadan o‘chirish (DATA yo‘qoladi).

Ishlatish:
  python rest.py --yes

.env dagi DATABASE_URL ishlatiladi.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy.ext.asyncio import create_async_engine


async def _drop_all() -> None:
    from app.config import settings
    from app.database.connection import Base

    import app.database.models  # noqa: F401 — Base.metadata jadvallar bilan to‘ladi

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Barcha DB jadvallarini o‘chirish")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Tasdiq (bu flagsiz hech narsa qilinmaydi)",
    )
    args = parser.parse_args()
    if not args.yes:
        print(
            "Xavfli operatsiya: barcha jadvallar va qatorlar o‘chiriladi.\n"
            "Davom etish uchun:  python rest.py --yes",
            file=sys.stderr,
        )
        return 1

    try:
        asyncio.run(_drop_all())
    except Exception as e:
        print(f"Xatolik: {e}", file=sys.stderr)
        return 1

    print("Tayyor: modellarga mos barcha jadvallar o‘chirildi.")
    print(
        "Eslatma: PostgreSQL da ENUM turlari (masalan platform) qolgan bo‘lishi mumkin — "
        "kerak bo‘lsa qo‘lda DROP TYPE ... CASCADE qiling.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
