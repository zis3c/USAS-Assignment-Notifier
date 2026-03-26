"""Telegram command handlers and ConversationHandler flows."""
import asyncio
import logging
import os
import shutil
import time
from datetime import datetime, timezone
import psutil

from cryptography.fernet import InvalidToken
from sqlalchemy import select
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src import config, keyboards, strings
from src.crypto import decrypt_text, encrypt_text
from src.database import AsyncSessionLocal
from src.jobs import poll_user_id
from src.lms_client import LMSClient, extract_user_name, extract_sesskey
from src.models import User, SystemSettings
from src.sheets_client import sheets_client
from src.logging_utils import log_activity

logger = logging.getLogger(__name__)

# ── Conversation states ───────────────────────────────────────────────────────
ASK_MEMBERSHIP_ID, ASK_STUDENT_ID, ASK_PASSWORD = range(3)
CONFIRM_UNREGISTER = 10

# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_cancel(text: str) -> bool:
    return text.strip() in ("Cancel", "/cancel", "cancel")

async def check_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Checks if the bot is in maintenance mode and sends a message if it is."""
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(SystemSettings).limit(1))
        settings = res.scalar_one_or_none()
        if settings and settings.is_maintenance:
            await update.message.reply_text(strings.ADMIN_MAINTENANCE_ACTIVE_MSG, parse_mode="Markdown")
            return True
    return False

async def check_banned(user_id: int) -> bool:
    """Checks if a user is banned via their chat ID."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User.is_banned).where(User.chat_id == str(user_id)))
        is_banned = result.scalars().first()
        return is_banned if is_banned is not None else False


# ── /start ────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    # Global checks (anti-spam, maintenance, ban) are handled in bot.py

    await update.message.reply_text(
        strings.WELCOME,
        parse_mode="Markdown",
        reply_markup=keyboards.main_menu(),
    )


# ── /help  &  ❓ Help button ──────────────────────────────────────────────────

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        strings.HELP,
        parse_mode="Markdown",
        reply_markup=keyboards.help_inline_keyboard(),
    )


async def how_it_works_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Switch to 'How it works' view."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        text=strings.HELP_DETAIL,
        parse_mode="Markdown",
        reply_markup=keyboards.back_inline_keyboard()
    )


async def help_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return to main 'Help' view."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        text=strings.HELP,
        parse_mode="Markdown",
        reply_markup=keyboards.help_inline_keyboard()
    )


async def help_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        strings.HELP_DETAIL,
        parse_mode="MarkDown",
        reply_markup=keyboards.main_menu(),
    )


# ── /status  &  📊 Status button ─────────────────────────────────────────────

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the currently linked academic account."""
    # Global checks handled in bot.py

    chat_id = str(update.message.chat_id)
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.chat_id == chat_id))
        user = result.scalars().first()

    if not user or not user.active:
        await update.message.reply_text(
            strings.NOT_REGISTERED, parse_mode="Markdown", reply_markup=keyboards.main_menu()
        )
        return

    lms_name = user.display_name or "Not yet fetched"
    matric = user.student_id

    if user.last_checked_at:
        # last_checked_at is stored as UTC (naive in SQLite)
        utc_time = user.last_checked_at.replace(tzinfo=timezone.utc)
        t = utc_time.astimezone(config.LOCAL_TZ)
        local_time = t.strftime(f"%d {t.strftime('%b').capitalize()} %y, %I:%M %p").replace("AM", "am").replace("PM", "pm")
        await update.message.reply_text(
            strings.STATUS_OK.format(lms_name=lms_name, matric=matric, last_checked=local_time, tz=config.LOCAL_TZ.key),
            parse_mode="Markdown",
            reply_markup=keyboards.main_menu(),
        )
    else:
        await update.message.reply_text(
            strings.STATUS_NEVER_CHECKED.format(lms_name=lms_name, matric=matric),
            parse_mode="Markdown",
            reply_markup=keyboards.main_menu(),
        )


# ── /check  &  📋 Check Now button ───────────────────────────────────────────

async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually trigger an assignment check for the user."""
    # Anti-spam for Check Now (5 min) is still specific to this command
    now = datetime.now(timezone.utc).timestamp()
    last_check = context.user_data.get("last_check_time", 0)
    if now - last_check < config.USER_CHECK_INTERVAL:
        remaining_secs = int(config.USER_CHECK_INTERVAL - (now - last_check))
        minutes, seconds = divmod(remaining_secs, 60)
        time_limit_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
        await update.message.reply_text(
            strings.RATE_LIMIT_USER.format(remaining=time_limit_str),
            parse_mode="Markdown"
        )
        return

    context.user_data["last_check_time"] = now

    chat_id = str(update.message.chat_id)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User.id).where(User.chat_id == chat_id, User.active.is_(True))
        )
        user_id = result.scalars().first()

    if not user_id:
        await update.message.reply_text(
            strings.NOT_REGISTERED, parse_mode="Markdown", reply_markup=keyboards.main_menu()
        )
        return

    waiting = await update.message.reply_text(strings.CHECK_RUNNING, parse_mode="Markdown")
    count = await poll_user_id(user_id, context.application.bot)

    try:
        await waiting.delete()
    except TelegramError:
        pass

    msg = strings.CHECK_NEW.format(count=count) if count > 0 else strings.CHECK_NO_NEW
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboards.main_menu())
    
    # Log the result
    log_activity(
        update.effective_user.first_name or "Unknown",
        update.effective_user.id,
        "CHECK_MEMBERSHIP",
        f"Matric: {user_id} | Result: {'SUCCESS' if count >= 0 else 'FAILED'}"
    )


