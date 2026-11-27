# SECURITY

## Supported Versions

Security fixes are provided for the latest code on `main`.

## Reporting a Vulnerability

If you discover a security issue, please report it responsibly:

1. **Do not** open a public GitHub issue with exploit details.
2. Contact the maintainer directly (repository owner) with:
   - vulnerability summary
   - impact
   - reproduction steps
   - suggested fix (if available)
3. Allow reasonable time for a fix before public disclosure.

For user-facing bot support, you can also reach the team via Telegram: `@STEMUSAS`.

## Security Practices in This Project

- LMS passwords are encrypted using Fernet before storage. This is a deliberate trade-off: the bot needs the password to re-login when the LMS session expires.
- Session cookies are stored encrypted when persisted.
- Users see a privacy notice before entering credentials, and `/logout` deletes their account and assignment data.
- Accounts with no successful LMS check for 90 days are deleted automatically (`INACTIVE_USER_RETENTION_DAYS`).
- Sensitive values are loaded from environment variables.
- LMS TLS verification is enabled by default (insecure TLS must be explicitly enabled via `LMS_ALLOW_INSECURE_SSL=true`).
- Registration password messages are deleted after processing when possible.
- Registration login attempts are rate-limited with lockout after repeated failures.
- Free-text user messages are redacted in activity logs.
- Submission-status checks are used to avoid sending reminders for already-submitted assignments.

## Residual Risk

Encrypting stored passwords does not protect against a full server compromise if the Fernet key is stored on the same host. The key and database should be separated where possible (for example, a secret manager or a root-only environment file), backups should be protected, and the risk should be explained to users. If the server or key is exposed, rotate `FERNET_KEY` and force affected users to register again.

## Production Hardening Checklist

- Keep `LMS_ALLOW_INSECURE_SSL=false` in production.
- Use `LMS_CA_BUNDLE` instead of disabling TLS verification when custom CA trust is required.
- Never store `service_account.json` in deploy/build contexts; rotate the key immediately if exposure is suspected.
- Ensure Docker builds use `.dockerignore` so `.env`, DB files, and logs are not baked into images.
- Keep `.env` root-only (`chmod 600`) and never include it in backups or demo archives.
- Review `INACTIVE_USER_RETENTION_DAYS` and the purge job logs regularly.

## Scope Notes

- Third-party services (Telegram API, LMS platform, Google Sheets API, hosting providers) are out of direct maintainer control.
- Misconfiguration of deployment secrets is considered an operational risk and should be handled urgently.
