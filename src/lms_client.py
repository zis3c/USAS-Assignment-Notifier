"""LMS HTTP client : login, event fetching, and HTML parsing."""
import asyncio
import json
import logging
import re
import ssl
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import aiohttp
from bs4 import BeautifulSoup
from yarl import URL

from src import config

logger = logging.getLogger(__name__)

SUBMISSION_STATUS_LABEL_HINTS = (
    "submission status",
    "status penghantaran",
)
SUBMISSION_STATUS_POSITIVE_HINTS = (
    "submitted for grading",
    "submitted for marking",
    "already submitted",
    "graded",
    "marked",
    "telah dihantar",
    "sudah dihantar",
    "dihantar untuk penilaian",
    "dihantar untuk pemarkahan",
    "telah dinilai",
)
SUBMISSION_STATUS_NEGATIVE_HINTS = (
    "not submitted",
    "draft (not submitted)",
    "no attempt",
    "nothing submitted",
    "belum dihantar",
    "tiada cubaan",
    "belum hantar",
)
SUBMISSION_BUTTON_POSITIVE_HINTS = (
    "edit submission",
    "view submission",
    "sunting penghantaran",
    "lihat penghantaran",
)
SUBMISSION_BUTTON_NEGATIVE_HINTS = (
    "add submission",
    "tambah penghantaran",
)


class LMSAuthenticationError(Exception):
    """Raised when LMS authentication fails."""


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_login_url(url: str) -> bool:
    lowered = url.lower()
    return "/login/" in lowered or "/login/index.php" in lowered


def page_requires_login(html: str) -> bool:
    """
    Detect whether a response page is actually a login page.
    Some LMS deployments use non-standard paths (for example `/v2/index.php`)
    for both public landing and post-login pages, so URL-only checks are unsafe.
    """
    soup = BeautifulSoup(html, "html.parser")
    has_password = soup.find("input", attrs={"name": "password"}) is not None
    has_username = soup.find("input", attrs={"name": "username"}) is not None
    has_login_token = soup.find("input", attrs={"name": "logintoken"}) is not None
    return bool((has_username and has_password) or has_login_token)


def is_assignment_url(url: str) -> bool:
    return "/mod/assign/view.php" in (url or "").lower()


def _normalize_text(value: str) -> str:
    return " ".join((value or "").split()).strip().lower()


def _classify_submission_text(value: str) -> Optional[bool]:
    text = _normalize_text(value)
    if not text:
        return None
    if any(token in text for token in SUBMISSION_STATUS_NEGATIVE_HINTS):
        return False
    if any(token in text for token in SUBMISSION_STATUS_POSITIVE_HINTS):
        return True
    return None


