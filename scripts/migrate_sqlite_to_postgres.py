#!/usr/bin/env python3
"""Migrate Assignment Notifier data from SQLite to PostgreSQL."""

from __future__ import annotations

import argparse
import os
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence
from urllib.parse import urlparse

import psycopg2
from psycopg2.extras import execute_values


TABLES = ("users", "user_events", "system_settings")


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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


def chunked(items: Sequence[sqlite3.Row], size: int) -> Iterable[Sequence[sqlite3.Row]]:
    for idx in range(0, len(items), size):
        yield items[idx : idx + size]


def ensure_queue_defaults(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE users
            SET poll_lock_until = NULL,
                poll_fail_count = COALESCE(poll_fail_count, 0),
                last_poll_error = NULL
            """
        )
    conn.commit()


def spread_next_poll_at(conn, poll_interval_seconds: int, jitter_seconds: int) -> None:
    now = utc_now_naive()
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE active = TRUE ORDER BY id")
        user_ids = [row[0] for row in cur.fetchall()]

        updates = []
        for uid in user_ids:
            jitter = random.randint(-jitter_seconds, jitter_seconds)
            next_poll = now + timedelta(seconds=max(60, poll_interval_seconds + jitter))
            updates.append((next_poll, uid))

        execute_values(
            cur,
            """
            UPDATE users AS u
            SET next_poll_at = v.next_poll_at
            FROM (VALUES %s) AS v(next_poll_at, id)
            WHERE u.id = v.id
            """,
            updates,
            template="(%s, %s)",
        )
    conn.commit()


def migrate_users(sql_rows: Sequence[sqlite3.Row], conn, batch_size: int) -> None:
    sql = """
        INSERT INTO users (
            id, chat_id, student_id, display_name, password_blob, session_cookie_blob,
            created_at, last_checked_at, active, is_banned, next_poll_at, poll_lock_until,
            poll_fail_count, last_poll_error
        ) VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            chat_id = EXCLUDED.chat_id,
            student_id = EXCLUDED.student_id,
            display_name = EXCLUDED.display_name,
            password_blob = EXCLUDED.password_blob,
            session_cookie_blob = EXCLUDED.session_cookie_blob,
            created_at = EXCLUDED.created_at,
            last_checked_at = EXCLUDED.last_checked_at,
            active = EXCLUDED.active,
            is_banned = EXCLUDED.is_banned,
            next_poll_at = EXCLUDED.next_poll_at,
            poll_lock_until = EXCLUDED.poll_lock_until,
            poll_fail_count = EXCLUDED.poll_fail_count,
            last_poll_error = EXCLUDED.last_poll_error
    """
    with conn.cursor() as cur:
        for rows in chunked(sql_rows, batch_size):
            payload = [
                (
                    r["id"],
                    r["chat_id"],
                    r["student_id"],
                    r["display_name"],
                    bytes(r["password_blob"]) if r["password_blob"] is not None else None,
                    bytes(r["session_cookie_blob"]) if r["session_cookie_blob"] is not None else None,
                    r["created_at"],
                    r["last_checked_at"],
                    bool(r["active"]),
                    bool(r["is_banned"]),
                    r["next_poll_at"],
                    r["poll_lock_until"],
                    int(r["poll_fail_count"] or 0),
                    r["last_poll_error"],
                )
                for r in rows
            ]
            execute_values(cur, sql, payload)
    conn.commit()


def migrate_user_events(sql_rows: Sequence[sqlite3.Row], conn, batch_size: int) -> None:
    sql = """
        INSERT INTO user_events (
            id, user_id, event_id, title, subject, due_at, link, first_seen_at, last_notified_at,
            reminder_3d_sent_at, reminder_2d_sent_at, reminder_1d_sent_at
        ) VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            user_id = EXCLUDED.user_id,
            event_id = EXCLUDED.event_id,
            title = EXCLUDED.title,
            subject = EXCLUDED.subject,
            due_at = EXCLUDED.due_at,
            link = EXCLUDED.link,
            first_seen_at = EXCLUDED.first_seen_at,
            last_notified_at = EXCLUDED.last_notified_at,
            reminder_3d_sent_at = EXCLUDED.reminder_3d_sent_at,
            reminder_2d_sent_at = EXCLUDED.reminder_2d_sent_at,
            reminder_1d_sent_at = EXCLUDED.reminder_1d_sent_at
    """
    with conn.cursor() as cur:
        for rows in chunked(sql_rows, batch_size):
            payload = [
                (
                    r["id"],
                    r["user_id"],
                    r["event_id"],
                    r["title"],
                    r["subject"],
                    r["due_at"],
                    r["link"],
                    r["first_seen_at"],
                    r["last_notified_at"],
                    r["reminder_3d_sent_at"],
                    r["reminder_2d_sent_at"],
                    r["reminder_1d_sent_at"],
                )
                for r in rows
            ]
            execute_values(cur, sql, payload)
    conn.commit()


def migrate_system_settings(sql_rows: Sequence[sqlite3.Row], conn) -> None:
    sql = """
        INSERT INTO system_settings (id, is_maintenance, broadcast_count)
        VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            is_maintenance = EXCLUDED.is_maintenance,
            broadcast_count = EXCLUDED.broadcast_count
    """
    with conn.cursor() as cur:
        payload = [
            (
                r["id"],
                bool(r["is_maintenance"]),
                int(r["broadcast_count"] or 0),
            )
            for r in sql_rows
        ]
        if payload:
            execute_values(cur, sql, payload)
    conn.commit()


def fetch_sqlite_rows(sqlite_path: str, table: str) -> Sequence[sqlite3.Row]:
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
    finally:
        conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate SQLite DB to PostgreSQL")
    parser.add_argument("--sqlite-path", default=os.getenv("DB_PATH", "data/lms_notifier.db"))
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--batch-size", type=int, default=int(os.getenv("MIGRATION_BATCH_SIZE", "500")))
    parser.add_argument("--poll-interval-seconds", type=int, default=int(os.getenv("POLL_INTERVAL_SECONDS", "3600")))
    parser.add_argument("--poll-jitter-seconds", type=int, default=int(os.getenv("POLL_JITTER_SECONDS", "600")))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dsn = postgres_dsn_from_url(args.database_url)
    if not os.path.exists(args.sqlite_path):
        raise RuntimeError(f"SQLite DB not found: {args.sqlite_path}")

    print(f"Reading SQLite: {args.sqlite_path}")
    users = fetch_sqlite_rows(args.sqlite_path, "users")
    events = fetch_sqlite_rows(args.sqlite_path, "user_events")
    settings = fetch_sqlite_rows(args.sqlite_path, "system_settings")
    print(f"SQLite rows -> users={len(users)} user_events={len(events)} system_settings={len(settings)}")

    pg_conn = psycopg2.connect(dsn)
    try:
        migrate_users(users, pg_conn, max(1, args.batch_size))
        print("Migrated users.")
        migrate_user_events(events, pg_conn, max(1, args.batch_size))
        print("Migrated user_events.")
        migrate_system_settings(settings, pg_conn)
        print("Migrated system_settings.")
        ensure_queue_defaults(pg_conn)
        spread_next_poll_at(
            pg_conn,
            poll_interval_seconds=max(60, args.poll_interval_seconds),
            jitter_seconds=max(0, args.poll_jitter_seconds),
        )
        print("Queue bootstrap completed.")
    finally:
        pg_conn.close()

    print("Migration complete.")


if __name__ == "__main__":
    main()
