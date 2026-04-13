from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from typing import AsyncGenerator

from app.config import settings


class Base(DeclarativeBase):
    """Base class for all database models"""
    pass


# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # Set to True for SQL debugging
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600
)

# Create async session factory
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session"""
    async with async_session() as session:
        yield session


async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Alembic yo'q: mavjud bazalarga invite_link ustuni
    dialect = engine.dialect.name
    try:
        async with engine.begin() as conn:
            if dialect == "sqlite":
                r = await conn.execute(text("PRAGMA table_info(required_channels)"))
                cols = [row[1] for row in r.fetchall()]
                if cols and "invite_link" not in cols:
                    await conn.execute(
                        text(
                            "ALTER TABLE required_channels ADD COLUMN invite_link VARCHAR(500)"
                        )
                    )
            elif dialect == "postgresql":
                await conn.execute(
                    text(
                        "ALTER TABLE required_channels ADD COLUMN IF NOT EXISTS invite_link VARCHAR(500)"
                    )
                )
    except Exception:
        pass


async def close_db():
    """Close database connections"""
    await engine.dispose()
