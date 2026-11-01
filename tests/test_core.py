"""Unit tests for Assignment Notifier core logic."""
import os
import unittest
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet

# Configure safe test environment variables before importing src modules
os.environ.setdefault("BOT_TOKEN", "123456789:TEST_TOKEN_DEMO_ONLY_ABC123XYZ")
os.environ.setdefault("FERNET_KEY", Fernet.generate_key().decode("utf-8"))
os.environ.setdefault("DB_PATH", "data/test_lms_notifier.db")

from src import config  # noqa: E402
from src.crypto import decrypt_text, encrypt_text  # noqa: E402
from src.jobs import (  # noqa: E402
    _build_assignment_batches,
    _countdown_stage_days,
    _format_subject,
    _format_title,
    _is_pending,
    _next_poll_at_from_now,
    _should_send_reminder,
)
from src.lms_client import (  # noqa: E402
    enrich_event_subjects,
    extract_calendar_context,
    extract_course_name_map,
    extract_events_from_result,
    extract_sesskey,
    extract_user_name,
    filter_assignment_events,
    is_assignment_url,
    is_login_url,
    normalize_event,
    page_requires_login,
    parse_events_from_html,
    parse_is_submitted_from_assignment_html,
)
from src.logging_utils import user_ref  # noqa: E402
from scripts.migrate_sqlite_to_postgres import postgres_dsn_from_url  # noqa: E402


class CryptoAndLoggingTests(unittest.TestCase):
    def test_encrypt_decrypt_roundtrip(self):
        secret = "P@ssw0rd!2026_USAS"
        blob = encrypt_text(secret)
        self.assertIsInstance(blob, bytes)
        self.assertNotIn(secret.encode("utf-8"), blob)
        self.assertEqual(decrypt_text(blob), secret)

    def test_user_ref_is_deterministic_and_pseudonymous(self):
        ref1 = user_ref("Ahmad", 1001)
        ref2 = user_ref("Ahmad", 1001)
        ref3 = user_ref("Ahmad", 1002)
        self.assertEqual(ref1, ref2)
        self.assertEqual(len(ref1), 12)
        self.assertNotEqual(ref1, ref3)


class LMSClientParsingTests(unittest.TestCase):
    def test_login_url_and_page_detection(self):
        self.assertTrue(is_login_url("https://lms.usas.edu.my/login/index.php"))
        self.assertFalse(is_login_url("https://lms.usas.edu.my/my/"))

        login_html = '<form><input name="username"><input name="password" type="password"></form>'
        token_html = '<form><input name="logintoken" value="abc123"></form>'
        dash_html = '<div class="dashboard"><h2>Hi, ALI!</h2></div>'
        self.assertTrue(page_requires_login(login_html))
        self.assertTrue(page_requires_login(token_html))
        self.assertFalse(page_requires_login(dash_html))

    def test_assignment_url_detection(self):
        self.assertTrue(is_assignment_url("https://lms.usas.edu.my/mod/assign/view.php?id=42"))
        self.assertFalse(is_assignment_url("https://lms.usas.edu.my/mod/quiz/view.php?id=42"))

    def test_parse_submission_status_from_table_and_buttons(self):
        submitted_html = """
        <table>
          <tr><th>Submission status</th><td>Submitted for grading</td></tr>
        </table>
        """
        pending_html = """
        <table>
          <tr><th>Status penghantaran</th><td>Belum dihantar</td></tr>
        </table>
        """
        button_submitted = '<div><a href="#">Edit submission</a></div>'
        button_pending = '<div><button>Add submission</button></div>'

        self.assertTrue(parse_is_submitted_from_assignment_html(submitted_html))
        self.assertFalse(parse_is_submitted_from_assignment_html(pending_html))
        self.assertTrue(parse_is_submitted_from_assignment_html(button_submitted))
        self.assertFalse(parse_is_submitted_from_assignment_html(button_pending))

    def test_extract_sesskey_and_calendar_context(self):
        html = """
        <script>var M = {"cfg":{"sesskey":"S3ssK3y99","userId":77}};</script>
        <div id="month-upcoming-mini-1" data-courseid="12" data-categoryid="3" data-context-id="99"></div>
        """
        self.assertEqual(extract_sesskey(html), "S3ssK3y99")
        self.assertEqual(extract_calendar_context(html), (12, 3, 99))

    def test_extract_user_name_variants(self):
        html_logininfo = '<div class="logininfo">You are logged in as <a href="https://lms/user/profile.php?id=5">SITI NURHALIZA</a></div>'
        self.assertEqual(extract_user_name(html_logininfo), "SITI NURHALIZA")

        html_header = '<div class="headerandnav"><h2>Hi, 10:30 AM AHMAD ZAKI! 👋</h2></div>'
        self.assertEqual(extract_user_name(html_header), "AHMAD ZAKI")

    def test_course_map_and_event_enrichment(self):
        html = """
        <div class="container1"><b>KSC6433</b> - FINANCIAL TECHNOLOGY</div>
        <div class="container1"><b>MPU3123</b> TAMADUN ISLAM</div>
        """
        cmap = extract_course_name_map(html)
        self.assertEqual(cmap, {
            "KSC6433": "FINANCIAL TECHNOLOGY",
            "MPU3123": "TAMADUN ISLAM",
        })
        events = [
            {"id": "1", "title": "Essay 1", "subject": "KSC6433"},
            {"id": "2", "title": "MPU3123 Quiz", "subject": ""},
        ]
        enriched = enrich_event_subjects(events, html)
        self.assertEqual(enriched[0]["subject"], "FINANCIAL TECHNOLOGY")
        self.assertEqual(enriched[1]["subject"], "TAMADUN ISLAM")

    def test_normalize_and_filter_events(self):
        raw_assign = {
            "id": 501,
            "name": "Lab Report 1 is due",
            "url": "https://lms.usas.edu.my/mod/assign/view.php?id=501",
            "timestart": 1767225600,
            "modulename": "assign",
            "course": {"fullname": "KSC6433: FINANCIAL TECHNOLOGY"},
        }
        raw_forum = {
            "id": 502,
            "name": "Forum post",
            "modulename": "forum",
        }
        norm_assign = normalize_event(raw_assign)
        norm_forum = normalize_event(raw_forum)
        self.assertIsNotNone(norm_assign)
        self.assertEqual(norm_assign["id"], "501")
        self.assertEqual(norm_assign["subject"], "KSC6433 FINANCIAL TECHNOLOGY")

        filtered = filter_assignment_events([norm_assign, norm_forum])
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["id"], "501")

    def test_parse_events_from_html_and_result(self):
        html = '<a href="https://lms.usas.edu.my/mod/assign/view.php?id=88">KSC6433 Final Project</a>'
        parsed = parse_events_from_html(html)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["subject"], "KSC6433")

        by_day = {"eventsbyday": [{"events": [{"id": 1}, {"id": 2}]}]}
        self.assertEqual(len(extract_events_from_result(by_day)), 2)


