"""Portrait timetable renderer for Telegram photo output."""

from __future__ import annotations

from datetime import datetime
from hashlib import md5
from html import escape
from io import BytesIO
from typing import Dict, Iterable, List, Optional, Tuple

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
    digest = md5(seed.encode("utf-8")).hexdigest()
    # Pick from strong but readable palette.
    palette = [
        (24, 119, 242),
        (41, 163, 85),
        (242, 153, 74),
        (220, 53, 69),
        (111, 66, 193),
        (0, 166, 153),
        (255, 99, 71),
        (0, 128, 255),
    ]
    index = int(digest[:2], 16) % len(palette)
    return palette[index]


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


def render_timetable_image(
    entries: List[Dict[str, object]],
    time_slots: List[Tuple[str, str]],
    student_name: str,
    generated_at: datetime,
) -> bytes:
    """Render a 1080x1920 portrait timetable image and return PNG bytes."""
    width, height = 1080, 1920
    img = Image.new("RGB", (width, height), (241, 246, 255))
    draw = ImageDraw.Draw(img)

    # Soft vertical gradient background.
    for y in range(height):
        ratio = y / height
        r = int(241 - (ratio * 18))
        g = int(246 - (ratio * 10))
        b = int(255 - (ratio * 6))
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    title_font = _load_font(52, bold=True)
    subtitle_font = _load_font(26)
    small_font = _load_font(20)
    block_title_font = _load_font(20, bold=True)
    block_meta_font = _load_font(16)

    # Header
    draw.rounded_rectangle((36, 36, width - 36, 220), radius=28, fill=(21, 38, 74))
    draw.text((64, 66), "USAS Timetable Factory", fill=(255, 255, 255), font=title_font)
    draw.text(
        (64, 132),
        _fit_single_line(draw, f"Student: {student_name or 'Unknown'}", subtitle_font, width - 220),
        fill=(217, 228, 255),
        font=subtitle_font,
    )
    generated_str = generated_at.strftime("%d %b %Y, %I:%M %p")
    draw.text((64, 172), f"Generated: {generated_str}", fill=(181, 199, 237), font=small_font)

    grid_left = 36
    grid_top = 270
    grid_right = width - 36
    grid_bottom = height - 64
    day_col_width = 138
    slot_count = max(len(time_slots), 16)
    timeline_left = grid_left + day_col_width
    timeline_width = grid_right - timeline_left
    slot_width = timeline_width / slot_count
    row_height = (grid_bottom - grid_top) / 7

    # Grid container.
    draw.rounded_rectangle((grid_left, grid_top, grid_right, grid_bottom), radius=26, fill=(255, 255, 255))

    # Time labels.
    label_y = grid_top - 28
    for idx, (start, _) in enumerate(time_slots[:slot_count]):
        if idx % 2 != 0:
            continue
        short = start.replace(" AM", "A").replace(" PM", "P")
        x = int(timeline_left + idx * slot_width + 4)
        draw.text((x, label_y), short, fill=(34, 57, 94), font=small_font)

    # Grid lines + day labels.
    for row_idx, day in enumerate(DAY_ORDER):
        y0 = int(grid_top + row_idx * row_height)
        y1 = int(grid_top + (row_idx + 1) * row_height)
        bg = (250, 252, 255) if row_idx % 2 == 0 else (246, 249, 255)
        draw.rectangle((grid_left + 2, y0 + 1, grid_right - 2, y1 - 1), fill=bg)
        draw.text((grid_left + 22, y0 + int(row_height * 0.35)), day, fill=(25, 42, 76), font=_load_font(22, bold=True))
        draw.line((grid_left, y0, grid_right, y0), fill=(220, 228, 242), width=1)

    draw.line((grid_left, grid_bottom, grid_right, grid_bottom), fill=(220, 228, 242), width=1)
    draw.line((timeline_left, grid_top, timeline_left, grid_bottom), fill=(205, 217, 237), width=2)
    for slot_idx in range(slot_count + 1):
        x = int(timeline_left + slot_idx * slot_width)
        line_color = (228, 234, 245) if slot_idx % 2 == 0 else (238, 242, 250)
        draw.line((x, grid_top, x, grid_bottom), fill=line_color, width=1)

    # Class blocks.
    for entry in entries:
        day = str(entry.get("day", "")).upper()
        if day not in DAY_ORDER:
            continue
        day_idx = DAY_ORDER.index(day)
        start_slot = max(0, int(entry.get("start_slot", 0)))
        duration = max(1, int(entry.get("duration_slots", 1)))
        start_slot = min(start_slot, slot_count - 1)
        duration = min(duration, slot_count - start_slot)

        x0 = int(timeline_left + start_slot * slot_width + 4)
        x1 = int(timeline_left + (start_slot + duration) * slot_width - 4)
        y0 = int(grid_top + day_idx * row_height + 10)
        y1 = int(grid_top + (day_idx + 1) * row_height - 10)
        if x1 <= x0 + 24:
            x1 = x0 + 24

        subject_code = str(entry.get("subject_code") or entry.get("subject") or "SUBJECT")
        block_color = _subject_color(subject_code)
        draw.rounded_rectangle((x0, y0, x1, y1), radius=14, fill=block_color)

        content_width = max(40, x1 - x0 - 14)
        subject = str(entry.get("subject") or subject_code)
        time_range = _slot_range(entry, time_slots)
        venue = str(entry.get("venue") or "")
        group = str(entry.get("group") or "")
        meta = " | ".join(part for part in [time_range, group, venue] if part)

        draw.text(
            (x0 + 7, y0 + 8),
            _fit_single_line(draw, subject, block_title_font, content_width),
            fill=(255, 255, 255),
            font=block_title_font,
        )
        draw.text(
            (x0 + 7, y0 + 36),
            _fit_single_line(draw, meta, block_meta_font, content_width),
            fill=(242, 246, 255),
            font=block_meta_font,
        )

    footer_font = _load_font(18)
    draw.text(
        (grid_left + 6, height - 40),
        "Tip: Use this as your lock screen wallpaper.",
        fill=(70, 89, 121),
        font=footer_font,
    )

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

    parts: List[str] = ["<b>Weekly Timetable (Text Backup)</b>"]
    for day in DAY_ORDER:
        day_entries = sorted(grouped[day], key=lambda item: int(item.get("start_slot", 0)))
        if not day_entries:
            continue
        parts.append(f"\n<b>{day}</b>")
        for item in day_entries:
            time_range = escape(_slot_range(item, time_slots))
            subject = escape(str(item.get("subject") or item.get("subject_code") or "Subject"))
            group = str(item.get("group") or "").strip()
            venue = str(item.get("venue") or "").strip()

            extra = " | ".join(part for part in [group, venue] if part)
            if extra:
                extra = f" | {escape(extra)}"
            parts.append(f"- <b>{time_range}</b> | {subject}{extra}")

    return "\n".join(parts).strip()
