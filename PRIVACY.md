# Privacy Notice

USAS Assignment Notifier (DueBot) is a student project. This notice explains what data the bot stores and why.

## Data stored

- Telegram user ID, first name, and chat ID.
- LMS matric number and display name.
- LMS password and session cookie, encrypted with Fernet before storage.
- Assignment metadata (title, subject, due date, link) and notification timestamps.

## Why it is stored

The bot logs in to the USAS LMS on your behalf to check for new assignments and send reminders. The password is stored so the bot can re-login when the LMS session expires.

## Where it is stored

On the bot's own database (SQLite or PostgreSQL) on the project server. Passwords and session cookies are encrypted at rest. The encryption key is kept in the server environment file and is not committed to git.

## Third parties

- Telegram processes bot messages.
- The USAS LMS receives your login and assignment requests.
- The hosting provider stores the server and database.

The bot does not sell data or send it to advertising services.

## Retention and deletion

- `/logout` deletes your user record and assignment metadata immediately.
- Accounts with no successful LMS check for 90 days are deleted automatically.
- You can ask the maintainer to delete your data through Telegram `@STEMUSAS`.

## Risk

No service is completely secure. If the server or database is compromised, encrypted credentials could be exposed if the encryption key is also obtained. Use the bot only if you accept this risk, and do not register an account you do not own.