# ── /register  &  🔐 Register flow ───────────────────────────────────────────

async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the registration conversation."""
    if update.effective_user.id != config.ADMIN_ID:
        if await check_maintenance(update, context):
            return ConversationHandler.END
        if await check_banned(update.effective_user.id):
            return ConversationHandler.END

    await update.message.reply_text(
        strings.PROMPT_MEMBERSHIP_ID,
        parse_mode="Markdown",
        reply_markup=keyboards.cancel_menu(),
    )
    return ASK_MEMBERSHIP_ID


async def receive_membership_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if _is_cancel(text):
        return await _cancel_registration(update, context)

    # Verify ID in Sheets (Async)
    matric_expected, error = await sheets_client.lookup_membership(text)
    if error:
        await update.message.reply_text(f"⚠️ {error}", parse_mode="Markdown")
        return ASK_MEMBERSHIP_ID

    context.user_data["membership_id"] = text
    context.user_data["matric_expected"] = matric_expected

    await update.message.reply_text(
        strings.PROMPT_STUDENT_ID.format(membership_id=text),
        parse_mode="Markdown",
        reply_markup=keyboards.cancel_menu(),
    )
    return ASK_STUDENT_ID


async def receive_student_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip().upper()
    if _is_cancel(text):
        return await _cancel_registration(update, context)

    # Verification Match
    expected = context.user_data.get("matric_expected", "")
    if text != expected:
        await update.message.reply_text(
            strings.ERR_MEMBERSHIP_MATRIC_MISMATCH.format(entered=text),
            parse_mode="Markdown"
        )
        return ASK_STUDENT_ID

    context.user_data["student_id"] = text
    membership_id = context.user_data.get("membership_id", "Unknown")
    
    # Set flag to mask next message (password) in activity logs
    context.user_data["is_typing_password"] = True

    await update.message.reply_text(
        strings.PROMPT_PASSWORD.format(membership_id=membership_id, student_id=text),
        parse_mode="Markdown",
        reply_markup=keyboards.cancel_menu(),
    )
    return ASK_PASSWORD


async def receive_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    # Reset password masking flag
    context.user_data["is_typing_password"] = False

    if _is_cancel(text):
        return await _cancel_registration(update, context)

    student_id = context.user_data.get("student_id", "")
    chat_id = str(update.message.chat_id)
    enc_pwd = encrypt_text(text)

    # Delete the password message immediately for security
    try:
        await context.bot.delete_message(
            chat_id=update.message.chat_id,
            message_id=update.message.message_id,
        )
    except TelegramError:
        pass

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.chat_id == chat_id))
        user = result.scalars().first()
        is_update = user is not None

        # --- VALIDATION STEP ---
        # Before saving, try a real login to verify credentials
        waiting = await update.message.reply_text("⏳ *Verifying credentials...*", parse_mode="Markdown")
        client = LMSClient(student_id, text, None)  # Verifying with fresh login
        try:
            fetch_result = await client.fetch_events()
            # A successful login will contain a Moodle session key (sesskey)
            if not fetch_result.dashboard_html or not extract_sesskey(fetch_result.dashboard_html):
                 raise Exception("Login failed (no sesskey found)")
        except Exception as e:
            logger.warning("Validation failed for %s: %s", student_id, e)
            await waiting.delete()
            await update.message.reply_text(strings.LOGIN_FAILED, parse_mode="Markdown", reply_markup=keyboards.main_menu())
            return ConversationHandler.END

        await waiting.delete()
        parsed_name = extract_user_name(fetch_result.dashboard_html)

        if user:
            user.student_id = student_id
            user.password_blob = enc_pwd
            user.display_name = parsed_name
            user.active = True
            user.session_cookie_blob = encrypt_text(fetch_result.session_cookie) if fetch_result.session_cookie else None
        else:
            user = User(
                chat_id=chat_id,
                student_id=student_id,
                password_blob=enc_pwd,
                display_name=parsed_name,
                active=True,
                session_cookie_blob=encrypt_text(fetch_result.session_cookie) if fetch_result.session_cookie else None
            )
            session.add(user)
        
        await session.commit()

    reply_tmpl = strings.ALREADY_REGISTERED if is_update else strings.REGISTERED_OK
    reply = reply_tmpl.format(name=parsed_name or "Student")
    await update.message.reply_text(reply, parse_mode="Markdown", reply_markup=keyboards.main_menu())
    return ConversationHandler.END


async def _cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["is_typing_password"] = False
    await update.message.reply_text(
        strings.REGISTER_CANCELLED,
        parse_mode="Markdown",
        reply_markup=keyboards.main_menu(),
    )
    return ConversationHandler.END


# -- Logout flow ---------------------------------------------------------------

async def unregister_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = str(update.message.chat_id)
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.chat_id == chat_id))
        user = result.scalars().first()

    if not user or not user.active:
        await update.message.reply_text(
            strings.NOT_REGISTERED, parse_mode="Markdown", reply_markup=keyboards.main_menu()
        )
        return ConversationHandler.END

    display_name = user.display_name or "Student"

    await update.message.reply_text(
        strings.UNREGISTER_CONFIRM.format(name=display_name, matric=user.student_id),
        parse_mode="Markdown",
        reply_markup=keyboards.confirm_menu(),
    )
    return CONFIRM_UNREGISTER


async def unregister_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text == "Logout":
        chat_id = str(update.message.chat_id)
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.chat_id == chat_id))
            user = result.scalars().first()
            if user:
                user.active = False
                await session.commit()
        await update.message.reply_text(
            strings.UNREGISTERED_OK, parse_mode="Markdown", reply_markup=keyboards.main_menu()
        )
    else:
        await update.message.reply_text(
            strings.UNREGISTER_CANCELLED,
            parse_mode="Markdown",
            reply_markup=keyboards.main_menu()
        )

    return ConversationHandler.END


# ── Admin Commands ───────────────────────────────────────────────────────────

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry point for the admin dashboard."""
    if update.effective_user.id != config.ADMIN_ID:
        return

    await update.message.reply_text(
        strings.ADMIN_WELCOME,
        parse_mode="Markdown",
        reply_markup=keyboards.admin_menu(),
    )


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show quick registration stats."""
    if update.effective_user.id != config.ADMIN_ID:
        return

    async with AsyncSessionLocal() as session:
        registered = await session.execute(select(User))
        registered_users = registered.scalars().all()
        total_registered = len(registered_users)
        total_active = len([u for u in registered_users if u.active])

    await update.message.reply_text(
        strings.ADMIN_STATS.format(total=total_active, registered=total_registered),
        parse_mode="Markdown",
        reply_markup=keyboards.admin_menu(),
    )


async def admin_user_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all users with their Matric and Chat ID."""
    if update.effective_user.id != config.ADMIN_ID:
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).order_by(User.student_id.asc()))
        users = result.scalars().all()

    if not users:
        await update.message.reply_text("No users registered yet.")
        return

    # Group by student_id
    grouped = {}
    for u in users:
        if u.student_id not in grouped:
            grouped[u.student_id] = []
        grouped[u.student_id].append(u.chat_id)

    msg = strings.ADMIN_USER_LIST_HEADER
    for i, (matric, chat_ids) in enumerate(grouped.items(), 1):
        chat_str = ", ".join([f"`{cid}`" for cid in chat_ids])
        msg += f"{i}. {matric} : {chat_str}\n"

    # Simple split if too long (Telegram limit ~4096 chars)
    if len(msg) > 4000:
        for i in range(0, len(msg), 4000):
            await update.message.reply_text(msg[i : i + 4000], parse_mode="Markdown")
    else:
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboards.admin_menu())


