# INSTALLATION

This guide covers local setup and deployment basics for **USAS Assignment Notifier**.

## Requirements

- Python 3.10+
- `pip`
- Telegram bot token from [@BotFather](https://t.me/BotFather)
- A valid `FERNET_KEY`

## 1) Clone Project

```bash
git clone https://github.com/zis3c/USAS-Assignment-Notifier.git
cd USAS-Assignment-Notifier
```

## 2) Create Virtual Environment

```bash
python -m venv .venv
```

Activate it:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# Linux/macOS
source .venv/bin/activate
```

## 3) Install Dependencies

```bash
pip install -r requirements.txt
```

## 4) Configure Environment

Copy template:

```bash
# Windows
copy .env.example .env
# Linux/macOS
# cp .env.example .env
```

Generate Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set at minimum in `.env`:

- `BOT_TOKEN`
- `FERNET_KEY`
- `LMS_BASE_URL` (default is already provided)
- `ADMIN_ID` (required for daily log auto-send)

Recommended security settings:
- Keep `LMS_ALLOW_INSECURE_SSL=false` (default).
- If your environment needs custom trust roots, set `LMS_CA_BUNDLE` to a valid CA bundle path.

## 5) Run Bot

```bash
python bot.py
```

Or on Windows:

```powershell
.\run.ps1
```

## 6) Verify It Works

- Send `/start` to your bot.
- Complete `/register`.
- Try `/check`.
- Confirm scheduler logs show polling started.

## Docker (Optional)

Build:

```bash
docker build -t usas-due-bot .
```

Security note:
- `.dockerignore` excludes `.env`, `service_account.json`, `data/`, and `logs/` to avoid leaking secrets into images.

Run:

```bash
docker run --env-file .env -p 10000:10000 usas-due-bot
```

## DigitalOcean Deployment (Recommended)

1. Create `/opt/assignment-notifier` on your droplet and clone this repository.
2. Create and activate a virtual environment, then install dependencies:
   - `python3 -m venv .venv`
   - `. .venv/bin/activate`
   - `pip install -r requirements.txt`
3. Configure `.env` with production values, then keep `PUBLIC_BASE_URL` empty for polling mode.
4. Create a `systemd` service to run `python bot.py`.
5. Enable it with `sudo systemctl enable --now assignment-notifier` and verify logs with:
   - `journalctl -u assignment-notifier -n 100 --no-pager`

## Common Issues

- `BOT_TOKEN is required`: set `BOT_TOKEN` in `.env`.
- `FERNET_KEY is required`: generate and set `FERNET_KEY`.
- Daily logs not sent: verify `ADMIN_ID` is correct.
- LMS login failures: verify matric/password and LMS availability.
- Windows package build issues: use Python 3.10/3.11 virtual environment.


