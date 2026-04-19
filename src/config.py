"""Configuration : loads .env and exposes all runtime constants."""
import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

# ── Telegram ──────────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required. Set it in your .env file.")

# ── Encryption ────────────────────────────────────────────────────────────────
FERNET_KEY: str = os.getenv("FERNET_KEY", "")
if not FERNET_KEY:
    raise RuntimeError("FERNET_KEY is required. Set it in your .env file.")

# ── LMS ───────────────────────────────────────────────────────────────────────
LMS_BASE_URL: str = os.getenv("LMS_BASE_URL", "https://lms.usas.edu.my").rstrip("/")

# ── Polling & Admin ───────────────────────────────────────────────────────────
POLL_INTERVAL_SECONDS: int = int(os.getenv("POLL_INTERVAL_SECONDS", "3600"))
MAX_CONCURRENCY: int = int(os.getenv("MAX_CONCURRENCY", "10"))
EVENT_HORIZON_DAYS: int = int(os.getenv("EVENT_HORIZON_DAYS", "30"))
REMINDER_INTERVAL_SECONDS: int = int(os.getenv("REMINDER_INTERVAL_SECONDS", "3600"))
ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))
DAILY_LOG_HOUR: int = int(os.getenv("DAILY_LOG_HOUR", "8"))
DAILY_LOG_MINUTE: int = int(os.getenv("DAILY_LOG_MINUTE", "0"))
LOG_FILE_PATH: str = os.getenv("LOG_FILE_PATH", "logs/bot.log")
ACTIVITY_LOG_PATH: str = os.getenv("ACTIVITY_LOG_PATH", "logs/activity.log")
# ── Rate Limiting ───────────────────────────────────────────────────────────
USER_CHECK_INTERVAL = 300  # 5 minutes in seconds
ADMIN_POLL_INTERVAL = 900  # 15 minutes in seconds
GLOBAL_ANTI_SPAM_INTERVAL = 1.0  # 1 second between any interaction

# ── Google Sheets (STEM DB) ───────────────────────────────────────────────────
SHEET_ID: str = os.getenv("SHEET_ID", "")
GOOGLE_CREDENTIALS: str = os.getenv("GOOGLE_CREDENTIALS", "") # JSON string

# ── Time & DB ─────────────────────────────────────────────────────────────────
LOCAL_TZ = ZoneInfo("Asia/Kuala_Lumpur")
DB_PATH: str = os.getenv("DB_PATH", "data/lms_notifier.db")
DATABASE_URL: str = os.getenv("DATABASE_URL", "") # Optional PostgreSQL URL (asyncpg)

# ── Web Runtime & Self-Pinger ─────────────────────────────────────────────────
PORT: int = int(os.getenv("PORT", "10000"))
PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "").rstrip("/") # e.g. https://bot.example.com
SELF_PING_INTERVAL: int = 14 * 60 # 14 minutes