async def admin_poll_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Force a background poll for all users."""
    if update.effective_user.id != config.ADMIN_ID:
        return

    # Anti-spam / Rate limit (Global)
    now = datetime.now(timezone.utc).timestamp()
    last_poll = context.bot_data.get("last_global_poll_time", 0)
    if now - last_poll < config.ADMIN_POLL_INTERVAL:
        remaining_secs = int(config.ADMIN_POLL_INTERVAL - (now - last_poll))
        minutes, seconds = divmod(remaining_secs, 60)
        time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
        await update.message.reply_text(
            strings.RATE_LIMIT_ADMIN.format(remaining=time_str),
            parse_mode="Markdown"
        )
        return

    context.bot_data["last_global_poll_time"] = now
    from src.jobs import poll_all_users
    await update.message.reply_text(strings.ADMIN_POLL_STARTED, parse_mode="Markdown")
    # Run in background via job queue or just await if it's small
    asyncio.create_task(poll_all_users(context))


async def admin_logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send current log file to admin."""
    if update.effective_user.id != config.ADMIN_ID:
        return

    import os
    if not os.path.exists(config.ACTIVITY_LOG_PATH):
        await update.message.reply_text("📂 Activity log is empty or missing.")
        return

    try:
        with open(config.ACTIVITY_LOG_PATH, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=f"activity_{datetime.now().strftime('%Y-%m-%d')}.txt",
                caption="📜 *Activity Logs*",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error("Failed to send logs: %s", e)
        await update.message.reply_text("⚠️ Failed to send log file.")


# ── Keyboard button router ────────────────────────────────────────────────────

async def button_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route all main-menu and admin-menu keyboard button taps."""
    text = update.message.text
    
    # Common tools
    if text == "Check Now":
        await check_now(update, context)
    elif text == "Status":
        await status(update, context)
    elif text == "Help":
        await help_cmd(update, context)
    elif text == "Register":
        await register_start(update, context)
    elif text == "Logout":
        await unregister_start(update, context)
    elif text == "Main Menu":
        await start(update, context)

    # Admin tools
    elif text == "User Stats":
        await admin_stats(update, context)
    elif text == "User List":
        await admin_user_list(update, context)
    elif text == "Poll All Now":
        await admin_poll_now(update, context)
    elif text == "View Logs":
        await admin_logs(update, context)
    elif text == "Find User":
        context.user_data["admin_action"] = "find"
        await update.message.reply_text(strings.ADMIN_FIND_USER_PROMPT, parse_mode="Markdown")
        return
    elif text == "Ban/Unban":
        context.user_data["admin_action"] = "ban"
        await update.message.reply_text("Please enter the *Matric ID* to Ban/Unban:", parse_mode="Markdown")
        return
    elif text == "Backup DB":
        await admin_backup_db(update, context)
    elif text == "Maint. Mode":
        await admin_toggle_maintenance(update, context)
    elif text == "Server Performance":
        await admin_performance(update, context)


# ── Advanced Admin Handlers ──────────────────────────────────────────────────



async def admin_toggle_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle the global maintenance mode."""
    if update.effective_user.id != config.ADMIN_ID:
        return

    async with AsyncSessionLocal() as session:
        res = await session.execute(select(SystemSettings).order_by(SystemSettings.id.asc()).limit(1))
        settings = res.scalar_one_or_none()
        if not settings:
            settings = SystemSettings(is_maintenance=True)
            session.add(settings)
        else:
            settings.is_maintenance = not settings.is_maintenance
        
        status = "ACTIVE" if settings.is_maintenance else "INACTIVE"
        await session.commit()

    await update.message.reply_text(
        strings.ADMIN_MAINTENANCE_TOGGLE.format(status=status),
        parse_mode="Markdown"
    )


async def admin_performance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show server performance metrics."""
    if update.effective_user.id != config.ADMIN_ID:
        return

    # Gather stats
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # Calculate uptime
    boot_time = psutil.boot_time()
    uptime_seconds = time.time() - boot_time
    days, rem = divmod(int(uptime_seconds), 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    uptime_str = f"{days}d {hours}h {minutes}m"

    await update.message.reply_text(
        strings.ADMIN_PERFORMANCE.format(
            cpu=cpu,
            ram_used=round(ram.used / (1024**3), 2),
            ram_total=round(ram.total / (1024**3), 2),
            ram_percent=ram.percent,
            disk_used=round(disk.used / (1024**3), 2),
            disk_total=round(disk.total / (1024**3), 2),
            disk_percent=disk.percent,
            uptime=uptime_str
        ),
        parse_mode="Markdown",
        reply_markup=keyboards.admin_menu()
    )


async def admin_backup_db(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a backup of the SQLite database."""
    if update.effective_user.id != config.ADMIN_ID:
        return

    if not os.path.exists(config.DB_PATH):
        await update.message.reply_text("❌ Database file not found.")
        return

    backup_path = f"{config.DB_PATH}.bak"
    try:
        # Create a copy to avoid locking issues
        shutil.copy2(config.DB_PATH, backup_path)
        
        with open(backup_path, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                caption="📅 Database Backup"
            )
    except Exception as e:
        logging.error(f"Backup failed: {e}")
        await update.message.reply_text(f"⚠️ Backup failed: {e}")
    finally:
        if os.path.exists(backup_path):
            os.remove(backup_path)


# ── Broadcast Conversation ───────────────────────────────────────────────────

BROADCAST_MSG, BROADCAST_CONFIRM = range(1, 3)

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user.id != config.ADMIN_ID:
        return ConversationHandler.END
    await update.message.reply_text(strings.ADMIN_BROADCAST_PROMPT, parse_mode="Markdown")
    return BROADCAST_MSG

async def broadcast_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show message preview and ask for confirmation."""
    msg_text = update.message.text
    context.user_data["broadcast_text"] = msg_text
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.active == True))
        users = result.scalars().all()
        count = len(users)

    await update.message.reply_text(
        strings.ADMIN_BROADCAST_PREVIEW.format(message=msg_text, count=count),
        parse_mode="Markdown",
        reply_markup=keyboards.confirmation_keyboard()
    )
    return BROADCAST_CONFIRM

async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Finally send the message to everyone."""
    if update.message.text == "Cancel":
        await update.message.reply_text("❌ Broadcast cancelled.", reply_markup=keyboards.admin_menu())
        return ConversationHandler.END

    msg_text = context.user_data.get("broadcast_text")
    if not msg_text:
        return ConversationHandler.END

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.active == True))
        users = result.scalars().all()
    
    count = 0
    fail = 0
    for u in users:
        try:
            await context.bot.send_message(
                chat_id=u.chat_id,
                text=f"*📢 Broadcast Message*\n\n{msg_text}",
                parse_mode="Markdown"
            )
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail += 1
            
    await update.message.reply_text(
        f"*✅ Broadcast Complete*\n\nSent to: *{count}*\nFailed: *{fail}*",
        parse_mode="Markdown",
        reply_markup=keyboards.admin_menu()
    )
    return ConversationHandler.END


