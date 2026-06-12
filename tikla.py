"""
oxangxbot: backups/*.sql zaxirasini DATABASE_URL bazasiga tiklash (psql).

Yangi serverda:
  1. PostgreSQL o'rnatilgan bo'lsin, `psql` PATH da bo'lsin
  2. `.env` da ulanish:
     DATABASE_URL=postgresql+asyncpg://miniuser:PAROL@localhost:5432/oxangxbot_db
  3. `backups/` papkasida .sql zaxira bo'lsin

Ishlatish:
  python tikla.py --yes
  python tikla.py --file backups/oxangxbot_db_20260611_132358.sql --yes
  python tikla.py --yes --create-db --drop-existing

Ehtiyot: `--drop-existing` joriy DB foydalanuvchisiga tegishli obyektlarni o'chiradi.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

_root = str(Path(__file__).resolve().parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from app.config import settings
from app.utils.pg_tools import db_params


def _psql_base(cfg: dict[str, str | int]) -> list[str]:
    psql = shutil.which("psql")
    if not psql:
        raise SystemExit(
            "psql topilmadi.\n"
            "PostgreSQL client o'rnating (masalan: postgresql-client)."
        )
    return [
        psql,
        "-h",
        str(cfg["host"]),
        "-p",
        str(cfg["port"]),
        "-U",
        str(cfg["user"]),
        "-v",
        "ON_ERROR_STOP=1",
    ]


def _run_psql(
    cfg: dict[str, str | int],
    env: dict[str, str],
    *,
    database: str,
    args: list[str],
) -> None:
    cmd = _psql_base(cfg) + ["-d", database] + args
    subprocess.run(cmd, env=env, check=True)


def _safe_db_name(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise SystemExit(f"Noto'g'ri baza nomi: {name!r}")
    return name


def _database_exists(cfg: dict[str, str | int], env: dict[str, str]) -> bool:
    db = _safe_db_name(str(cfg["database"]))
    result = subprocess.run(
        _psql_base(cfg)
        + [
            "-d",
            "postgres",
            "-tAc",
            f"SELECT 1 FROM pg_database WHERE datname = '{db}'",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise SystemExit(f"Bazani tekshirib bo'lmadi: {err}")
    return result.stdout.strip() == "1"


def _create_database(cfg: dict[str, str | int], env: dict[str, str]) -> None:
    db = _safe_db_name(str(cfg["database"]))
    user = str(cfg["user"])
    safe_db = db.replace('"', '""')
    safe_user = user.replace('"', '""')
    sql = f'CREATE DATABASE "{safe_db}" OWNER "{safe_user}"'
    print(f"Baza yaratilmoqda: {db}")
    _run_psql(cfg, env, database="postgres", args=["-c", sql])


def _public_table_count(cfg: dict[str, str | int], env: dict[str, str]) -> int:
    db = _safe_db_name(str(cfg["database"]))
    result = subprocess.run(
        _psql_base(cfg)
        + [
            "-d",
            db,
            "-tAc",
            "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public'",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise SystemExit(f"Jadvallarni sanab bo'lmadi: {err}")
    return int((result.stdout or "0").strip() or "0")


def _clean_existing_objects(cfg: dict[str, str | int], env: dict[str, str]) -> None:
    db = _safe_db_name(str(cfg["database"]))
    n = _public_table_count(cfg, env)
    if n == 0:
        print(f"Baza bo'sh ({db}) — tozalash o'tkazib yuborildi.")
        return

    print(f"Mavjud obyektlar tozalanmoqda ({n} ta jadval): {db}")
    _run_psql(
        cfg,
        env,
        database=db,
        args=["-c", "DROP OWNED BY CURRENT_USER CASCADE;"],
    )

    left = _public_table_count(cfg, env)
    if left > 0:
        raise SystemExit(
            f"{left} ta jadval qoldi (boshqa foydalanuvchiga tegishli).\n"
            "postgres superuser bilan bir marta bajaring:\n"
            f'  ALTER SCHEMA public OWNER TO "{cfg["user"]}";\n'
            "yoki barcha jadvallarni o'chirib, qayta: python tikla.py --yes --drop-existing"
        )


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
            "Zaxira faylini shu papkaga qo'ying."
        )
    return files[0]


def _pick_backup(backups_dir: Path, file_arg: Path | None) -> Path:
    if file_arg is not None:
        path = file_arg.resolve()
        if not path.is_file():
            raise SystemExit(f"Fayl topilmadi: {path}")
        return path
    return _latest_backup(backups_dir.resolve())


def run_restore(
    backup_path: Path,
    *,
    create_db: bool,
    drop_existing: bool,
) -> None:
    raw_url = (settings.DATABASE_URL or "").strip()
    if not raw_url:
        raise SystemExit("DATABASE_URL .env faylida topilmadi.")

    cfg = db_params(raw_url)
    db_name = str(cfg["database"])

    env = os.environ.copy()
    if cfg["password"]:
        env["PGPASSWORD"] = str(cfg["password"])

    print(
        f"Maqsad: {cfg['user']}@{cfg['host']}:{cfg['port']}/{db_name}"
    )
    print(f"Zaxira: {backup_path} ({backup_path.stat().st_size:,} bayt)")

    try:
        if create_db and not _database_exists(cfg, env):
            _create_database(cfg, env)
        elif not _database_exists(cfg, env):
            raise SystemExit(
                f"'{db_name}' bazasi mavjud emas.\n"
                "Yaratish uchun: python tikla.py --yes --create-db"
            )

        if drop_existing:
            _clean_existing_objects(cfg, env)

        print("Zaxira yuklanmoqda (psql)...")
        _run_psql(
            cfg,
            env,
            database=db_name,
            args=["-f", str(backup_path.resolve())],
        )
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"psql xato bilan tugadi (kod {exc.returncode}).") from exc
    finally:
        env.pop("PGPASSWORD", None)

    print("Tayyor: baza tiklandi.")
    print("Botni ishga tushiring: python main.py")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="oxangxbot SQL zaxiradan PostgreSQL bazasini tiklash.",
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
        "--create-db",
        action="store_true",
        help="Baza yo'q bo'lsa CREATE DATABASE qilish",
    )
    parser.add_argument(
        "--drop-existing",
        action="store_true",
        help="Tiklashdan oldin joriy foydalanuvchining obyektlarini o'chirish",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Tiklashni tasdiqlash (bundsiz hech narsa qilinmaydi)",
    )
    args = parser.parse_args()

    if not args.yes:
        print(
            "Bu skript .sql zaxirani DATABASE_URL bazasiga yozadi.\n"
            "Mavjud ma'lumotlar ustiga yozilishi yoki xato berishi mumkin.\n"
            "Davom etish uchun:\n"
            "  python tikla.py --yes\n"
            "Toza tiklash (eski jadvallarni o'chirish):\n"
            "  python tikla.py --yes --drop-existing\n"
            "Baza yo'q bo'lsa:\n"
            "  python tikla.py --yes --create-db --drop-existing",
        )
        sys.exit(0)

    backup_path = _pick_backup(args.dir, args.file)
    run_restore(
        backup_path,
        create_db=args.create_db,
        drop_existing=args.drop_existing,
    )


if __name__ == "__main__":
    main()
