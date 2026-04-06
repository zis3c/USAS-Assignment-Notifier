# USAS Assignment Notifier (USAS DueBot)

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram&logoColor=white)
![PTB](https://img.shields.io/badge/python--telegram--bot-v22.5-2AABEE)
![aiohttp](https://img.shields.io/badge/aiohttp-Async%20HTTP-005571)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen.svg)

A secure async Telegram bot for USAS students that monitors LMS assignments, sends deadline reminders (3 days, 2 days, within 24 hours), and generates a phone-ready timetable wallpaper directly from LMS.

> [!NOTE]
> **Security-first design**: LMS credentials and session cookies are encrypted with Fernet before storage, and plaintext credentials are only used in-memory during login.

## Features

- Async event-driven polling with `python-telegram-bot`, `asyncio`, and `aiohttp`.
- Secure LMS account linking:
  - STEM membership validation via Google Sheets.
  - Encrypted credential storage (`FERNET_KEY`).
  - Session cookie reuse with self-healing re-login.
- Smart assignment notifications:
  - New assignment alerts.
  - Countdown reminders at 3 days, 2 days, and within 24 hours.
  - Deduped notifications (no repeated stage spam).
  - Real submission-status check from assignment pages (reminders stop once submitted).
- Manual scan via `/check` (or **Check Now** button).
- Timetable factory:
  - Fetches timetable from LMS dashboard HTML.
  - Generates high-resolution portrait class schedule image for lock/home screen use.
- Admin tools:
  - User stats/list, poll-all-now, maintenance mode, ban/unban, DB backup.
  - Daily activity log report auto-send.

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/zis3c/USAS-Assignment-Notifier.git
   cd USAS-Assignment-Notifier
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv .venv
   # Windows PowerShell
   .\.venv\Scripts\Activate.ps1
   # Linux/macOS
   # source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   copy .env.example .env   # Windows
   # cp .env.example .env   # Linux/macOS
   ```

5. **Generate `FERNET_KEY`**
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
   Paste that value into `.env`.

6. **Run bot**
   ```bash
   python bot.py
   ```
   or:
   ```powershell
   .\run.ps1
   ```

## Environment Variables

Core:
- `BOT_TOKEN` - Telegram bot token from [@BotFather](https://t.me/BotFather)
- `FERNET_KEY` - Encryption key for LMS credentials/cookies
- `LMS_BASE_URL` - Default: `https://lms.usas.edu.my`

Polling and reminders:
- `POLL_INTERVAL_SECONDS` - Auto scan interval (default `3600`)
- `MAX_CONCURRENCY` - Concurrent user polling limit
- `EVENT_HORIZON_DAYS` - LMS event horizon window
- `REMINDER_INTERVAL_SECONDS` - Generic reminder cooldown

Admin and logs:
- `ADMIN_ID` - Telegram numeric user ID of admin
- `DAILY_LOG_HOUR` / `DAILY_LOG_MINUTE` - Daily activity report time (Asia/Kuala_Lumpur)
- `LOG_FILE_PATH` - Bot runtime log path
- `ACTIVITY_LOG_PATH` - User activity log path

Database:
- `DB_PATH` - SQLite path for local mode
- `DATABASE_URL` - PostgreSQL URL (Render/production)

STEM verification (required for registration flow):
- `SHEET_ID`
- `GOOGLE_CREDENTIALS` (JSON string) or `service_account.json` file

Render keep-alive:
- `PORT`
- `RENDER_EXTERNAL_URL`

## Deploy to Render

This repo includes `render.yaml` with:
- Web service (`python bot.py`)
- PostgreSQL database
- Health check endpoint (`/health`)

Steps:
1. Create a new **Blueprint** service on Render from this repo.
2. Set required environment variables in Render dashboard:
   - `BOT_TOKEN`, `FERNET_KEY`, `ADMIN_ID`
   - `SHEET_ID`, `GOOGLE_CREDENTIALS`
   - `RENDER_EXTERNAL_URL`
3. Deploy.

## Project Structure

```text
USAS-Assignment-Notifier/
|- bot.py                    # Application entrypoint, handlers, scheduler bootstrap
|- run.ps1                   # Windows launcher
|- requirements.txt          # Python dependencies
|- render.yaml               # Render blueprint config
|- Dockerfile                # Container build config
|- .env.example              # Environment template
|- assets/
|  `- fonts/                 # Timetable renderer fonts
|- data/                     # SQLite database (local)
|- logs/                     # Runtime and activity logs
`- src/
   |- config.py              # Environment loading and runtime constants
   |- crypto.py              # Fernet encryption/decryption helpers
   |- database.py            # Async SQLAlchemy engine + migrations
   |- models.py              # ORM models (users, user_events, settings)
   |- handlers.py            # Telegram command/button/conversation handlers
   |- jobs.py                # Polling jobs, reminders, daily logs
   |- lms_client.py          # LMS login/session/events/timetable/submission checks
   |- timetable_renderer.py  # Portrait timetable image rendering (Pillow)
   |- keyboards.py           # Reply/inline keyboard layouts
   |- strings.py             # User-facing text constants
   |- sheets_client.py       # Google Sheets STEM membership verification
   `- logging_utils.py       # Activity logging
```

## Commands

| Command | Description |
|:--------|:------------|
| `/start` | Open main menu |
| `/register` | Link LMS account (STEM-verified flow) |
| `/status` | Show linked account and last scan |
| `/check` | Trigger immediate LMS scan |
| `/timetable` | Generate class schedule image from LMS |
| `/help` | Show usage guide |
| `/logout` | Logout and disable account |
| `/unregister` | Alias of `/logout` |

### Admin Commands

| Command | Description |
|:--------|:------------|
| `/admin` | Open admin dashboard |
| `/logs` | Download activity log file |

## How It Works

1. User registers with STEM membership ID, matric number, and LMS password.
2. Bot validates membership from Google Sheets, then verifies LMS login.
3. Credentials are encrypted and stored; session cookie is reused when possible.
4. Hourly scheduler polls LMS events for active users.
5. Bot sends:
   - New assignment alerts
   - Countdown reminders (3d/2d/within 24h)
   - Manual pending reminders on **Check Now**
6. Before sending pending reminders, bot checks assignment page status to skip already submitted work.
7. `/timetable` fetches LMS timetable HTML and returns a portrait wallpaper-style schedule image.

## Troubleshooting

- **No auto daily logs**
  - Ensure `ADMIN_ID` is set correctly.
  - Ensure `ACTIVITY_LOG_PATH` exists and has content.
- **Registration fails at STEM check**
  - Verify `SHEET_ID` and `GOOGLE_CREDENTIALS` (or `service_account.json`).
- **LMS login fails**
  - Recheck matric/password and LMS accessibility.
- **Windows dependency issues**
  - Use Python 3.10 or 3.11 virtual environment.
