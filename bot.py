"""
Assignment Notifier Bot — Entry Point
────────────────────────────────────────────────────────────────────────────────
Run:  python bot.py
Env:  Copy .env.example → .env and fill in BOT_TOKEN and FERNET_KEY.
────────────────────────────────────────────────────────────────────────────────
"""
import sys
import logging

# Force UTF-8 encoding for Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

from telegram import BotCommand, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, CallbackQueryHandler, filters, TypeHandler, ApplicationHandlerStop
from datetime import datetime, timedelta, timezone
import asyncio
from aiohttp import web, ClientSession

from src import config
from src.database import init_db
from src.handlers import (
    admin_handle_matric_actions,
    admin_logs,
    admin_panel,
    admin_toggle_maintenance,
    broadcast_conversation,
    button_router,
    check_now,
    help_cmd,
    register_conversation,
    start,
    status,
    timetable,
    unregister_conversation,
    check_banned,
    check_maintenance,
)
from src.database import AsyncSessionLocal
from src.models import User, SystemSettings
from sqlalchemy import select
from src.jobs import poll_all_users, send_daily_logs
from src.logging_utils import log_activity

# ── Logging ───────────────────────────────────────────────────────────────────
import os
os.makedirs("logs", exist_ok=True)

from logging.handlers import RotatingFileHandler

log_format = "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(
            config.LOG_FILE_PATH, 
            encoding="utf-8", 
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=0
        )
    ]
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

logger = logging.getLogger("lms_notifier")


def _seconds_until_next_poll_tick(interval_seconds: int) -> float:
    """Seconds until the next local interval boundary (e.g. HH:00 when interval=3600)."""
    now_local = datetime.now(config.LOCAL_TZ)
    midnight_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    elapsed_seconds = (now_local - midnight_local).total_seconds()
    remainder = elapsed_seconds % interval_seconds
    # If we're exactly on the boundary, run immediately.
    return (interval_seconds - remainder) % interval_seconds


# ── Startup hook ──────────────────────────────────────────────────────────────
async def configure_runtime(app: Application) -> None:
    """Configure command list and recurring jobs (safe to call multiple times)."""
    if app.bot_data.get("runtime_configured"):
        return
    app.bot_data["runtime_configured"] = True

    # Register bot command list (shown in Telegram menu)
    try:
        await app.bot.set_my_commands(
            [
                BotCommand("start", "Open the main menu"),
                BotCommand("register", "Link your LMS account"),
                BotCommand("status", "View your account status"),
                BotCommand("check", "Check for new assignments now"),
                BotCommand("timetable", "Show your class schedule"),
                BotCommand("help", "How to use this bot"),
                BotCommand("logout", "Logout / Remove account"),
            ]
        )
    except Exception as e:
        logger.warning("Could not set bot commands: %s", e)

    if app.job_queue is None:
        logger.error("JobQueue unavailable: auto polling/reminders/daily logs are disabled.")
        return

    poll_interval = max(1, config.POLL_INTERVAL_SECONDS)
    if poll_interval != config.POLL_INTERVAL_SECONDS:
        logger.warning(
            "Invalid POLL_INTERVAL_SECONDS=%s; using %s instead.",
            config.POLL_INTERVAL_SECONDS,
            poll_interval,
        )
    first_poll_in = _seconds_until_next_poll_tick(poll_interval)
    next_poll_local = datetime.now(config.LOCAL_TZ) + timedelta(seconds=first_poll_in)

    # Schedule periodic polling once.
    if not app.job_queue.get_jobs_by_name("poll_all_users"):
        app.job_queue.run_repeating(
            poll_all_users,
            interval=poll_interval,
            first=first_poll_in,
            name="poll_all_users",
        )

    # Schedule daily activity log delivery once (default 08:00 Asia/Kuala_Lumpur).
    from datetime import time
    daily_log_time = time(
        hour=config.DAILY_LOG_HOUR,
        minute=config.DAILY_LOG_MINUTE,
        second=0,
        tzinfo=config.LOCAL_TZ,
    )
    if not app.job_queue.get_jobs_by_name("send_daily_logs"):
        app.job_queue.run_daily(
            send_daily_logs,
            time=daily_log_time,
            name="send_daily_logs",
        )

    logger.info(
        "Scheduler started - polling every %ss (next at %s), daily logs at %02d:%02d (%s)",
        poll_interval,
        next_poll_local.strftime("%Y-%m-%d %H:%M:%S"),
        config.DAILY_LOG_HOUR,
        config.DAILY_LOG_MINUTE,
        getattr(config.LOCAL_TZ, "key", str(config.LOCAL_TZ)),
    )


async def post_init(app: Application) -> None:
    """Called once after the Application is initialised."""
    await init_db()
    await configure_runtime(app)

