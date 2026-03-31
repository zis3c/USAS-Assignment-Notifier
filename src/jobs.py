"""Background job functions : periodic LMS polling."""
import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from typing import Optional

from cryptography.fernet import InvalidToken
from sqlalchemy import select

from src import config, strings
from src.crypto import decrypt_text, encrypt_text
from src.database import AsyncSessionLocal, get_utc_now
from src.lms_client import LMSAuthenticationError, LMSClient, extract_user_name
from src.models import User, UserEvent

logger = logging.getLogger(__name__)


@dataclass
class PollResult:
    new_count: int = 0
    reminder_count: int = 0
    pending_count: int = 0
    error: Optional[str] = None


def _to_utc_naive(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _to_local_display(value: datetime) -> str:
    utc_aware = value.replace(tzinfo=timezone.utc)
    local_dt = utc_aware.astimezone(config.LOCAL_TZ)
    return local_dt.strftime(f"%d {local_dt.strftime('%b').capitalize()} %y, %I:%M %p").replace("AM", "am").replace("PM", "pm")


def _is_pending(due_at: Optional[datetime], now_utc: datetime) -> bool:
    if due_at is None:
        return False
    return due_at >= now_utc


def _should_send_reminder(last_notified_at: Optional[datetime], now_utc: datetime) -> bool:
    if last_notified_at is None:
        return True
    seconds_since_last = (now_utc - last_notified_at).total_seconds()
    return seconds_since_last >= config.REMINDER_INTERVAL_SECONDS


def _format_subject(subject: str) -> str:
    clean = " ".join((subject or "").split()).strip()
    if not clean:
        return clean

    match = re.match(
        r"^([A-Z]{2,4}\d{3,4})(?:\s*[-:|]\s*|\s+)(.+)$",
        clean,
        flags=re.IGNORECASE,
    )
    code = ""
    name = clean
    if match:
        code = match.group(1).upper()
        name = match.group(2).strip()
    elif re.fullmatch(r"[A-Z]{2,4}\d{3,4}", clean, flags=re.IGNORECASE):
        return clean.upper()

    tokens = name.split()
    if all(token.isupper() for token in tokens):
        formatted_tokens = []
        for token in tokens:
            # Keep short acronyms as uppercase (e.g., IT, AI).
            if len(token) <= 3:
                formatted_tokens.append(token)
            else:
                formatted_tokens.append(token.capitalize())
        formatted_name = " ".join(formatted_tokens)
    else:
        formatted_name = name.title() if code else name

    return f"{code} {formatted_name}".strip()


def _format_title(title: str) -> str:
    clean = " ".join((title or "").split()).strip()
    return re.sub(r"\s+is\s+due$", "", clean, flags=re.IGNORECASE).strip()


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


def _build_assignment_item(event: dict) -> str:
    due_at = _to_utc_naive(event.get("due_at"))
    due_line = ""
    if isinstance(due_at, datetime):
        due_line = strings.ASSIGNMENT_DUE_LINE.format(due=escape(_to_local_display(due_at)))

    link = event.get("link") or ""
    link_line = strings.ASSIGNMENT_LINK_LINE.format(link=escape(link, quote=True)) if link else ""

    subject = _format_subject((event.get("subject") or "").strip())
    subject_line = strings.ASSIGNMENT_SUBJECT_LINE.format(subject=escape(subject)) if subject else ""
    title = escape(_format_title(str(event.get("title") or "Assignment")))

    return strings.ASSIGNMENT_ITEM.format(
        subject_line=subject_line,
        title=title,
        due_line=due_line,
        link_line=link_line,
    )


def _build_assignment_batches(events: list[dict], is_reminder: bool) -> list[str]:
    if not events:
        return []

    header = strings.PENDING_ASSIGNMENT_HEADER if is_reminder else strings.NEW_ASSIGNMENT_HEADER
    max_len = 3900
    batches: list[str] = []
    current = f"{header}\n\n"
    continuation_header = f"{header} (cont.)\n\n"

    for event in events:
        item = _build_assignment_item(event)
        prefix = "" if current.endswith("\n\n") else "\n\n"
        candidate = f"{current}{prefix}{item}"
        if len(candidate) <= max_len:
            current = candidate
        else:
            batches.append(current.rstrip())
            current = f"{continuation_header}{item}"

    if current.strip():
        batches.append(current.rstrip())
    return batches


async def poll_user_id(user_id: int, bot, force_pending_reminders: bool = False) -> PollResult:
    """Poll a single user and send notifications for new and pending assignments."""
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if not user or not user.active:
            return PollResult()

        try:
            password = decrypt_text(user.password_blob)
        except InvalidToken:
            logger.warning("Failed to decrypt password for user %s", user_id)
            return PollResult()

        session_cookie: Optional[str] = None
        if user.session_cookie_blob:
            try:
                session_cookie = decrypt_text(user.session_cookie_blob)
            except InvalidToken:
                session_cookie = None

        client = LMSClient(user.student_id, password, session_cookie)
        try:
            fetch_result = await client.fetch_events()
        except LMSAuthenticationError:
            logger.warning("LMS authentication failed for user %s", user_id)
            return PollResult(error="auth_failed")
        except Exception as exc:
            logger.exception("LMS fetch failed for user %s: %s", user_id, exc)
            return PollResult(error="fetch_failed")

        events = fetch_result.events
        now_utc = get_utc_now()
        chat_id = user.chat_id

        if fetch_result.session_cookie:
            user.session_cookie_blob = encrypt_text(fetch_result.session_cookie)

        # Update display name if freshly parsed
        if fetch_result.dashboard_html:
            parsed_name = extract_user_name(fetch_result.dashboard_html)
            if parsed_name:
                user.display_name = parsed_name

        existing_result = await session.execute(
            select(UserEvent).where(UserEvent.user_id == user.id)
        )
        existing_rows = existing_result.scalars().all()
        existing_by_id = {row.event_id: row for row in existing_rows}

        new_events = []
        reminder_events = []
        pending_count = 0
        seen_event_ids = set()

        for event in events:
            event_id = event["id"]
            if event_id in seen_event_ids:
                continue
            seen_event_ids.add(event_id)
            due_at = _to_utc_naive(event.get("due_at"))
            subject = (event.get("subject") or "").strip() or None
            current = existing_by_id.get(event_id)
            is_new = current is None

            if is_new:
                current = UserEvent(
                    user_id=user.id,
                    event_id=event_id,
                    title=event["title"],
                    subject=subject,
                    due_at=due_at,
                    link=event.get("link"),
                )
                session.add(current)
                existing_by_id[event_id] = current
                new_events.append(event)
            else:
                current.title = event["title"]
                current.subject = subject or current.subject
                current.due_at = due_at
                current.link = event.get("link")

            if _is_pending(due_at, now_utc):
                pending_count += 1
                should_send = force_pending_reminders or _should_send_reminder(
                    current.last_notified_at, now_utc
                )
                if not is_new and should_send:
                    reminder_events.append(event)

        for event in [*new_events, *reminder_events]:
            row = existing_by_id.get(event["id"])
            if row:
                row.last_notified_at = now_utc

        user.last_checked_at = get_utc_now()
        await session.commit()

    # Send notifications outside the DB session
    for batch in _build_assignment_batches(new_events, is_reminder=False):
        await bot.send_message(
            chat_id=chat_id,
            text=batch,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

    for batch in _build_assignment_batches(reminder_events, is_reminder=True):
        await bot.send_message(
            chat_id=chat_id,
            text=batch,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

    return PollResult(
        new_count=len(new_events),
        reminder_count=len(reminder_events),
        pending_count=pending_count,
    )


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
