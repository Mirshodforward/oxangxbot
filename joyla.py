"""
users.json dagi Telegram user_id larni users_taronabot jadvaliga yangi user sifatida yozadi.
Takroriy user_id o'tkazib yuboriladi.

Ishlatish (loyiha ildizidan):
  python joyla.py
  python joyla.py path/to/users.json

.env dagi DATABASE_URL ishlatiladi.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select

from app.database.connection import async_session
from app.database.models import UserTaronja


def _load_user_ids(path: Path) -> list[int]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "user_ids" in raw:
        raw = raw["user_ids"]
    if not isinstance(raw, list):
        raise ValueError("users.json: kutilgan format — [] yoki {\"user_ids\": []}")

    out: list[int] = []
    for x in raw:
        if isinstance(x, dict):
            uid = x.get("user_id") or x.get("id")
            if uid is None:
                continue
        else:
            uid = x
        try:
            out.append(int(uid))
        except (TypeError, ValueError):
            continue

    # tartibni saqlab, noyob
    seen: set[int] = set()
    unique: list[int] = []
    for u in out:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique


async def import_users(json_path: Path) -> tuple[int, int]:
    """(qo'shilgan, o'tkazilgan)"""
    ids = _load_user_ids(json_path)
    if not ids:
        return 0, 0

    added = 0
    skipped = 0

    async with async_session() as session:
        result = await session.execute(
            select(UserTaronja.user_id).where(UserTaronja.user_id.in_(ids))
        )
        existing = {row[0] for row in result.fetchall()}

        for uid in ids:
            if uid in existing:
                skipped += 1
                continue
            session.add(
                UserTaronja(
                    user_id=uid,
                    username=None,
                    language_code="uz",
                )
            )
            existing.add(uid)
            added += 1

        if added:
            await session.commit()

    return added, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="users.json → users_taronabot")
    parser.add_argument(
        "json_file",
        nargs="?",
        default="users.json",
        help="JSON fayl (default: users.json)",
    )
    args = parser.parse_args()
    path = Path(args.json_file).resolve()
    if not path.is_file():
        print(f"Fayl topilmadi: {path}", file=sys.stderr)
        return 1

    try:
        added, skipped = asyncio.run(import_users(path))
    except Exception as e:
        print(f"Xato: {e}", file=sys.stderr)
        return 1

    print(f"Jami ID: {added + skipped} | Yangi qo'shildi: {added} | Allaqachon bor: {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
