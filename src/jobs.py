"""Background job functions : periodic LMS polling."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from cryptography.fernet import InvalidToken
from sqlalchemy import select

from src import config, strings
from src.crypto import decrypt_text, encrypt_text
from src.database import AsyncSessionLocal, get_utc_now
from src.lms_client import LMSClient, extract_user_name
from src.models import User, UserEvent

logger = logging.getLogger(__name__)


async def poll_all_users(context) -> None:
    """Job: poll every active user for new assignments."""
    start_time = datetime.now()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User.id).where(User.active.is_(True)))
        user_ids = result.scalars().all()

    if not user_ids:
        return

    sem = asyncio.Semaphore(config.MAX_CONCURRENCY)
    bot = context.application.bot

    async def run_one(uid: int) -> None:
        async with sem:
            try:
                await poll_user_id(uid, bot)
            except Exception as exc:
                logger.exception("Polling failed for user %s: %s", uid, exc)

    await asyncio.gather(*(run_one(uid) for uid in user_ids))
    
    duration = (datetime.now() - start_time).total_seconds()
    logger.info("📊  Poll cycle completed in %.2fs for %d users.", duration, len(user_ids))


async def poll_user_id(user_id: int, bot) -> int:
    """Poll a single user and send notifications for new assignments.

    Returns the count of new assignments sent.
    """
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if not user or not user.active:
            return 0

        try:
            password = decrypt_text(user.password_blob)
        except InvalidToken:
            logger.warning("Failed to decrypt password for user %s", user_id)
            return 0

        session_cookie: Optional[str] = None
        if user.session_cookie_blob:
            try:
                session_cookie = decrypt_text(user.session_cookie_blob)
            except InvalidToken:
                session_cookie = None

        client = LMSClient(user.student_id, password, session_cookie)
        fetch_result = await client.fetch_events()
        events = fetch_result.events

        if fetch_result.session_cookie:
            user.session_cookie_blob = encrypt_text(fetch_result.session_cookie)

        # Update display name if freshly parsed
        if fetch_result.dashboard_html:
            parsed_name = extract_user_name(fetch_result.dashboard_html)
            if parsed_name:
                user.display_name = parsed_name

        existing = await session.execute(
            select(UserEvent.event_id).where(UserEvent.user_id == user.id)
        )
        existing_ids = set(existing.scalars().all())

        new_events = [e for e in events if e["id"] not in existing_ids]
        for e in new_events:
            session.add(
                UserEvent(
                    user_id=user.id,
                    event_id=e["id"],
                    title=e["title"],
                    due_at=e.get("due_at"),
                    link=e.get("link"),
                )
            )

        user.last_checked_at = get_utc_now()
        await session.commit()

    # Send notifications outside the DB session
    for e in new_events:
        due_at = e.get("due_at")
        due_line = ""
        if isinstance(due_at, datetime):
            t = due_at.astimezone(config.LOCAL_TZ)
            local_time = t.strftime(f"%d {t.strftime('%b').capitalize()} %y, %I:%M %p").replace("AM", "am").replace("PM", "pm")
            due_line = strings.ASSIGNMENT_DUE_LINE.format(due=local_time)

        link = e.get("link") or ""
        link_line = strings.ASSIGNMENT_LINK_LINE.format(link=link) if link else ""

        card = strings.ASSIGNMENT_CARD.format(
            title=e["title"],
            due_line=due_line,
            link_line=link_line,
        )
        await bot.send_message(
            chat_id=user.chat_id,
            text=card,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )

    return len(new_events)


async def send_daily_logs(context) -> None:
    """Job: send the daily activity log file to the admin and clear it."""
    import os
    from datetime import timedelta

    if not config.ADMIN_ID:
        logger.warning("Daily log job skipped: ADMIN_ID is not configured.")
        return

    if not os.path.exists(config.ACTIVITY_LOG_PATH):
        logger.info("Daily log job skipped: %s does not exist.", config.ACTIVITY_LOG_PATH)
        return

    # Yesterday's date for the report filename
    now_local = datetime.now(config.LOCAL_TZ)
    yesterday = now_local - timedelta(days=1)
    date_str = yesterday.strftime('%Y-%m-%d')

    try:
        # Check if file has content
        if os.path.getsize(config.ACTIVITY_LOG_PATH) == 0:
            logger.info("Daily log job skipped: %s is empty.", config.ACTIVITY_LOG_PATH)
            return

        # Send the file
        with open(config.ACTIVITY_LOG_PATH, "rb") as f:
            await context.bot.send_document(
                chat_id=config.ADMIN_ID,
                document=f,
                filename=f"activity_report_{date_str}.txt",
                caption=f"📄 *Daily Activity Report*\nDate: `{date_str}`",
                parse_mode="Markdown"
            )
        
        # Clear the file after sending for the new day
        with open(config.ACTIVITY_LOG_PATH, "w", encoding="utf-8") as f:
            f.truncate(0)

        logger.info("✅ Daily activity logs sent to admin and file reset.")
    except Exception as e:
        logger.error("Failed to send daily logs: %s", e)
