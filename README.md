# USAS DueBot 🎓📝

A professional Telegram bot designed for USAS students to stay on top of their LMS assignments. Never miss a deadline again with real-time notifications and automated deadline tracking.

## 🚀 Features

- **Real-time Notifications**: Get alerted instantly when new assignments are posted on the USAS LMS.
- **Deadline Tracking**: Automated reminders to help you manage your study schedule.
- **Secure Integration**: Safely link your LMS account with encrypted credential storage.
- **Easy Access**: Quick links to jump directly to your assignment tasks.

## 🛠️ Setup & Deployment

### Development / Manual Setup
1. **Clone & Install**:
   ```bash
   git clone https://github.com/zis3c/USAS-Assignment-Notifier.git
   cd USAS-Assignment-Notifier
   pip install -r requirements.txt
   ```
2. **Configure**:
   Copy `.env.example` to `.env` and fill in your tokens.
3. **Run**:
   ```bash
   python bot.py
   ```

### 🐳 Production Deployment (Recommended)
The easiest way to run the bot on your cloud server is using **Docker Compose**:

1. **Prepare**: Ensure Docker and Docker Compose are installed.
2. **Configure**: Create your `.env` file (see `.env.example`).
3. **Launch**:
   ```bash
   docker-compose up -d
   ```
This setup includes:
- **Automatic Restarts**: The bot restarts automatically if the server reboots or the process crashes.
- **Persistent Data**: Database and logs are stored in `./data` and `./logs` on your host.
## 📜 Admin Commands
Access these by sending `/admin` (if your ID is set as `ADMIN_ID` in `.env`):
- **User Stats**: Quick overview of registration.
- **Broadcast**: Send a message to all active users.
- **Server Performance**: Real-time CPU, RAM, and Disk usage monitoring.
- **Maint. Mode**: Toggle global maintenance.
- **View Logs**: Download the latest bot logs directly.

## 🚀 Deployment (Render)

This bot is optimized for deployment as a **Render Web Service** with **PostgreSQL**.

### 1. One-Click Setup
1.  In the Render Dashboard, click **New +** -> **Blueprint**.
2.  Connect this GitHub repository.
3.  Render will automatically detect the `render.yaml` and provision:
    *   **Web Service**: For the bot and health checks.
    *   **PostgreSQL**: For persistent data storage.

### 2. Environment Variables
Configure these in the Render Dashboard (**Environment** section):
- `BOT_TOKEN`: Telegram Bot API token.
- `ADMIN_ID`: Your Telegram numeric ID.
- `FERNET_KEY`: Generated encryption key.
- `SHEET_ID`: Google Sheet ID for membership data.
- `GOOGLE_CREDENTIALS`: Service account JSON string.
- `RENDER_EXTERNAL_URL`: Your app's public URL (e.g., `https://usas-due-bot.onrender.com`).

### 3. Sustainability Features
- **Self-Pinger**: The bot automatically pings its own `/health` endpoint every 14 minutes to stay active on Render's free tier.
- **Port Binding**: Uses port `10000` (default) for Render health checks.
- **Persistent DB**: Uses PostgreSQL to ensure registrations and settings survive restarts.

---
© 2026 USAS Assignment Notifier Team
