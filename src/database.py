"""Database engine, session factory, and schema initialisation."""
import os
import sqlite3

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src import config
from src.models import Base

# Ensure data directory and SQLite path handling
is_sqlite = not config.DATABASE_URL
if is_sqlite:
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    db_url = f"sqlite+aiosqlite:///{config.DB_PATH}"
else:
    # Render's DATABASE_URL usually starts with postgres://, SQLAlchemy needs postgresql+asyncpg://
    db_url = config.DATABASE_URL.replace("postgres://", "postgresql+asyncpg://")

engine = create_async_engine(db_url)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    if is_sqlite:
        _migrate_db_sqlite()


def _migrate_db_sqlite() -> None:
    """Apply missing columns for SQLite manually (SQLite doesn't support IF NOT EXISTS in ALTER)."""
    migrations = [
        "ALTER TABLE users ADD COLUMN display_name TEXT",
        "ALTER TABLE users ADD COLUMN is_banned BOOLEAN DEFAULT 0",
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
