"""Portrait class schedule renderer for Telegram photo output."""

from __future__ import annotations

import colorsys
from datetime import datetime
from hashlib import md5
from html import escape
from io import BytesIO
from typing import Dict, Iterable, List, Tuple

from PIL import Image, ImageDraw, ImageFont

DAY_ORDER = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
DAY_SHORT_LABELS = ["M", "T", "W", "T", "F", "S", "S"]

BASE_START_HOUR = 8
MAX_END_HOUR = 22  # 10 PM
MAX_VISIBLE_SLOTS = MAX_END_HOUR - BASE_START_HOUR  # 14 rows: 08-09 ... 21-22

FONT_CANDIDATES_REGULAR = [
    "Inter-Regular.ttf",
    "Inter.ttf",
    "/usr/share/fonts/truetype/inter/Inter-Regular.ttf",
    "C:/Windows/Fonts/Inter-Regular.ttf",
    "C:/Windows/Fonts/Inter.ttf",
    "DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
FONT_CANDIDATES_BOLD = [
    "Inter-Bold.ttf",
    "Inter-SemiBold.ttf",
    "/usr/share/fonts/truetype/inter/Inter-Bold.ttf",
    "C:/Windows/Fonts/Inter-Bold.ttf",
    "C:/Windows/Fonts/Inter-SemiBold.ttf",
    "DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = FONT_CANDIDATES_BOLD if bold else FONT_CANDIDATES_REGULAR
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _subject_color(seed: str) -> Tuple[int, int, int]:
    """Deterministic color: same subject code always gets same color."""
    digest = md5(seed.encode("utf-8")).hexdigest()
    hue = int(digest[:4], 16) / 65535.0
    sat = 0.50 + (int(digest[4:6], 16) / 255.0) * 0.25
    val = 0.70 + (int(digest[6:8], 16) / 255.0) * 0.20
    r, g, b = colorsys.hsv_to_rgb(hue, min(max(sat, 0.50), 0.82), min(max(val, 0.66), 0.92))
    return int(r * 255), int(g * 255), int(b * 255)


def _fit_single_line(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> str:
    if draw.textlength(text, font=font) <= max_width:
        return text
    suffix = "..."
    trimmed = text
    while trimmed and draw.textlength(trimmed + suffix, font=font) > max_width:
        trimmed = trimmed[:-1]
    return (trimmed + suffix) if trimmed else suffix


def _subject_code(entry: Dict[str, object]) -> str:
    """Render class code only."""
    code = str(entry.get("subject_code") or "").strip()
    if code:
        return code.upper()
    fallback = str(entry.get("subject") or "SUBJECT").strip()
    return fallback.split(" ", 1)[0].upper() if fallback else "SUBJECT"


def _hour_range_label(slot_idx: int) -> str:
    start_hour = BASE_START_HOUR + slot_idx
    end_hour = start_hour + 1
    return f"{start_hour:02d}-{end_hour:02d}"


def _slot_range(entry: Dict[str, object], visible_slots: int) -> str:
    start_slot = max(0, int(entry.get("start_slot", 0)))
    start_slot = min(start_slot, max(0, visible_slots - 1))
    duration = max(1, int(entry.get("duration_slots", 1)))
    end_slot = min(visible_slots, start_slot + duration)
    start_hour = BASE_START_HOUR + start_slot
    end_hour = BASE_START_HOUR + end_slot
    return f"{start_hour:02d}-{end_hour:02d}"


def _visible_slot_count(entries: List[Dict[str, object]]) -> int:
    """Auto-crop Y-axis based on latest class end, plus one extra period."""
    latest_end = 0
    for entry in entries:
        day = str(entry.get("day", "")).upper()
        if day not in DAY_ORDER:
            continue
        start_slot = max(0, int(entry.get("start_slot", 0)))
        duration = max(1, int(entry.get("duration_slots", 1)))
        if start_slot >= MAX_VISIBLE_SLOTS:
            continue
        end_slot = min(MAX_VISIBLE_SLOTS, start_slot + duration)
        latest_end = max(latest_end, end_slot)

    if latest_end <= 0:
        return MAX_VISIBLE_SLOTS

    # Add one extra visible period after the last class to keep spacing natural.
    return min(MAX_VISIBLE_SLOTS, latest_end + 1)


def _pick_code_font(draw: ImageDraw.ImageDraw, text: str, max_w: int, max_h: int) -> ImageFont.ImageFont:
    for size in (40, 38, 36, 34, 32, 30, 28, 26, 24, 22, 20, 18):
        font = _load_font(size, bold=True)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        if text_w <= max_w and text_h <= max_h:
            return font
    return _load_font(18, bold=True)


def render_timetable_image(
    entries: List[Dict[str, object]],
    time_slots: List[Tuple[str, str]],
    student_name: str,
    generated_at: datetime,
) -> bytes:
    """Render a 1080x1920 portrait class schedule and return PNG bytes."""
    _ = time_slots
    _ = student_name
    _ = generated_at

    width, height = 1080, 1920
    img = Image.new("RGB", (width, height), (247, 249, 252))
    draw = ImageDraw.Draw(img)

    day_font = _load_font(26, bold=True)
    time_font = _load_font(19, bold=True)

    grid_left = 24
    grid_top = 30
    grid_right = width - 24
    grid_bottom = height - 30
    left_time_col_w = 128
    top_day_row_h = 72

    visible_slots = _visible_slot_count(entries)
    day_count = len(DAY_ORDER)

    days_left = grid_left + left_time_col_w
    days_top = grid_top + top_day_row_h
    days_width = grid_right - days_left
    days_height = grid_bottom - days_top
    day_w = days_width / day_count
    slot_h = days_height / visible_slots

    draw.rounded_rectangle((grid_left, grid_top, grid_right, grid_bottom), radius=22, fill=(255, 255, 255))
    draw.rectangle((grid_left, grid_top, grid_right, days_top), fill=(250, 252, 255))
    draw.rectangle((grid_left, grid_top, days_left, grid_bottom), fill=(250, 252, 255))

    # X-axis = day (compact letters)
    for day_idx, short_label in enumerate(DAY_SHORT_LABELS):
        x0 = int(days_left + day_idx * day_w)
        x1 = int(days_left + (day_idx + 1) * day_w)
        cx = x0 + ((x1 - x0) // 2)
        label_w = int(draw.textlength(short_label, font=day_font))
        draw.text((cx - (label_w // 2), grid_top + 20), short_label, fill=(42, 57, 78), font=day_font)
        draw.line((x0, grid_top, x0, grid_bottom), fill=(228, 234, 242), width=1)
    draw.line((grid_right, grid_top, grid_right, grid_bottom), fill=(228, 234, 242), width=1)

    # Y-axis = 24h compact periods (08-09, 13-14, ...)
    for slot_idx in range(visible_slots):
        y0 = int(days_top + slot_idx * slot_h)
        y1 = int(days_top + (slot_idx + 1) * slot_h)
        fill = (254, 255, 255) if slot_idx % 2 == 0 else (251, 253, 255)
        draw.rectangle((days_left + 1, y0 + 1, grid_right - 1, y1 - 1), fill=fill)
        draw.line((grid_left, y0, grid_right, y0), fill=(235, 239, 246), width=1)

        label = _hour_range_label(slot_idx)
        draw.text((grid_left + 16, y0 + int((y1 - y0) * 0.32)), label, fill=(70, 84, 106), font=time_font)

    draw.line((grid_left, days_top, grid_right, days_top), fill=(220, 227, 238), width=2)
    draw.line((days_left, grid_top, days_left, grid_bottom), fill=(220, 227, 238), width=2)
    draw.line((grid_left, grid_bottom, grid_right, grid_bottom), fill=(235, 239, 246), width=1)

    # Class blocks: code only (no time/place inside block)
    for entry in entries:
        day = str(entry.get("day", "")).upper()
        if day not in DAY_ORDER:
            continue

        day_idx = DAY_ORDER.index(day)
        start_slot = max(0, int(entry.get("start_slot", 0)))
        duration = max(1, int(entry.get("duration_slots", 1)))

        if start_slot >= visible_slots:
            continue
        end_slot = min(visible_slots, start_slot + duration)
        duration = end_slot - start_slot
        if duration <= 0:
            continue

        x0 = int(days_left + day_idx * day_w + 5)
        x1 = int(days_left + (day_idx + 1) * day_w - 5)
        y0 = int(days_top + start_slot * slot_h + 5)
        y1 = int(days_top + (start_slot + duration) * slot_h - 5)
        if y1 <= y0 + 34:
            y1 = y0 + 34

        code = _subject_code(entry)
        block_color = _subject_color(code)
        draw.rounded_rectangle((x0, y0, x1, y1), radius=12, fill=block_color)

        content_w = max(20, x1 - x0 - 12)
        content_h = max(20, y1 - y0 - 12)
        code_font = _pick_code_font(draw, code, content_w, content_h)
        code_label = _fit_single_line(draw, code, code_font, content_w)
        bbox = draw.textbbox((0, 0), code_label, font=code_font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        text_x = x0 + ((x1 - x0 - text_w) // 2)
        text_y = y0 + ((y1 - y0 - text_h) // 2) - 1
        draw.text((text_x, text_y), code_label, fill=(255, 255, 255), font=code_font)

    buffer = BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    return buffer.getvalue()


def build_timetable_text_fallback(
    entries: Iterable[Dict[str, object]],
    time_slots: List[Tuple[str, str]],
) -> str:
    """Build a compact HTML text fallback grouped by day."""
    _ = time_slots
    entry_list = list(entries)
    grouped: Dict[str, List[Dict[str, object]]] = {day: [] for day in DAY_ORDER}
    for entry in entry_list:
        day = str(entry.get("day", "")).upper()
        if day in grouped:
            grouped[day].append(entry)

    parts: List[str] = ["<b>Class Schedule (Text Backup)</b>"]
    visible_slots = _visible_slot_count(entry_list)
    for day in DAY_ORDER:
        day_entries = sorted(grouped[day], key=lambda item: int(item.get("start_slot", 0)))
        if not day_entries:
            continue
        parts.append(f"\n<b>{day}</b>")
        for item in day_entries:
            time_range = escape(_slot_range(item, visible_slots))
            subject = escape(_subject_code(item))
            parts.append(f"- <b>{time_range}</b> | {subject}")

    return "\n".join(parts).strip()
