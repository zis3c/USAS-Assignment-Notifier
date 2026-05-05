# SQLite -> PostgreSQL Cutover Runbook

This runbook performs a short-freeze migration (`1-3 min`) with immediate rollback path.

## 1) Pre-checks (no downtime)

1. Ensure PostgreSQL exists and `DATABASE_URL` is valid.
2. Ensure new bot code is deployed (contains queue columns + migration scripts).
3. Dry run on copied SQLite file if possible.

## 2) Freeze + backup

```bash
sudo systemctl stop assignment-notifier
cd /opt/assignment-notifier
cp data/lms_notifier.db data/lms_notifier.db.backup.$(date +%Y%m%d_%H%M%S)
```

## 3) Migrate data

```bash
source .venv/bin/activate
export DATABASE_URL='postgresql://USER:PASS@HOST:5432/DBNAME'
python scripts/migrate_sqlite_to_postgres.py --sqlite-path data/lms_notifier.db
python scripts/verify_migration.py --sqlite-path data/lms_notifier.db
```

Hard gates:
- table counts match
- verification script passes
- no null-constraint errors

## 4) Switch bot to PostgreSQL

1. Set `DATABASE_URL` in runtime environment or service env file.
2. Keep `DB_PATH` unchanged as rollback source.

```bash
sudo systemctl daemon-reload
sudo systemctl restart assignment-notifier
sudo journalctl -u assignment-notifier -n 120 --no-pager
```

Check:
- bot starts cleanly
- `/status` works
- manual `/check` works
- at least 2 poll ticks complete

## 5) Rollback (if needed)

```bash
sudo systemctl stop assignment-notifier
# remove/disable DATABASE_URL in service env
sudo systemctl daemon-reload
sudo systemctl start assignment-notifier
sudo journalctl -u assignment-notifier -n 120 --no-pager
```

Notes:
- Do not modify backup SQLite file during rollback window.
- Keep PostgreSQL snapshot for investigation.
