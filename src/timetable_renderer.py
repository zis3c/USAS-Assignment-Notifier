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

FONT_CANDIDATES_REGULAR = [
    "DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
FONT_CANDIDATES_BOLD = [
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
    """Deterministic color: same subject code -> same color."""
    digest = md5(seed.encode("utf-8")).hexdigest()
    hue = int(digest[:4], 16) / 65535.0
    sat = 0.56 + (int(digest[4:6], 16) / 255.0) * 0.24
    val = 0.70 + (int(digest[6:8], 16) / 255.0) * 0.20
    r, g, b = colorsys.hsv_to_rgb(hue, min(max(sat, 0.52), 0.84), min(max(val, 0.66), 0.93))
    return int(r * 255), int(g * 255), int(b * 255)


def _fit_single_line(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> str:
    if draw.textlength(text, font=font) <= max_width:
        return text
    suffix = "..."
    trimmed = text
    while trimmed and draw.textlength(trimmed + suffix, font=font) > max_width:
        trimmed = trimmed[:-1]
    return (trimmed + suffix) if trimmed else suffix


def _slot_range(entry: Dict[str, object], time_slots: List[Tuple[str, str]]) -> str:
    if not time_slots:
        return "Time N/A"
    start = int(entry.get("start_slot", 0))
    duration = max(1, int(entry.get("duration_slots", 1)))
    start = max(0, min(start, len(time_slots) - 1))
    end_slot = max(0, min(start + duration - 1, len(time_slots) - 1))
    return f"{time_slots[start][0]} - {time_slots[end_slot][1]}"


def _subject_code(entry: Dict[str, object]) -> str:
    """Render code-only for timetable blocks."""
    code = str(entry.get("subject_code") or "").strip()
    if code:
        return code.upper()
    fallback = str(entry.get("subject") or "SUBJECT").strip()
    return fallback.split(" ", 1)[0].upper() if fallback else "SUBJECT"


def render_timetable_image(
    entries: List[Dict[str, object]],
    time_slots: List[Tuple[str, str]],
    student_name: str,
    generated_at: datetime,
) -> bytes:
    """Render a 1080x1920 portrait class schedule and return PNG bytes."""
    _ = student_name
    _ = generated_at

    width, height = 1080, 1920
    img = Image.new("RGB", (width, height), (239, 245, 255))
    draw = ImageDraw.Draw(img)

    for y in range(height):
        ratio = y / height
        r = int(241 - (ratio * 14))
        g = int(247 - (ratio * 9))
        b = int(255 - (ratio * 7))
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    day_font = _load_font(22, bold=True)
    time_font = _load_font(18, bold=True)
    subject_font = _load_font(22, bold=True)
    meta_font = _load_font(16)

    grid_left = 22
    grid_top = 42
    grid_right = width - 22
    grid_bottom = height - 34
    left_time_col_w = 166
    top_day_row_h = 86

    slot_count = max(len(time_slots), 16)
    day_count = len(DAY_ORDER)

    days_left = grid_left + left_time_col_w
    days_top = grid_top + top_day_row_h
    days_width = grid_right - days_left
    days_height = grid_bottom - days_top
    day_w = days_width / day_count
    slot_h = days_height / slot_count

    draw.rounded_rectangle((grid_left, grid_top, grid_right, grid_bottom), radius=20, fill=(255, 255, 255))
    draw.rectangle((grid_left + 1, grid_top + 1, grid_right - 1, grid_top + top_day_row_h), fill=(245, 249, 255))
    draw.rectangle((grid_left + 1, grid_top + 1, grid_left + left_time_col_w, grid_bottom - 1), fill=(247, 250, 255))

    # X-axis = day
    for day_idx, day in enumerate(DAY_ORDER):
        x0 = int(days_left + day_idx * day_w)
        x1 = int(days_left + (day_idx + 1) * day_w)
        cx = x0 + (x1 - x0) // 2
        label_w = int(draw.textlength(day, font=day_font))
        draw.text((cx - (label_w // 2), grid_top + 28), day, fill=(25, 44, 80), font=day_font)
        draw.line((x0, grid_top, x0, grid_bottom), fill=(223, 232, 246), width=1)
    draw.line((grid_right, grid_top, grid_right, grid_bottom), fill=(223, 232, 246), width=1)

    # Y-axis = period/time
    for slot_idx in range(slot_count):
        y0 = int(days_top + slot_idx * slot_h)
        y1 = int(days_top + (slot_idx + 1) * slot_h)
        is_even = (slot_idx % 2 == 0)
        row_fill = (251, 253, 255) if is_even else (248, 251, 255)
        draw.rectangle((days_left + 1, y0 + 1, grid_right - 1, y1 - 1), fill=row_fill)
        draw.line((grid_left, y0, grid_right, y0), fill=(228, 236, 248), width=1)

        if slot_idx < len(time_slots):
            start, end = time_slots[slot_idx]
            label = f"{start}-{end}"
        else:
            label = f"P{slot_idx + 1}"
        label = _fit_single_line(draw, label, time_font, left_time_col_w - 20)
        draw.text((grid_left + 12, y0 + int((y1 - y0) * 0.34)), label, fill=(36, 56, 92), font=time_font)

    draw.line((grid_left, days_top, grid_right, days_top), fill=(210, 221, 239), width=2)
    draw.line((grid_left + left_time_col_w, grid_top, grid_left + left_time_col_w, grid_bottom), fill=(205, 217, 237), width=2)
    draw.line((grid_left, grid_bottom, grid_right, grid_bottom), fill=(228, 236, 248), width=1)

    for entry in entries:
        day = str(entry.get("day", "")).upper()
        if day not in DAY_ORDER:
            continue
        day_idx = DAY_ORDER.index(day)

        start_slot = max(0, int(entry.get("start_slot", 0)))
        duration = max(1, int(entry.get("duration_slots", 1)))
        start_slot = min(start_slot, slot_count - 1)
        duration = min(duration, slot_count - start_slot)

        x0 = int(days_left + day_idx * day_w + 6)
        x1 = int(days_left + (day_idx + 1) * day_w - 6)
        y0 = int(days_top + start_slot * slot_h + 5)
        y1 = int(days_top + (start_slot + duration) * slot_h - 5)
        if y1 <= y0 + 28:
            y1 = y0 + 28

        code = _subject_code(entry)
        block_color = _subject_color(code)
        draw.rounded_rectangle((x0, y0, x1, y1), radius=14, fill=block_color)

        content_w = max(20, x1 - x0 - 12)
        code_label = _fit_single_line(draw, code, subject_font, content_w)
        draw.text((x0 + 6, y0 + 6), code_label, fill=(255, 255, 255), font=subject_font)

        group = str(entry.get("group") or "").strip()
        venue = str(entry.get("venue") or "").strip()
        time_range = _slot_range(entry, time_slots)
        if y1 - y0 >= 72:
            meta_a = _fit_single_line(draw, time_range, meta_font, content_w)
            draw.text((x0 + 6, y0 + 36), meta_a, fill=(241, 247, 255), font=meta_font)
        if y1 - y0 >= 94:
            meta_b = " | ".join(part for part in [group, venue] if part)
            if meta_b:
                meta_b = _fit_single_line(draw, meta_b, meta_font, content_w)
                draw.text((x0 + 6, y0 + 56), meta_b, fill=(241, 247, 255), font=meta_font)

    buffer = BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    return buffer.getvalue()


def build_timetable_text_fallback(
    entries: Iterable[Dict[str, object]],
    time_slots: List[Tuple[str, str]],
) -> str:
    """Build a compact HTML text fallback grouped by day."""
    grouped: Dict[str, List[Dict[str, object]]] = {day: [] for day in DAY_ORDER}
    for entry in entries:
        day = str(entry.get("day", "")).upper()
        if day in grouped:
            grouped[day].append(entry)

    parts: List[str] = ["<b>Class Schedule (Text Backup)</b>"]
    for day in DAY_ORDER:
        day_entries = sorted(grouped[day], key=lambda item: int(item.get("start_slot", 0)))
        if not day_entries:
            continue
        parts.append(f"\n<b>{day}</b>")
        for item in day_entries:
            time_range = escape(_slot_range(item, time_slots))
            subject = escape(_subject_code(item))
            group = str(item.get("group") or "").strip()
            venue = str(item.get("venue") or "").strip()

            extra = " | ".join(part for part in [group, venue] if part)
            if extra:
                extra = f" | {escape(extra)}"
            parts.append(f"- <b>{time_range}</b> | {subject}{extra}")

    return "\n".join(parts).strip()