# ── Find & Ban Handlers ──────────────────────────────────────────────────────

async def admin_handle_matric_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text input for Find/Ban in the admin context."""
    if update.effective_user.id != config.ADMIN_ID:
        return
    
    text = update.message.text.upper().strip()
    
    import re
    if not re.match(r"^[A-Z]\d{8}$", text): # Case-insensitive check
        if context.user_data.get("admin_action"):
            await update.message.reply_text("❌ *Invalid format.* Please enter a valid Matric ID (e.g. I24107504):", parse_mode="Markdown")
        return

    async with AsyncSessionLocal() as session:
        res = await session.execute(select(User).where(User.student_id == text))
        users = res.scalars().all()
    
    if not users:
        await update.message.reply_text(strings.ADMIN_USER_NOT_FOUND, parse_mode="Markdown")
        return

    action = context.user_data.get("admin_action")
    
    if action == "ban":
        new_status = False
        async with AsyncSessionLocal() as session:
            for user in users:
                user_to_update = await session.get(User, user.id)
                user_to_update.is_banned = not user_to_update.is_banned
                new_status = user_to_update.is_banned # Capture the new state
            await session.commit()
        
        status_text = "banned 🚫" if new_status else "unbanned ✅"
        await update.message.reply_text(
            f"🎯 *Action Complete*\n\nAll session(s) for Matric *{text}* have been *{status_text}*.",
            parse_mode="Markdown"
        )
        context.user_data["admin_action"] = None
        return

    # Default action: Find (show details for all associated accounts)
    response = f"*👤 User Details for {text}* ({len(users)} account(s))\n\n"
    for i, user in enumerate(users, 1):
        response += (
            f"--- *Account #{i}* ---\n"
            f"Chat ID: `{user.chat_id}`\n"
            f"Status: *{'Active' if user.active else 'Inactive'}*\n"
            f"Created: *{user.created_at.strftime('%Y-%m-%d')}*\n"
            f"Banned: *{'YES 🚫' if user.is_banned else 'NO'}*\n\n"
        )
    
    await update.message.reply_text(response, parse_mode="Markdown", reply_markup=keyboards.admin_menu())
    context.user_data["admin_action"] = None


# ── ConversationHandlers (exported for bot.py) ────────────────────────────────

def broadcast_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Broadcast$"), broadcast_start)],
        states={
            BROADCAST_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_preview)],
            BROADCAST_CONFIRM: [MessageHandler(filters.Regex("^(Confirm Sending|Cancel)$"), broadcast_send)],
        },
        fallbacks=[MessageHandler(filters.Regex("^Main Menu$"), start)],
        name="broadcast",
        persistent=False
    )

async def check_banned(user_id: int) -> bool:
    """Check if a user is banned."""
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(User).where(User.chat_id == str(user_id)))
        user = res.scalar_one_or_none()
        return user.is_banned if user else False


async def check_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the system is in maintenance mode."""
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(SystemSettings).limit(1))
        settings = res.scalar_one_or_none()
        if settings and settings.is_maintenance:
            await update.message.reply_text(strings.ADMIN_MAINTENANCE_ACTIVE_MSG, parse_mode="Markdown")
            return True
    return False


