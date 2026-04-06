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

- LMS passwords are encrypted using Fernet before storage.
- Session cookies are stored encrypted when persisted.
- Sensitive values are loaded from environment variables.
- Registration password messages are deleted after processing when possible.
- Submission-status checks are used to avoid sending reminders for already-submitted assignments.

## Scope Notes

- Third-party services (Telegram API, LMS platform, Google Sheets API, hosting providers) are out of direct maintainer control.
- Misconfiguration of deployment secrets is considered an operational risk and should be handled urgently.

