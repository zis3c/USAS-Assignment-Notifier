#!/usr/bin/env python3
"""Verify SQLite -> PostgreSQL migration integrity."""

from __future__ import annotations

import argparse
import hashlib
import os
import random
import sqlite3
from urllib.parse import urlparse

import psycopg2


TABLES = ("users", "user_events", "system_settings")


def postgres_dsn_from_url(database_url: str) -> str:
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    parsed = urlparse(database_url)
    if parsed.scheme != "postgresql":
        raise RuntimeError("DATABASE_URL must be postgres/postgresql/postgresql+asyncpg")
    return database_url


COUNT_SQL = {
    "users": "SELECT COUNT(*) FROM users",
    "courses": "SELECT COUNT(*) FROM courses",
    "assignments": "SELECT COUNT(*) FROM assignments",
    "notifications_sent": "SELECT COUNT(*) FROM notifications_sent",
}

SELECT_ID_SQL = {
    "users": "SELECT id FROM users ORDER BY id",
    "courses": "SELECT id FROM courses ORDER BY id",
    "assignments": "SELECT id FROM assignments ORDER BY id",
    "notifications_sent": "SELECT id FROM notifications_sent ORDER BY id",
}


def sqlite_count(conn: sqlite3.Connection, table: str) -> int:
    if table not in COUNT_SQL:
        raise ValueError(f"Unsupported table: {table}")
    return int(conn.execute(COUNT_SQL[table]).fetchone()[0])


def postgres_count(conn, table: str) -> int:
    if table not in COUNT_SQL:
        raise ValueError(f"Unsupported table: {table}")
    with conn.cursor() as cur:
        cur.execute(COUNT_SQL[table])
        return int(cur.fetchone()[0])


def hash_bytes(value: bytes | None) -> str:
    if value is None:
        return "NULL"
    return hashlib.sha256(value).hexdigest()


def sample_ids(sqlite_conn: sqlite3.Connection, table: str, sample_size: int) -> list[int]:
    if table not in SELECT_ID_SQL:
        raise ValueError(f"Unsupported table: {table}")
    rows = sqlite_conn.execute(SELECT_ID_SQL[table]).fetchall()
    ids = [int(row[0]) for row in rows]
    if len(ids) <= sample_size:
        return ids
    return sorted(random.sample(ids, sample_size))


def verify_user_blob_samples(sqlite_conn: sqlite3.Connection, pg_conn, sample_size: int) -> None:
    ids = sample_ids(sqlite_conn, "users", sample_size)
    for uid in ids:
        sqlite_row = sqlite_conn.execute(
            "SELECT password_blob, session_cookie_blob FROM users WHERE id = ?",
            (uid,),
        ).fetchone()
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT password_blob, session_cookie_blob FROM users WHERE id = %s",
                (uid,),
            )
            pg_row = cur.fetchone()
        if pg_row is None:
            raise RuntimeError(f"Missing users.id={uid} in PostgreSQL")
        sqlite_pwd = bytes(sqlite_row[0]) if sqlite_row[0] is not None else None
        sqlite_cookie = bytes(sqlite_row[1]) if sqlite_row[1] is not None else None
        pg_pwd = bytes(pg_row[0]) if pg_row[0] is not None else None
        pg_cookie = bytes(pg_row[1]) if pg_row[1] is not None else None
        if hash_bytes(sqlite_pwd) != hash_bytes(pg_pwd):
            raise RuntimeError(f"password_blob mismatch for users.id={uid}")
        if hash_bytes(sqlite_cookie) != hash_bytes(pg_cookie):
            raise RuntimeError(f"session_cookie_blob mismatch for users.id={uid}")


def verify_required_user_columns(pg_conn) -> None:
    required = {"next_poll_at", "poll_lock_until", "poll_fail_count", "last_poll_error"}
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'users'
            """
        )
        existing = {row[0] for row in cur.fetchall()}
    missing = required - existing
    if missing:
        raise RuntimeError(f"Missing required users columns in PostgreSQL: {', '.join(sorted(missing))}")


def verify_null_constraints(pg_conn) -> None:
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM users
            WHERE chat_id IS NULL OR student_id IS NULL OR password_blob IS NULL
            """
        )
        bad_users = int(cur.fetchone()[0])
        cur.execute(
            """
            SELECT COUNT(*) FROM user_events
            WHERE user_id IS NULL OR event_id IS NULL OR title IS NULL
            """
        )
        bad_events = int(cur.fetchone()[0])
    if bad_users > 0:
        raise RuntimeError(f"users table has {bad_users} null-constraint violations")
    if bad_events > 0:
        raise RuntimeError(f"user_events table has {bad_events} null-constraint violations")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify SQLite->PostgreSQL migration")
    parser.add_argument("--sqlite-path", default=os.getenv("DB_PATH", "data/lms_notifier.db"))
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--sample-size", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dsn = postgres_dsn_from_url(args.database_url)
    if not os.path.exists(args.sqlite_path):
        raise RuntimeError(f"SQLite DB not found: {args.sqlite_path}")

    sqlite_conn = sqlite3.connect(args.sqlite_path)
    pg_conn = psycopg2.connect(dsn)
    try:
        for table in TABLES:
            s_count = sqlite_count(sqlite_conn, table)
            p_count = postgres_count(pg_conn, table)
            print(f"{table}: sqlite={s_count} postgres={p_count}")
            if s_count != p_count:
                raise RuntimeError(f"Count mismatch for table {table}")

        verify_user_blob_samples(sqlite_conn, pg_conn, max(1, args.sample_size))
        verify_required_user_columns(pg_conn)
        verify_null_constraints(pg_conn)
    finally:
        sqlite_conn.close()
        pg_conn.close()

    print("Verification PASSED.")


if __name__ == "__main__":
    main()