def register_conversation() -> ConversationHandler:
    cancel_filter = filters.Regex(r"^Cancel$") | filters.COMMAND
    return ConversationHandler(
        entry_points=[
            CommandHandler("register", register_start),
            MessageHandler(filters.Regex(r"^Register$"), register_start),
        ],
        states={
            ASK_MEMBERSHIP_ID: [
                MessageHandler(filters.TEXT & ~cancel_filter, receive_membership_id),
                MessageHandler(cancel_filter, _cancel_registration),
            ],
            ASK_STUDENT_ID: [
                MessageHandler(filters.TEXT & ~cancel_filter, receive_student_id),
                MessageHandler(cancel_filter, _cancel_registration),
            ],
            ASK_PASSWORD: [
                MessageHandler(filters.TEXT & ~cancel_filter, receive_password),
                MessageHandler(cancel_filter, _cancel_registration),
            ],
        },
        fallbacks=[MessageHandler(cancel_filter, _cancel_registration)],
    )


def unregister_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("logout", unregister_start),
            CommandHandler("unregister", unregister_start),
            MessageHandler(filters.Regex(r"^Logout$"), unregister_start),
        ],
        states={
            CONFIRM_UNREGISTER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, unregister_confirm),
            ],
        },
        fallbacks=[
            MessageHandler(filters.COMMAND, unregister_confirm),
        ],
    )
