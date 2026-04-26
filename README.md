# USAS Assignment Notifier (USAS DueBot)

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram&logoColor=white)
![PTB](https://img.shields.io/badge/python--telegram--bot-v22.5-2AABEE)
![aiohttp](https://img.shields.io/badge/aiohttp-Async%20HTTP-005571)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen.svg)

A secure async Telegram bot for USAS students that monitors LMS assignments and sends deadline reminders (3 days, 2 days, within 24 hours).

> [!NOTE]
> **Security-first design**: LMS credentials and session cookies are encrypted with Fernet before storage, and plaintext credentials are only used in-memory during login.

## Features

- Async event-driven polling with `python-telegram-bot`, `asyncio`, and `aiohttp`.
- Secure LMS account linking:
  - LMS credential validation during registration.
  - Encrypted credential storage (`FERNET_KEY`).
  - Session cookie reuse with self-healing re-login.
- Smart assignment notifications:
  - New assignment alerts.
  - Countdown reminders at 3 days, 2 days, and within 24 hours.
  - Deduped notifications (no repeated stage spam).
  - Real submission-status check from assignment pages (reminders stop once submitted).
- Manual scan via `/check` (or **Check Now** button).
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
- `LMS_ALLOW_INSECURE_SSL` - Default `false` (keep TLS verification ON in production)
- `LMS_CA_BUNDLE` - Optional custom CA bundle path for LMS TLS verification

Polling and reminders:
- `POLL_INTERVAL_SECONDS` - Auto scan interval (default `3600`)
- `MAX_CONCURRENCY` - Concurrent user polling limit
- `EVENT_HORIZON_DAYS` - LMS event horizon window
- `REMINDER_INTERVAL_SECONDS` - Generic reminder cooldown
- `REGISTER_MAX_ATTEMPTS` - Failed registration-login attempts before lockout
- `REGISTER_LOCKOUT_SECONDS` - Lockout duration after too many failed attempts

Admin and logs:
- `ADMIN_ID` - Telegram numeric user ID of admin
- `DAILY_LOG_HOUR` / `DAILY_LOG_MINUTE` - Daily activity report time (Asia/Kuala_Lumpur)
- `LOG_FILE_PATH` - Bot runtime log path
- `ACTIVITY_LOG_PATH` - User activity log path

Database:
- `DB_PATH` - SQLite path for local mode
- `DATABASE_URL` - Optional PostgreSQL URL (legacy/advanced use; default deployment uses SQLite)

Server runtime:
- `PORT` - Local health endpoint port (set `10001` in DigitalOcean setup)
- `PUBLIC_BASE_URL` - Optional public URL for health self-ping (leave empty on DigitalOcean polling mode)

## Deploy to DigitalOcean (Recommended)

This project is currently deployed on a DigitalOcean Droplet using polling + `systemd`.

1. Clone the repo on the droplet and install dependencies.
2. Copy `.env` (without committing secrets).
3. Keep `PUBLIC_BASE_URL` empty for polling mode.
4. Run with a systemd service, for example:
   - `WorkingDirectory=/opt/assignment-notifier`
   - `ExecStart=/opt/assignment-notifier/.venv/bin/python /opt/assignment-notifier/bot.py`
5. Enable service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now assignment-notifier
   ```

## Auto Deploy (GitHub Actions)

This repository includes `.github/workflows/deploy-digitalocean.yml`.
Every push to `main` triggers automatic deployment to the droplet.
For full setup and troubleshooting, see [AUTO_DEPLOY.md](AUTO_DEPLOY.md).

Required repository secrets:
- `DROPLET_HOST` (example: `203.0.113.10`)
- `DROPLET_USER` (recommended: `deploy`)
- `DROPLET_SSH_KEY` (private SSH key for the deploy user)

Server assumptions:
- App path: `/opt/assignment-notifier`
- Service name: `assignment-notifier`
- Deploy user can run `sudo systemctl restart assignment-notifier`

## Project Structure

```text
USAS-Assignment-Notifier/
|- bot.py                    # Application entrypoint, handlers, scheduler bootstrap
|- run.ps1                   # Windows launcher
|- requirements.txt          # Python dependencies
|- Dockerfile                # Container build config
|- .env.example              # Environment template
|- data/                     # SQLite database (local)
|- logs/                     # Runtime and activity logs
`- src/
   |- config.py              # Environment loading and runtime constants
   |- crypto.py              # Fernet encryption/decryption helpers
   |- database.py            # Async SQLAlchemy engine + migrations
   |- models.py              # ORM models (users, user_events, settings)
   |- handlers.py            # Telegram command/button/conversation handlers
   |- jobs.py                # Polling jobs, reminders, daily logs
   |- lms_client.py          # LMS login/session/events/submission checks
   |- keyboards.py           # Reply/inline keyboard layouts
   |- strings.py             # User-facing text constants
      `- logging_utils.py       # Activity logging
```

## Commands

| Command | Description |
|:--------|:------------|
| `/start` | Open main menu |
| `/register` | Link LMS account |
| `/status` | Show linked account and last scan |
| `/check` | Trigger immediate LMS scan |
| `/help` | Show usage guide |
| `/logout` | Logout and disable account |
| `/unregister` | Alias of `/logout` |

### Admin Commands

| Command | Description |
|:--------|:------------|
| `/admin` | Open admin dashboard |
| `/logs` | Download activity log file |

## How It Works

1. User registers with matric number and LMS password.
2. Bot verifies LMS login before saving credentials.
3. Credentials are encrypted and stored; session cookie is reused when possible.
4. Hourly scheduler polls LMS events for active users.
5. Bot sends:
   - New assignment alerts
   - Countdown reminders (3d/2d/within 24h)
   - Manual pending reminders on **Check Now**
6. Before sending pending reminders, bot checks assignment page status to skip already submitted work.

Logout behavior:
- `/logout` removes the user record and linked assignment metadata from the database.

## Troubleshooting

- **No auto daily logs**
  - Ensure `ADMIN_ID` is set correctly.
  - Ensure `ACTIVITY_LOG_PATH` exists and has content.
- **LMS login fails**
  - Recheck matric/password and LMS accessibility.
- **Windows dependency issues**
  - Use Python 3.10 or 3.11 virtual environment.

## Additional Docs

- [AUTO_DEPLOY.md](AUTO_DEPLOY.md)
- [INSTALLATION.md](INSTALLATION.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [SECURITY.md](SECURITY.md)
- [LICENSE](LICENSE)

<center>Built with 🔥 by <b>@zis3c</b></center>


