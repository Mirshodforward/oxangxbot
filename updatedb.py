"""
Mavjud SQL bazasini yangi model ustunlari bilan yangilash.
Ishlatish: python updatedb.py

.env dagi DATABASE_URL ishlatiladi (app.config.settings).
"""
from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


# Har bir yozuv: jadval, ustun, tekshiruv va ALTER (dialect bo'yicha)
MIGRATIONS: list[dict] = [
    {
        "table": "required_channels",
        "column": "invite_link",
        "sqlite": "ALTER TABLE required_channels ADD COLUMN invite_link VARCHAR(500)",
        "postgresql": (
            "ALTER TABLE required_channels ADD COLUMN IF NOT EXISTS invite_link VARCHAR(500)"
        ),
    },
]


async def _table_exists(conn, dialect: str, table: str) -> bool:
    if dialect == "sqlite":
        r = await conn.execute(
            text(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=:t LIMIT 1"
            ),
            {"t": table},
        )
        return r.fetchone() is not None
    if dialect == "postgresql":
        r = await conn.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = :t LIMIT 1"
            ),
            {"t": table},
        )
        return r.fetchone() is not None
    return False


async def _column_exists(conn, dialect: str, table: str, column: str) -> bool:
    if dialect == "sqlite":
        r = await conn.execute(text(f'PRAGMA table_info("{table}")'))
        for row in r.fetchall():
            if row[1] == column:
                return True
        return False
    if dialect == "postgresql":
        r = await conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c "
                "LIMIT 1"
            ),
            {"t": table, "c": column},
        )
        return r.fetchone() is not None
    return False


async def run_migrations() -> int:
    from app.config import settings

    url = settings.DATABASE_URL
    engine = create_async_engine(url, echo=False)

    try:
        dialect = engine.dialect.name
        if dialect not in ("sqlite", "postgresql"):
            print(f"Qo'llab-quvvatlanmaydigan dialect: {dialect}. Faqat sqlite yoki postgresql.")
            return 1

        async with engine.begin() as conn:
            for m in MIGRATIONS:
                table = m["table"]
                column = m["column"]

                if not await _table_exists(conn, dialect, table):
                    print(f"[!] Jadval '{table}' yo'q - o'tkazib yuborildi: {column}")
                    continue

                if await _column_exists(conn, dialect, table, column):
                    print(f"[=] {table}.{column} - allaqachon bor")
                    continue

                sql = m.get(dialect)
                if not sql:
                    print(f"[!] {table}.{column} uchun {dialect} SQL yo'q")
                    continue

                await conn.execute(text(sql))
                print(f"[+] {table}.{column} qo'shildi ({dialect})")

        print("Tayyor.")
        return 0
    except Exception as e:
        print(f"Xatolik: {e}", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()


def main() -> None:
    code = asyncio.run(run_migrations())
    raise SystemExit(code)


if __name__ == "__main__":
    main()