def parse_is_submitted_from_assignment_html(html: str) -> Optional[bool]:
    """Return True/False if assignment submission status can be inferred, otherwise None."""
    soup = BeautifulSoup(html, "html.parser")

    # 1) Prefer explicit status row in submission status tables.
    for row in soup.select("tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) < 2:
            continue
        label = _normalize_text(cells[0].get_text(" ", strip=True))
        if any(hint in label for hint in SUBMISSION_STATUS_LABEL_HINTS):
            value = cells[1].get_text(" ", strip=True)
            classified = _classify_submission_text(value)
            if classified is not None:
                return classified

    # 2) Fallback to action buttons/links that usually exist on assign page.
    action_text = _normalize_text(" ".join(el.get_text(" ", strip=True) for el in soup.select("a, button")))
    if any(token in action_text for token in SUBMISSION_BUTTON_NEGATIVE_HINTS):
        return False
    if any(token in action_text for token in SUBMISSION_BUTTON_POSITIVE_HINTS):
        return True

    # 3) Final fallback: broad page text scan.
    page_text = _normalize_text(soup.get_text(" ", strip=True))
    return _classify_submission_text(page_text)


def extract_sesskey(html: str) -> Optional[str]:
    match = re.search(r'"sesskey":"([^"]+)"', html)
    return match.group(1) if match else None


def extract_calendar_context(html: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    soup = BeautifulSoup(html, "html.parser")
    node = soup.find(id=re.compile(r"^month-upcoming-mini-"))
    if not node:
        return None, None, None
    course_id = node.get("data-courseid")
    category_id = node.get("data-categoryid")
    context_id = node.get("data-context-id")
    return (
        int(course_id) if course_id and course_id.isdigit() else None,
        int(category_id) if category_id and category_id.isdigit() else None,
        int(context_id) if context_id and context_id.isdigit() else None,
    )


def extract_user_name(html: str) -> Optional[str]:
    """Parse the logged-in user's full name from the Moodle dashboard HTML.

    Methods (in order):
    1. Greeting Header: <h2>Hi, FULL NAME! 👋</h2>
    2. User Menu: The dropdown button usually contains the name.
    3. User ID lookup: Extract M.cfg.userId and find the corresponding link.
    """
    soup = BeautifulSoup(html, "html.parser")

    def clean_name(n: str) -> str:
        if not n: return n
        # Standardize whitespace and remove non-breaking spaces (\xa0)
        n = n.replace('\xa0', ' ').strip()
        # 1. Remove common greetings
        n = re.sub(r"^(?:Hi|Hello|Selamat\s+\w+|Welcome)[,\s]+", "", n, flags=re.I)
        # 2. Remove leading timestamps like "10:30 AM " or "10:30PM"
        n = re.sub(r"^\d{1,2}:\d{2}\s*(?:AM|PM)[\s,]*", "", n, flags=re.I)
        # 3. Handle naked AM/PM artifacts
        # If it starts with "AM " or "PM " (with space), strip it
        n = re.sub(r"^(?:AM|PM)\s+", "", n, flags=re.I)
        # If it's smashed (e.g., "AMAHMAD"), strip only if followed by another Uppercase (e.g., "AHMAD")
        # to avoid stripping "Amir" or "Amanda"
        n = re.sub(r"^(?:AM|PM)(?=[A-Z][A-Z])", "", n, flags=re.I)
        # Final trim of symbols
        return n.strip(" !👋").strip()

    # 1. Login Info: "You are logged in as Full Name" (Most reliable for full name)
    login_info = soup.find("div", class_="logininfo")
    if login_info:
        name_link = login_info.find("a", href=lambda h: h and ("user/profile.php" in h or "user/view.php" in h))
        if name_link:
            name = clean_name(name_link.get_text(strip=True))
            if name: return name

    # 2. Extract userId from M.cfg JS block and find its profile link
    user_id = None
    js_match = re.search(r'"userId":(\d+)', html)
    if js_match:
        user_id = js_match.group(1)

    if user_id:
        user_link = soup.find("a", href=re.compile(fr'user/(?:view|profile)\.php\?id={user_id}'))
        if user_link:
            name = clean_name(user_link.get_text(strip=True))
            if name: return name

    # 3. Greeting Header : "Hi, NAME! 👋" (Usually first name only)
    header = soup.find("div", class_=re.compile(r"headerandnav"))
    if header:
        h2 = header.find("h2")
        if h2:
            text = h2.get_text(separator=" ", strip=True)
            match = re.search(r"Hi,\s+(.+)", text, re.IGNORECASE)
            if match:
                return clean_name(match.group(1))

    # 3. Fallback: User dropdown toggle aria-label or title
    user_toggle = soup.find(id="user-menu-toggle")
    if user_toggle:
        label = user_toggle.get("aria-label", "")
        # "User menu for Full Name"
        match = re.search(r"(?:for|of|untuk)\s+(.+)$", label, re.IGNORECASE)
        if match:
            return clean_name(match.group(1))

    return None


def _extract_subject_code(text: str) -> Optional[str]:
    if not text:
        return None
    match = re.search(r"\b([A-Z]{2,4}\d{3,4})\b", text.upper())
    return match.group(1) if match else None


def _clean_subject_name(value: str) -> str:
    text = " ".join((value or "").split()).strip()
    if not text:
        return ""

    # Normalize forms like:
    # KSC6433 FINANCIAL TECHNOLOGY
    # KSC6433-FINANCIAL TECHNOLOGY
    # KSC6433: FINANCIAL TECHNOLOGY
    match = re.match(
        r"^([A-Z]{2,4}\d{3,4})(?:\s*[-:|]\s*|\s+)(.+)$",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        code = match.group(1).upper()
        name = " ".join(match.group(2).split()).strip()
        return f"{code} {name}" if name else code

    return text


def extract_course_name_map(html: str) -> Dict[str, str]:
    """Build a mapping such as KSC6433 -> FINANCIAL TECHNOLOGY from dashboard cards."""
    soup = BeautifulSoup(html, "html.parser")
    mapping: Dict[str, str] = {}
    for card in soup.select("div.container1"):
        code_el = card.find("b")
        if not code_el:
            continue
        code = _extract_subject_code(code_el.get_text(" ", strip=True))
        if not code:
            continue
        full_text = card.get_text(" ", strip=True)
        name = re.sub(rf"^\s*{re.escape(code)}\s*", "", full_text, flags=re.IGNORECASE).strip(" -:|")
        name = " ".join(name.split())
        if name:
            mapping[code] = name
    return mapping


def _extract_subject(raw: Dict[str, Any], title: str) -> Optional[str]:
    subject_full: Optional[str] = None
    subject_code: Optional[str] = None

    def _consume(value: Any) -> None:
        nonlocal subject_full, subject_code
        if not isinstance(value, str) or not value.strip():
            return
        cleaned = _clean_subject_name(value)
        if not cleaned:
            return
        code = _extract_subject_code(cleaned)
        is_code_only = bool(code and cleaned.upper() == code)
        if is_code_only:
            if subject_code is None:
                subject_code = code
        else:
            if subject_full is None:
                subject_full = cleaned

    course = raw.get("course")
    if isinstance(course, dict):
        for key in ("fullname", "displayname", "shortname"):
            _consume(course.get(key))
    elif isinstance(course, str) and course.strip():
        _consume(course)

    for key in (
        "coursefullname",
        "course_name",
        "coursename",
        "course_shortname",
        "courseshortname",
        "coursecode",
    ):
        _consume(raw.get(key))

    _consume(title)
    return subject_full or subject_code


def enrich_event_subjects(events: List[Dict[str, Any]], html: str) -> List[Dict[str, Any]]:
    """Replace subject codes with full course names when possible."""
    course_map = extract_course_name_map(html)
    if not course_map:
        return events

    enriched: List[Dict[str, Any]] = []
    for event in events:
        item = dict(event)
        subject = (item.get("subject") or "").strip()
        code = _extract_subject_code(subject)
        if code and subject.upper() == code:
            item["subject"] = course_map.get(code, subject)
        elif not subject:
            title_code = _extract_subject_code(item.get("title") or "")
            if title_code and title_code in course_map:
                item["subject"] = course_map[title_code]
        enriched.append(item)

    return enriched




def parse_events_from_html(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    events = []
    for link in soup.select('a[href*="mod/assign/view.php"]'):
        title = link.get_text(strip=True)
        href = link.get("href")
        context_text = " ".join(link.stripped_strings)
        subject = _extract_subject_code(context_text)
        if href:
            events.append(
                {
                    "id": href,
                    "title": title or "Assignment",
                    "subject": subject,
                    "due_at": None,
                    "link": href,
                }
            )
    return events


def normalize_event(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    event_id = raw.get("id") or raw.get("eventid") or raw.get("instance")
    title = raw.get("name") or raw.get("title") or raw.get("eventname")
    url = raw.get("url") or raw.get("viewurl")
    timestart = raw.get("timestart") or raw.get("time") or raw.get("due")

    if not event_id or not title:
        return None

    due_at = None
    if isinstance(timestart, (int, float)):
        due_at = datetime.fromtimestamp(int(timestart), tz=timezone.utc).replace(tzinfo=None)
    subject = _extract_subject(raw, str(title))

    return {
        "id": str(event_id),
        "title": str(title),
        "subject": subject,
        "due_at": due_at,
        "link": str(url) if url else None,
        "modulename": raw.get("modulename") or raw.get("modname"),
    }


def filter_assignment_events(events: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    filtered = []
    for e in events:
        modulename = (e.get("modulename") or "").lower()
        if modulename and modulename != "assign":
            continue
        filtered.append(e)
    return filtered


def extract_events_from_result(data: Any) -> List[Dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    if isinstance(data.get("events"), list):
        return data["events"]
    if isinstance(data.get("eventdata"), list):
        return data["eventdata"]
    if isinstance(data.get("eventsbyday"), list):
        combined: List[Dict[str, Any]] = []
        for day in data["eventsbyday"]:
            if isinstance(day, dict) and isinstance(day.get("events"), list):
                combined.extend(day["events"])
        return combined
    return []


def extract_html_from_result(data: Any) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    for key in ("html", "content"):
        if isinstance(data.get(key), str):
            return data[key]
    return None


# ── Client ────────────────────────────────────────────────────────────────────

@dataclass
class FetchResult:
    events: List[Dict[str, Any]]
    session_cookie: Optional[str]
    dashboard_html: Optional[str] = None


class LMSClient:
    def __init__(self, student_id: str, password: str, session_cookie: Optional[str]):
        self.student_id = student_id
        self.password = password
        self.session_cookie = session_cookie

    async def fetch_events(self) -> FetchResult:
        jar = aiohttp.CookieJar()
        if self.session_cookie:
            jar.update_cookies(
                {"MoodleSession": self.session_cookie},
                response_url=URL(config.LMS_BASE_URL),
            )

        ssl_context = self._build_ssl_context_safe()
        if ssl_context is False:
            logger.warning(
                "LMS SSL verification is DISABLED via LMS_ALLOW_INSECURE_SSL=true. "
                "This should only be used temporarily."
            )
        timeout = aiohttp.ClientTimeout(total=max(10, config.LMS_HTTP_TIMEOUT_SECONDS))
        async with aiohttp.ClientSession(
            cookie_jar=jar, 
            connector=aiohttp.TCPConnector(ssl=ssl_context),
            timeout=timeout
        ) as session:
            html, _ = await self._get_dashboard_html(session)
            sesskey = extract_sesskey(html)
            course_id, category_id, _ = extract_calendar_context(html)

            events: List[Dict[str, Any]] = []
            if sesskey:
                events = await self._fetch_calendar_events(
                    session, sesskey, course_id, category_id
                )

            if not events:
                events = parse_events_from_html(html)
            events = enrich_event_subjects(events, html)

            cookie = self._extract_session_cookie(session)
            return FetchResult(events=events, session_cookie=cookie, dashboard_html=html)

    async def fetch_submission_statuses(
        self, assignment_links: Iterable[str]
    ) -> Tuple[Dict[str, bool], Optional[str]]:
        """Return a mapping {assignment_link: is_submitted} for assignment URLs."""
        unique_links: List[str] = []
        seen = set()
        for link in assignment_links:
            if not link or not isinstance(link, str) or not is_assignment_url(link):
                continue
            if link in seen:
                continue
            seen.add(link)
            unique_links.append(link)

        if not unique_links:
            return {}, self.session_cookie

        jar = aiohttp.CookieJar()
        if self.session_cookie:
            jar.update_cookies(
                {"MoodleSession": self.session_cookie},
                response_url=URL(config.LMS_BASE_URL),
            )

        ssl_context = self._build_ssl_context_safe()
        if ssl_context is False:
            logger.warning(
                "LMS SSL verification is DISABLED via LMS_ALLOW_INSECURE_SSL=true. "
                "This should only be used temporarily."
            )
        timeout = aiohttp.ClientTimeout(total=max(10, config.LMS_HTTP_TIMEOUT_SECONDS))
        async with aiohttp.ClientSession(
            cookie_jar=jar,
            connector=aiohttp.TCPConnector(ssl=ssl_context),
            timeout=timeout,
        ) as session:
            # Ensure authenticated session (self-healing login if needed).
            await self._get_dashboard_html(session)

            sem = asyncio.Semaphore(min(config.MAX_CONCURRENCY, 5))
            statuses: Dict[str, bool] = {}

            async def run_one(link: str) -> None:
                async with sem:
                    submitted = await self._is_assignment_submitted(session, link)
                    if submitted is not None:
                        statuses[link] = submitted

            await asyncio.gather(*(run_one(link) for link in unique_links))
            return statuses, self._extract_session_cookie(session)

    async def _get_dashboard_html(self, session: aiohttp.ClientSession) -> Tuple[str, bool]:
        """Fetch dashboard HTML, logging in if necessary."""
        dashboard_url = f"{config.LMS_BASE_URL}/my/"
        html, final_url = await self._request_text(session, "GET", dashboard_url, allow_redirects=True)

        if is_login_url(final_url) or page_requires_login(html):
            logger.info("Session expired or missing for %s, logging in...", self.student_id)
            login_html = await self._login(session)
            return login_html, True

        return html, False

    async def _login(self, session: aiohttp.ClientSession) -> str:
        """Perform login and return the HTML of the landing page."""
        login_url = f"{config.LMS_BASE_URL}/login/index.php"
        html, _ = await self._request_text(session, "GET", login_url, allow_redirects=True)
        
        soup = BeautifulSoup(html, "html.parser")
        token_el = soup.find("input", attrs={"name": "logintoken"})
        payload = {"username": self.student_id, "password": self.password}
        if token_el and token_el.get("value"):
            payload["logintoken"] = token_el.get("value")
        
        lms_html, final_url = await self._request_text(
            session, "POST", login_url, data=payload, allow_redirects=True
        )

        if is_login_url(final_url) or page_requires_login(lms_html):
            logger.warning("Login FAILED for %s (still at login URL: %s)", self.student_id, final_url)
            raise LMSAuthenticationError("LMS authentication failed.")

        logger.info("Login SUCCESS for %s", self.student_id)
        return lms_html

    async def _fetch_calendar_events(
        self,
        session: aiohttp.ClientSession,
        sesskey: str,
        course_id: Optional[int],
        category_id: Optional[int],
    ) -> List[Dict[str, Any]]:
        ajax_url = f"{config.LMS_BASE_URL}/lib/ajax/service.php?sesskey={sesskey}"
        headers = {"Content-Type": "application/json"}
        now = datetime.now(timezone.utc)
        timesortfrom = int(now.timestamp())
        timesortto = int((now + timedelta(days=config.EVENT_HORIZON_DAYS)).timestamp())

        methods = [
            (
                "core_calendar_get_calendar_upcoming_view",
                {"courseid": course_id or 1, "categoryid": category_id or 0},
            ),
            (
                "core_calendar_get_action_events_by_timesort",
                {
                    "timesortfrom": timesortfrom,
                    "timesortto": timesortto,
                    "limitfrom": 0,
                    "limitnum": 50,
                    "courseid": course_id or 0,
                    "categoryid": category_id or 0,
                    "searchvalue": "",
                    "eventsby": "courses",
                },
            ),
        ]

        for methodname, args in methods:
            payload = [{"index": 0, "methodname": methodname, "args": args}]
            try:
                data = await self._request_json(
                    session,
                    "POST",
                    ajax_url,
                    data=json.dumps(payload),
                    headers=headers,
                )
            except Exception as exc:
                logger.warning("Calendar API [%s] failed: %s", methodname, exc)
                continue

            if not isinstance(data, list) or not data:
                continue
            result = data[0]
            if result.get("error"):
                logger.debug("Calendar API error [%s]: %s", methodname, result.get("exception"))
                continue

            events = extract_events_from_result(result.get("data"))
            if events:
                normalized = [normalize_event(e) for e in events]
                filtered = filter_assignment_events([e for e in normalized if e])
                if filtered:
                    return filtered

            html = extract_html_from_result(result.get("data"))
            if html:
                parsed = parse_events_from_html(html)
                if parsed:
                    return parsed

        return []

    async def _is_assignment_submitted(
        self, session: aiohttp.ClientSession, assignment_url: str
    ) -> Optional[bool]:
        """Check assignment page and infer whether submission is already made."""
        try:
            html, final_url = await self._request_text(
                session, "GET", assignment_url, allow_redirects=True
            )
        except Exception as exc:
            logger.warning("Assignment status fetch failed for %s: %s", assignment_url, exc)
            return None

        if is_login_url(final_url) or page_requires_login(html):
            # Session may have expired between calls; retry once after login.
            try:
                await self._login(session)
            except LMSAuthenticationError:
                return None
            except Exception as exc:
                logger.warning("Re-login failed while checking submission status: %s", exc)
                return None

            try:
                html, retry_final_url = await self._request_text(
                    session, "GET", assignment_url, allow_redirects=True
                )
                if is_login_url(retry_final_url) or page_requires_login(html):
                    return None
            except Exception as exc:
                logger.warning("Assignment status retry failed for %s: %s", assignment_url, exc)
                return None

        return parse_is_submitted_from_assignment_html(html)

    def _extract_session_cookie(self, session: aiohttp.ClientSession) -> Optional[str]:
        cookies = session.cookie_jar.filter_cookies(config.LMS_BASE_URL)
        moodle = cookies.get("MoodleSession")
        return moodle.value if moodle else None

    async def _request_text(
        self,
        session: aiohttp.ClientSession,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> Tuple[str, str]:
        attempts = max(1, int(config.LMS_RETRY_ATTEMPTS))
        for attempt in range(1, attempts + 1):
            try:
                async with session.request(method, url, **kwargs) as resp:
                    return await resp.text(), str(resp.url)
            except (aiohttp.ClientError, asyncio.TimeoutError, ssl.SSLError) as exc:
                if attempt >= attempts:
                    raise
                wait_s = float(config.LMS_RETRY_BACKOFF_SECONDS) * attempt
                logger.warning(
                    "HTTP %s retry %s/%s for %s due to %s; waiting %.1fs",
                    method,
                    attempt,
                    attempts,
                    url,
                    type(exc).__name__,
                    wait_s,
                )
                await asyncio.sleep(wait_s)

    async def _request_json(
        self,
        session: aiohttp.ClientSession,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> Any:
        attempts = max(1, int(config.LMS_RETRY_ATTEMPTS))
        for attempt in range(1, attempts + 1):
            try:
                async with session.request(method, url, **kwargs) as resp:
                    return await resp.json(content_type=None)
            except (aiohttp.ClientError, asyncio.TimeoutError, ssl.SSLError) as exc:
                if attempt >= attempts:
                    raise
                wait_s = float(config.LMS_RETRY_BACKOFF_SECONDS) * attempt
                logger.warning(
                    "HTTP JSON %s retry %s/%s for %s due to %s; waiting %.1fs",
                    method,
                    attempt,
                    attempts,
                    url,
                    type(exc).__name__,
                    wait_s,
                )
                await asyncio.sleep(wait_s)

    @staticmethod
    def _build_ssl_context_safe() -> ssl.SSLContext | bool:
        """
        Build SSL policy with resilience for misconfigured custom CA paths.
        Keeps secure defaults while avoiding hard-fail on bad `LMS_CA_BUNDLE`.
        """
        try:
            return config.build_lms_ssl_context()
        except Exception as exc:
            logger.warning(
                "Invalid TLS configuration for LMS (%s). Falling back to system CA trust.",
                exc,
            )
            return ssl.create_default_context()