async def global_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global middleware for anti-spam, maintenance, and bans + Activity Logging."""
    if not update.effective_user or not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    actor_name = (
        update.effective_user.first_name
        or update.effective_user.username
        or "unknown"
    )
    text = update.message.text
    
    # --- Activity Logging (Sensitive Data Masking) ---
    safe_buttons = [
        "Check Now", "Status", "Timetable", "Help", "Register", "Logout", "Main Menu",
        "User Stats", "User List", "Poll All Now", "View Logs", "Broadcast",
        "Find User", "Ban/Unban", "Backup DB", "Maint. Mode", "Confirm Sending", "Cancel"
    ]
    
    is_command = text.startswith('/')
    log_text = text
    
    # --- Activity Logging (State-based Masking) ---
    if context.user_data.get("is_typing_password"):
        log_text = "[PASSWORD MASKED]"

    logger.info(f"👤 Activity: {actor_name} ({user_id}) -> {log_text}")

    # --- New Activity Log (Clean Format) ---
    action = "MSG"
    details = log_text
    
    if is_command:
        action = "COMMAND"
    elif text in safe_buttons:
        action = "KEYBOARD_CLICK"
        details = f"Button: {text}"

    # Use first_name for the log as requested (Radzi)
    first_name = update.effective_user.first_name or "Unknown"
    log_activity(first_name, user_id, action, details)

    # 1. Anti-Spam (1 second)
    now = datetime.now(timezone.utc).timestamp()
    last_action = context.user_data.get("last_action_time", 0)
    if now - last_action < config.GLOBAL_ANTI_SPAM_INTERVAL:
        raise ApplicationHandlerStop()
    context.user_data["last_action_time"] = now

    # Skip maintenance/ban for Admin
    if user_id == config.ADMIN_ID:
        return

    # 2. Maintenance Mode
    from src.handlers import check_maintenance
    if await check_maintenance(update, context):
        raise ApplicationHandlerStop()

    # 3. Ban Check
    from src.handlers import check_banned
    if await check_banned(user_id):
        raise ApplicationHandlerStop()


# ── Application setup ─────────────────────────────────────────────────────────
def build_app() -> Application:
    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        .concurrent_updates(True)
        .build()
    )

    # Global check first
    app.add_handler(TypeHandler(Update, global_check), group=-1)

    # Conversation flows (registered first — they take priority)
    app.add_handler(register_conversation())
    app.add_handler(unregister_conversation())
    app.add_handler(broadcast_conversation())

    # Slash commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("check", check_now))
    app.add_handler(CommandHandler("timetable", timetable))
    app.add_handler(CommandHandler("logs", admin_logs))
    app.add_handler(CommandHandler("admin", admin_panel))

    # Keyboard button taps
    app.add_handler(
        MessageHandler(
            filters.Regex(r"^(Check Now|Status|Timetable|Help|Register|Logout|Main Menu|User Stats|User List|Poll All Now|View Logs|Broadcast|Find User|Ban/Unban|Backup DB|Maint. Mode|Server Performance)$"),
            button_router,
        )
    )

    # Callbacks
    from src.handlers import how_it_works_callback, help_back_callback
    app.add_handler(CallbackQueryHandler(how_it_works_callback, pattern="^how_it_works$"))
    app.add_handler(CallbackQueryHandler(help_back_callback, pattern="^help_back$"))

    # Admin text handler (for matric lookups)
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            admin_handle_matric_actions
        )
    )

    return app


# ── Render & Self-Pinger ──────────────────────────────────────────────────────

async def self_pinger() -> None:
    """Pings the bot's own URL every 14 minutes to prevent sleep on Render."""
    if not config.RENDER_EXTERNAL_URL:
        logger.info("📡 RENDER_EXTERNAL_URL not set. Self-pinger disabled.")
        return

    logger.info("💓 Self-pinger started (Interval: 14m)")
    while True:
        await asyncio.sleep(config.SELF_PING_INTERVAL)
        try:
            url = f"{config.RENDER_EXTERNAL_URL.rstrip('/')}/health"
            async with ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        logger.info("💓 Self-Ping: Succesful (200 OK)")
                    else:
                        logger.warning(f"💓 Self-Ping: Unexpected status {resp.status}")
        except Exception as e:
            logger.error(f"⚠️ Self-Ping Failed: {e}")

async def health_check(request: web.Request) -> web.Response:
    """Simple health check endpoint for Render and UptimeRobot."""
    return web.Response(text="Alive", status=200)

async def start_web_server() -> None:
    """Starts a simple aiohttp server to handle health checks."""
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    app.router.add_get("/health/", health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    await site.start()
    logger.info(f"🌐 Web Server started on port {config.PORT}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    logger.error("Exception while handling an update:", exc_info=context.error)

    # Optionally notify the user
    if isinstance(update, Update) and update.effective_message:
        from src import strings
        await update.effective_message.reply_text(
            strings.SOMETHING_WENT_WRONG,
            parse_mode="Markdown"
        )

# ── Main ──────────────────────────────────────────────────────────────────────
async def run_bot() -> None:
    """Main async entry point for the bot and web server."""
    logger.info("🚀  LMS Assignment Notifier starting…")
    
    # 1. Start Web Server immediately to satisfy Render's health check
    await start_web_server()

    # 2. Initialize Database
    from src.database import init_db
    await init_db()
    
    # 3. Initialize Bot
    app = build_app()
    app.add_error_handler(error_handler)
    
    # 4. Start Self-Pinger task
    asyncio.create_task(self_pinger())
    
    # 4. Run Bot Polling
    async with app:
        await app.initialize()
        # In manual lifecycle mode, post_init callback is not invoked automatically.
        await configure_runtime(app)
        await app.start()
        logger.info("📡 Bot is now polling...")
        await app.updater.start_polling(drop_pending_updates=True)
        
        # Keep the loop alive
        while True:
            await asyncio.sleep(3600)

def main() -> None:
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user.")
    except Exception as e:
        logger.critical(f"💥 Fatal error: {e}", exc_info=True)


if __name__ == "__main__":
    main()
