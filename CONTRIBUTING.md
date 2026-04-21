# CONTRIBUTING

Thanks for helping improve **USAS Assignment Notifier**.

## Ground Rules

- Keep changes focused and easy to review.
- Do not commit secrets (`.env`, API keys, credentials, database dumps).
- Preserve existing bot behavior unless the change is intentional and documented.
- Prefer small pull requests over one large PR.

## Development Setup

1. Fork and clone the repository.
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   # Windows
   .\.venv\Scripts\Activate.ps1
   # Linux/macOS
   # source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Create local config:
   ```bash
   copy .env.example .env
   ```
4. Run the bot:
   ```bash
   python bot.py
   ```

## Branch and Commit Style

- Create a feature branch:
  - `feat/<short-name>`
  - `fix/<short-name>`
  - `docs/<short-name>`
- Use clear commit messages, for example:
  - `feat: add assignment parser fallback`
  - `fix: stop duplicate pending reminders`
  - `docs: update installation guide`

## Pull Request Checklist

- [ ] Code runs locally without errors.
- [ ] New/changed behavior is tested manually.
- [ ] No credentials or sensitive data are included.
- [ ] Documentation is updated when needed (`README.md`, `INSTALLATION.md`, etc.).
- [ ] PR description clearly explains what changed and why.

## Coding Notes

- Keep async flow non-blocking.
- Reuse existing helpers in `src/` before adding new patterns.
- Keep user-facing messages consistent with `src/strings.py`.
- For database changes, include safe additive migrations in `src/database.py`.

## Reporting Bugs

When opening an issue, include:

- What you expected to happen
- What actually happened
- Steps to reproduce
- Logs or screenshots (if safe)
- Environment details (OS, Python version, deployment target)

