import os
import logging
import hashlib
from datetime import datetime
from src import config

logger = logging.getLogger(__name__)


def user_ref(user_name: str, user_id: int) -> str:
    """Return deterministic pseudonymous user reference for activity logs."""
    salt = config.ACTIVITY_LOG_HASH_SALT or config.FERNET_KEY
    raw = f"{salt}|{user_name}|{user_id}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]

def log_activity(user_name: str, user_id: int, action: str, details: str, role: str = "USER") -> None:
    """
    Logs an activity event to the activity log file.
    Format: [YYYY-MM-DD HH:MM:SS] USER: Name (ID) | ACTION: TYPE | Details...
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Format: [2026-03-26 11:00:00] USER: Radzi (123456789) | ACTION: KEYBOARD_CLICK | Button: BTN_CHECK (Check Now)
    # Handle role in name if needed, but requested format uses "USER: Name (ID)"
    masked_ref = user_ref(user_name, user_id)
    log_entry = f"[{timestamp}] USER_REF: {masked_ref} | ACTION: {action} | {details}\n"
    
    try:
        # Ensure log directory exists
        os.makedirs(os.path.dirname(config.ACTIVITY_LOG_PATH), exist_ok=True)
        
        with open(config.ACTIVITY_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        logger.error(f"Failed to write to activity log: {e}")