class JobsAndMigrationTests(unittest.TestCase):
    def test_countdown_stages_and_pending(self):
        now = datetime(2026, 11, 1, 12, 0, 0)
        self.assertFalse(_is_pending(now - timedelta(minutes=1), now))
        self.assertTrue(_is_pending(now + timedelta(minutes=1), now))

        self.assertEqual(_countdown_stage_days(now + timedelta(hours=12), now), 1)
        self.assertEqual(_countdown_stage_days(now + timedelta(hours=36), now), 2)
        self.assertEqual(_countdown_stage_days(now + timedelta(hours=60), now), 3)
        self.assertIsNone(_countdown_stage_days(now + timedelta(hours=80), now))

    def test_format_subject_and_title(self):
        self.assertEqual(_format_subject("KSC6433 - FINANCIAL TECHNOLOGY AND AI"), "KSC6433 Financial Technology AND AI")
        self.assertEqual(_format_title("Assignment 2 is due"), "Assignment 2")

    def test_reminder_interval_and_backoff(self):
        now = datetime(2026, 11, 1, 12, 0, 0)
        self.assertTrue(_should_send_reminder(None, now))
        self.assertFalse(_should_send_reminder(now - timedelta(seconds=60), now))
        self.assertTrue(_should_send_reminder(now - timedelta(seconds=config.REMINDER_INTERVAL_SECONDS + 1), now))

        next_ok = _next_poll_at_from_now(now, fail_count=0)
        next_fail = _next_poll_at_from_now(now, fail_count=3)
        self.assertGreater(next_ok, now)
        self.assertGreater(next_fail, now)

    def test_build_assignment_batches_splits_large_payloads(self):
        events = [
            {
                "id": str(i),
                "title": f"Project Deliverable Part {i} " + ("X" * 120),
                "subject": "KSC6433 FINANCIAL TECHNOLOGY",
                "due_at": datetime(2026, 12, 1, 10, 0, tzinfo=timezone.utc),
                "link": f"https://lms.usas.edu.my/mod/assign/view.php?id={i}",
            }
            for i in range(40)
        ]
        batches = _build_assignment_batches(events, "<b>Header</b>")
        self.assertGreater(len(batches), 1)
        total_ids = sum(len(ids) for _, ids in batches)
        self.assertEqual(total_ids, 40)

    def test_postgres_dsn_normalization(self):
        self.assertEqual(
            postgres_dsn_from_url("postgres://user:pass@localhost:5432/db"),
            "postgresql://user:pass@localhost:5432/db",
        )
        self.assertEqual(
            postgres_dsn_from_url("postgresql+asyncpg://user:pass@localhost:5432/db"),
            "postgresql://user:pass@localhost:5432/db",
        )


if __name__ == "__main__":
    unittest.main()
