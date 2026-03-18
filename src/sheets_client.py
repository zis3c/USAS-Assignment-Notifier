import json
import logging
import os
import time
import asyncio
from typing import Optional, Tuple

import gspread
from google.oauth2.service_account import Credentials

from src import config, strings

logger = logging.getLogger(__name__)

class SheetsClient:
    def __init__(self):
        self.sheet_id = config.SHEET_ID
        self.creds_json = config.GOOGLE_CREDENTIALS
        
        # Cache
        self._cache = {}  # {membership_id: (matric, timestamp)}
        self._CACHE_TTL = 600  # 10 minutes

    def _get_worksheet(self):
        """Authorizes and returns the first worksheet."""
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]

        # 1. Try local file first (Most Reliable)
        json_path = os.path.join(os.getcwd(), "service_account.json")
        if os.path.exists(json_path):
            try:
                creds = Credentials.from_service_account_file(json_path, scopes=scope)
                client = gspread.authorize(creds)
                return client.open_by_key(self.sheet_id).sheet1
            except Exception as fe:
                logger.error(f"❌ Error loading service_account.json: {fe}")
                # Fallback to env

        # 2. Fallback to Env variable
        if not self.creds_json or not self.sheet_id:
            logger.error("❌ SHEET_ID or GOOGLE_CREDENTIALS missing")
            return None

        try:
            # Robust parsing for env fallback
            raw_creds = self.creds_json.strip()
            if (raw_creds.startswith("'") and raw_creds.endswith("'")) or \
               (raw_creds.startswith('"') and raw_creds.endswith('"')):
                raw_creds = raw_creds[1:-1].strip()
            
            raw_creds = raw_creds.replace("\\\\n", "\\n")
            creds_dict = json.loads(raw_creds)
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
            client = gspread.authorize(creds)
            return client.open_by_key(self.sheet_id).sheet1
        except Exception as e:
            logger.error(f"❌ Google Sheets Connection Error: {e}")
            return None

    async def lookup_membership(self, membership_id: str) -> Tuple[Optional[str], Optional[str]]:
        """Wraps the synchronous lookup in an executor to prevent blocking the bot."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._lookup_membership_sync, membership_id)

    def _lookup_membership_sync(self, membership_id: str) -> Tuple[Optional[str], Optional[str]]:
        """Synchronous implementation of membership lookup."""
        membership_id = membership_id.strip()
        
        # Check cache
        if membership_id in self._cache:
            matric, timestamp = self._cache[membership_id]
            if time.time() - timestamp < self._CACHE_TTL:
                return matric, None

        ws = self._get_worksheet()
        if not ws:
            return None, "⚠️ **STEM database connection failed.** Try again later."

        try:
            # Fetch all values to avoid repeated API calls in a loop
            all_rows = ws.get_all_values()
            
            # Find the row with matching membership_id
            found_row = None
            for row in all_rows[1:]: # Skip header
                if len(row) > 15 and row[15].strip().lower() == membership_id.lower():
                    found_row = row
                    break
            
            if not found_row:
                return None, strings.ERR_MEMBERSHIP_NOT_FOUND

            # Verify Status (Column R / Index 17)
            status_val = found_row[17].strip().lower() if len(found_row) > 17 else ""
            if status_val not in ("approved", "✓"):
                return None, "⚠️ Your **STEM membership** is **not yet approved**. Please contact an admin."

            # Extract Matric (Column D / Index 3)
            matric = found_row[3].strip().upper() if len(found_row) > 3 else ""
            if not matric:
                return None, "⚠️ Record found, but no **Matric Number** is associated with this ID."

            # Update cache
            self._cache[membership_id] = (matric, time.time())
            return matric, None

        except Exception as e:
            logger.error(f"❌ Error during sheet lookup: {e}")
            return None, "⚠️ **Database error occurred.** Please try again later."

# Singleton instance
sheets_client = SheetsClient()
