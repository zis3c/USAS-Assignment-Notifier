import os
import sqlite3
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

def get_utc_now() -> datetime:
    """Return a naive UTC datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

from src import config
from src.models import Base

logger = logging.getLogger(__name__)

# Ensure data directory and SQLite path handling
is_sqlite = not config.DATABASE_URL
if is_sqlite:
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    db_url = f"sqlite+aiosqlite:///{config.DB_PATH}"
else:
    # Render's DATABASE_URL usually starts with postgres:// or postgresql://
    # SQLAlchemy 2.0+ with create_async_engine MUST use postgresql+asyncpg://
    db_url = config.DATABASE_URL
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgresql://") and "+asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(db_url)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if is_sqlite:
            # SQLite migration is run sync via sqlite3 helper below.
            pass
        else:
            await _migrate_db_postgres(conn)
    
    if is_sqlite:
        _migrate_db_sqlite()


async def _migrate_db_postgres(conn) -> None:
    """Apply additive schema migrations for PostgreSQL."""
    migrations = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN DEFAULT FALSE",
        "ALTER TABLE user_events ADD COLUMN IF NOT EXISTS subject TEXT",
        "ALTER TABLE user_events ADD COLUMN IF NOT EXISTS last_notified_at TIMESTAMP",
    ]
    for sql in migrations:
        try:
            await conn.execute(text(sql))
        except Exception as e:
            # Keep startup resilient even if a migration statement is unsupported
            # or already applied with a slightly different type.
            logger.warning("PostgreSQL migration skipped for '%s': %s", sql, e)


def _migrate_db_sqlite() -> None:
    """Apply missing columns for SQLite manually (SQLite doesn't support IF NOT EXISTS in ALTER)."""
    migrations = [
        "ALTER TABLE users ADD COLUMN display_name TEXT",
        "ALTER TABLE users ADD COLUMN is_banned BOOLEAN DEFAULT 0",
        "ALTER TABLE user_events ADD COLUMN subject TEXT",
        "ALTER TABLE user_events ADD COLUMN last_notified_at DATETIME",
    ]
    import sqlite3
    conn = sqlite3.connect(config.DB_PATH)
    try:
        for sql in migrations:
            try:
                conn.execute(sql)
                conn.commit()
            except sqlite3.OperationalError:
                pass
    finally:
        conn.close()
