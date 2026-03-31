"""LMS HTTP client : login, event fetching, and HTML parsing."""
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import aiohttp
from bs4 import BeautifulSoup
from yarl import URL

from src import config

logger = logging.getLogger(__name__)


class LMSAuthenticationError(Exception):
    """Raised when LMS authentication fails."""


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_login_url(url: str) -> bool:
    lowered = url.lower()
    return "/login/" in lowered or "login" in lowered or "/v2/index.php" in lowered


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
        jar = aiohttp.CookieJar(unsafe=True)
        if self.session_cookie:
            jar.update_cookies(
                {"MoodleSession": self.session_cookie},
                response_url=URL(config.LMS_BASE_URL),
            )

        # Bypass SSL verification due to USAS LMS certificate chain issues on some environments
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(
            cookie_jar=jar, 
            connector=aiohttp.TCPConnector(ssl=False),
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

    async def _get_dashboard_html(self, session: aiohttp.ClientSession) -> Tuple[str, bool]:
        """Fetch dashboard HTML, logging in if necessary."""
        dashboard_url = f"{config.LMS_BASE_URL}/my/"
        async with session.get(dashboard_url, allow_redirects=True) as resp:
            html = await resp.text()
            final_url = str(resp.url)
            
            if is_login_url(final_url):
                logger.info("Session expired or missing for %s, logging in...", self.student_id)
                login_html = await self._login(session)
                return login_html, True
            
            return html, False

    async def _login(self, session: aiohttp.ClientSession) -> str:
        """Perform login and return the HTML of the landing page."""
        login_url = f"{config.LMS_BASE_URL}/login/index.php"
        async with session.get(login_url, allow_redirects=True) as resp:
            html = await resp.text()
        
        soup = BeautifulSoup(html, "html.parser")
        token_el = soup.find("input", attrs={"name": "logintoken"})
        payload = {"username": self.student_id, "password": self.password}
        if token_el and token_el.get("value"):
            payload["logintoken"] = token_el.get("value")
        
        async with session.post(login_url, data=payload, allow_redirects=True) as resp:
            final_url = str(resp.url)
            lms_html = await resp.text()
            
            if is_login_url(final_url):
                logger.warning("Login FAILED for %s (still at login URL: %s)", self.student_id, final_url)
                raise LMSAuthenticationError("LMS authentication failed.")
            else:
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
                async with session.post(ajax_url, data=json.dumps(payload), headers=headers) as resp:
                    data = await resp.json(content_type=None)
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

    def _extract_session_cookie(self, session: aiohttp.ClientSession) -> Optional[str]:
        cookies = session.cookie_jar.filter_cookies(config.LMS_BASE_URL)
        moodle = cookies.get("MoodleSession")
        return moodle.value if moodle else None
