import os
import sqlite3
import logging
from datetime import datetime, timezone
from typing import Sequence

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
    # Hosted DATABASE_URL values usually start with postgres:// or postgresql://
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
            await _assert_postgres_required_columns(conn)
    
    if is_sqlite:
        _migrate_db_sqlite()


async def _migrate_db_postgres(conn) -> None:
    """Apply additive schema migrations for PostgreSQL."""
    migrations = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS next_poll_at TIMESTAMP",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS poll_lock_until TIMESTAMP",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS poll_fail_count INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_poll_error TEXT",
        "ALTER TABLE user_events ADD COLUMN IF NOT EXISTS subject TEXT",
        "ALTER TABLE user_events ADD COLUMN IF NOT EXISTS last_notified_at TIMESTAMP",
        "ALTER TABLE user_events ADD COLUMN IF NOT EXISTS reminder_3d_sent_at TIMESTAMP",
        "ALTER TABLE user_events ADD COLUMN IF NOT EXISTS reminder_2d_sent_at TIMESTAMP",
        "ALTER TABLE user_events ADD COLUMN IF NOT EXISTS reminder_1d_sent_at TIMESTAMP",
        "CREATE INDEX IF NOT EXISTS ix_users_active_next_poll_at ON users (active, next_poll_at)",
        "CREATE INDEX IF NOT EXISTS ix_users_poll_lock_until ON users (poll_lock_until)",
    ]
    for sql in migrations:
        try:
            await conn.execute(text(sql))
        except Exception as e:
            # Keep startup resilient even if a migration statement is unsupported
            # or already applied with a slightly different type.
            logger.warning("PostgreSQL migration skipped for '%s': %s", sql, e)

    # Keep SERIAL sequences aligned after imports that preserve explicit IDs.
    await _sync_postgres_sequences(conn)


async def _assert_postgres_required_columns(conn) -> None:
    """Fail fast in PostgreSQL mode if queue columns are missing."""
    required_columns: Sequence[str] = (
        "next_poll_at",
        "poll_lock_until",
        "poll_fail_count",
        "last_poll_error",
    )
    result = await conn.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'users'
            """
        )
    )
    existing = {row[0] for row in result.fetchall()}
    missing = [col for col in required_columns if col not in existing]
    if missing:
        raise RuntimeError(
            "PostgreSQL schema missing required users columns: "
            + ", ".join(missing)
            + ". Run DB migration before starting bot."
        )


async def _sync_postgres_sequences(conn) -> None:
    """Align PostgreSQL SERIAL sequences with current max primary keys."""
    statements = [
        """
        SELECT setval(
            pg_get_serial_sequence('users', 'id'),
            COALESCE((SELECT MAX(id) FROM users), 1),
            true
        )
        """,
        """
        SELECT setval(
            pg_get_serial_sequence('user_events', 'id'),
            COALESCE((SELECT MAX(id) FROM user_events), 1),
            true
        )
        """,
        """
        SELECT setval(
            pg_get_serial_sequence('system_settings', 'id'),
            COALESCE((SELECT MAX(id) FROM system_settings), 1),
            true
        )
        """,
    ]
    for sql in statements:
        try:
            await conn.execute(text(sql))
        except Exception as e:
            logger.warning("PostgreSQL sequence sync skipped for '%s': %s", sql.splitlines()[1].strip(), e)


def _migrate_db_sqlite() -> None:
    """Apply missing columns for SQLite manually (SQLite doesn't support IF NOT EXISTS in ALTER)."""
    migrations = [
        "ALTER TABLE users ADD COLUMN display_name TEXT",
        "ALTER TABLE users ADD COLUMN is_banned BOOLEAN DEFAULT 0",
        "ALTER TABLE users ADD COLUMN next_poll_at DATETIME",
        "ALTER TABLE users ADD COLUMN poll_lock_until DATETIME",
        "ALTER TABLE users ADD COLUMN poll_fail_count INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN last_poll_error TEXT",
        "ALTER TABLE user_events ADD COLUMN subject TEXT",
        "ALTER TABLE user_events ADD COLUMN last_notified_at DATETIME",
        "ALTER TABLE user_events ADD COLUMN reminder_3d_sent_at DATETIME",
        "ALTER TABLE user_events ADD COLUMN reminder_2d_sent_at DATETIME",
        "ALTER TABLE user_events ADD COLUMN reminder_1d_sent_at DATETIME",
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
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_users_active_next_poll_at ON users (active, next_poll_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_users_poll_lock_until ON users (poll_lock_until)"
        )
        conn.commit()
    finally:
        conn.close()
