"""PostgreSQL backup/restore uchun pg_dump/psql parametrlari."""

from __future__ import annotations

import os
from typing import Mapping

from sqlalchemy.engine import make_url


def _normalize_host(host: str | None) -> str:
    """localhost → 127.0.0.1 (IPv6 ::1 va pg_hba chalkashligini kamaytirish)."""
    h = (host or "localhost").strip()
    if h.lower() in ("localhost", "::1"):
        return "127.0.0.1"
    return h


def db_params(database_url: str) -> dict[str, str | int]:
    """SQLAlchemy URL → pg_dump/psql ulanish parametrlari."""
    u = make_url(database_url.strip().strip('"').strip("'"))
    return {
        "host": _normalize_host(u.host),
        "port": int(u.port or 5432),
        "user": u.username or "postgres",
        "password": u.password or "",
        "database": u.database or "postgres",
    }


def pg_env(cfg: Mapping[str, str | int]) -> dict[str, str]:
    """psql/pg_dump uchun muhit: PGPASSWORD (.env URL yoki PGPASSWORD env)."""
    env = os.environ.copy()
    pwd = (os.environ.get("PGPASSWORD") or str(cfg.get("password") or "")).strip()
    if pwd:
        env["PGPASSWORD"] = pwd
    return env


def format_pg_auth_help(cfg: Mapping[str, str | int]) -> str:
    user = cfg.get("user", "postgres")
    host = cfg.get("host", "127.0.0.1")
    port = cfg.get("port", 5432)
    return (
        f"PostgreSQL parol noto'g'ri yoki foydalanuvchi '{user}' mavjud emas.\n\n"
        f"Tekshiring:\n"
        f"  1. Serverdagi `.env` → DATABASE_URL paroli to'g'rimi?\n"
        f"  2. Ulanish: psql -h {host} -p {port} -U {user} -d postgres\n"
        f"  3. Parolni yangilash (postgres superuser):\n"
        f"     sudo -u postgres psql -c \"ALTER USER {user} WITH PASSWORD 'YANGI_PAROL';\"\n"
        f"  4. `.env` dagi parolni shu parolga moslashtiring va qayta: python tikla.py --yes ..."
    )
