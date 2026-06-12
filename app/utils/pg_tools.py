"""PostgreSQL backup/restore uchun pg_dump/psql parametrlari."""

from __future__ import annotations

from sqlalchemy.engine import make_url


def db_params(database_url: str) -> dict[str, str | int]:
    """SQLAlchemy URL → pg_dump/psql ulanish parametrlari."""
    u = make_url(database_url.strip().strip('"').strip("'"))
    return {
        "host": u.host or "localhost",
        "port": int(u.port or 5432),
        "user": u.username or "postgres",
        "password": u.password or "",
        "database": u.database or "postgres",
    }
