"""Pure helpers for code stimuli, images, and bug-line scoring.

No PsychoPy imports: the experiment loop and the image renderer share this
module so a line number on a picture is the same line number in the log.
"""

from __future__ import annotations

import re
import struct
import zlib
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

_LABEL_FOR_ORIGIN: Dict[str, str] = {
    "human_written": "Написано человеком",
    "ai_generated": "Сгенерировано ИИ",
}
_CLOSES = {")": "(", "]": "[", "}": "{"}
_OPENS = {"(": ")", "[": "]", "{": "}"}
_GUTTER = re.compile(r"^(\s*\d+ \| )")


def _hex_rgb(value: str) -> Tuple[float, float, float]:
    """#RRGGBB as PsychoPy rgb, where 0 is mid-gray and 1 is full intensity."""
    red = int(value[0:2], 16) / 255.0
    green = int(value[2:4], 16) / 255.0
    blue = int(value[4:6], 16) / 255.0
    return (red * 2.0 - 1.0, green * 2.0 - 1.0, blue * 2.0 - 1.0)


# JetBrains Rainbow Brackets gives each bracket type its own palette and counts
# nesting of that type only. A pair shares one color; the next pair of the
# same type takes the next color. The rest of the code stays one editor color.
# Angle brackets are comparisons in Python, so they are left alone.
_TEXT_COLOR = (0.85, 0.85, 0.85)
_GUTTER_COLOR = (-0.25, -0.25, -0.25)
_UNEXPECTED_COLOR = (0.85, -0.55, -0.55)
_BRACKET_PALETTE: Dict[str, Tuple[Tuple[float, float, float], ...]] = {
    "(": (
        _hex_rgb("FFD700"),
        _hex_rgb("FF9F1C"),
        _hex_rgb("FFE66D"),
        _hex_rgb("F4A261"),
    ),
    "[": (
        _hex_rgb("C586C0"),
        _hex_rgb("D16D9E"),
        _hex_rgb("E2B4E0"),
        _hex_rgb("B56BFF"),
    ),
    "{": (
        _hex_rgb("4FC1FF"),
        _hex_rgb("56D6C2"),
        _hex_rgb("7AA2F7"),
        _hex_rgb("2EC4B6"),
    ),
}


def source_lines(code_text: str) -> List[str]:
    """Split source into lines without a phantom trailing blank line."""
    normalized = code_text.replace("\r\n", "\n").replace("\r", "\n")
    if normalized.endswith("\n"):
        normalized = normalized[:-1]
    return normalized.split("\n")


def bracket_paint(
    lines: Sequence[str],
) -> Tuple[
    List[List[Tuple[str, Tuple[float, float, float]]]],
    List[Tuple[int, int, int, Tuple[float, float, float]]],
]:
    """Color brackets the way Rainbow Brackets and VS Code do.

    Returns one list of ``(text, color)`` runs per line, plus vertical guides
    for pairs that span more than one line: ``(open_line, close_line, column, color)``.
    Brackets inside strings and comments stay the normal text color. A closer
    with no opener is the unexpected-bracket red.
    """
    painted: List[List[Tuple[str, Tuple[float, float, float]]]] = []
    guides: List[Tuple[int, int, int, Tuple[float, float, float]]] = []
    stack: List[Tuple[str, int, int, int]] = []
    in_string = False
    string_quote = ""
    string_triple = False
    escape = False

    for line_index, line in enumerate(lines):
        runs: List[Tuple[str, Tuple[float, float, float]]] = []
        buffer = ""
        buffer_color = _TEXT_COLOR

        def flush() -> None:
            nonlocal buffer
            if buffer:
                runs.append((buffer, buffer_color))
                buffer = ""

        def write(text: str, color: Tuple[float, float, float]) -> None:
            nonlocal buffer, buffer_color
            if buffer and buffer_color != color:
                flush()
            buffer_color = color
            buffer += text

        column = 0
        cursor = 0
        if not in_string:
            gutter = _GUTTER.match(line)
            if gutter:
                write(gutter.group(1), _GUTTER_COLOR)
                cursor = gutter.end()
                column = cursor
        while cursor < len(line):
            char = line[cursor]
            if in_string:
                write(char, _TEXT_COLOR)
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif string_triple and line.startswith(string_quote * 3, cursor):
                    write(line[cursor + 1 : cursor + 3], _TEXT_COLOR)
                    cursor += 3
                    column += 3
                    in_string = False
                    continue
                elif not string_triple and char == string_quote:
                    in_string = False
                cursor += 1
                column += 1
                continue
            if char == "#":
                write(line[cursor:], _TEXT_COLOR)
                break
            if char in ("'", '"'):
                triple = line.startswith(char * 3, cursor)
                take = 3 if triple else 1
                write(line[cursor : cursor + take], _TEXT_COLOR)
                in_string = True
                string_quote = char
                string_triple = triple
                escape = False
                cursor += take
                column += take
                continue
            if char in _OPENS:
                depth = sum(1 for opener, _line, _col, _depth in stack if opener == char)
                color = _BRACKET_PALETTE[char][depth % len(_BRACKET_PALETTE[char])]
                flush()
                runs.append((char, color))
                stack.append((char, line_index, column, depth))
            elif char in _CLOSES:
                flush()
                if stack and _OPENS[stack[-1][0]] == char:
                    opener, open_line, open_column, depth = stack.pop()
                    color = _BRACKET_PALETTE[opener][depth % len(_BRACKET_PALETTE[opener])]
                    runs.append((char, color))
                    if line_index > open_line:
                        guides.append((open_line, line_index, open_column, color))
                else:
                    runs.append((char, _UNEXPECTED_COLOR))
            else:
                write(char, _TEXT_COLOR)
            cursor += 1
            column += 1
        flush()
        if in_string and not string_triple:
            in_string = False
            escape = False
        painted.append(runs or [("", _TEXT_COLOR)])
    return painted, guides


def displayed_label(origin: str, label_text: str) -> str:
    """Badge the participant should read. A blank label follows the true origin."""
    text = label_text.strip()
    if text:
        return text
    return _LABEL_FOR_ORIGIN.get(origin, "Источник не указан")


def format_numbered_code(code_text: str) -> str:
    """Prefix each source line with a 1-based, space-padded line number.

    Example: `` 1 | def init():``
    """
    lines = source_lines(code_text)
    width = max(2, len(str(len(lines))))
    return "\n".join(
        f"{index:>{width}} | {line}" for index, line in enumerate(lines, start=1)
    )


def parse_reported_lines(answer: str) -> List[int]:
    """Pull line numbers out of a free-typed answer, in first-seen order.

    The raw answer is still stored. This only supports the count of bugs
    found. "3, 7" and "строки 3 и 7" both become ``[3, 7]``.
    """
    reported: List[int] = []
    token = ""
    for char in answer:
        if char.isdigit():
            token += char
            continue
        if token:
            _append_unique(reported, int(token))
            token = ""
    if token:
        _append_unique(reported, int(token))
    return reported


def score_bug_lines(
    reported: Sequence[int],
    truth: Sequence[int],
) -> Tuple[int, int, int]:
    """Return hit, false-alarm, and miss counts for one trial."""
    reported_set = set(reported)
    truth_set = set(truth)
    hits = len(reported_set & truth_set)
    false_alarms = len(reported_set - truth_set)
    misses = len(truth_set - reported_set)
    return hits, false_alarms, misses


def label_matches_origin(origin: str, label_text: str, show_label: bool) -> Optional[bool]:
    """Whether the badge text is the true origin.

    ``None`` when no badge is shown: there is nothing to match.
    """
    if not show_label:
        return None
    expected = _LABEL_FOR_ORIGIN.get(origin)
    if expected is None:
        return None
    return label_text.strip() == expected


def image_pixel_size(path: Path) -> Tuple[int, int]:
    """Read PNG width and height from the file header."""
    with path.open("rb") as handle:
        header = handle.read(24)
    if not header.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"Stimulus image must be a PNG: {path}")
    width, height = struct.unpack(">II", header[16:24])
    if width <= 0 or height <= 0:
        raise ValueError(f"PNG has an empty canvas: {path}")
    return int(width), int(height)


def fit_within(
    pixel_width: int,
    pixel_height: int,
    box_width: float,
    box_height: float,
) -> Tuple[float, float]:
    """Scale a picture into a box without changing its aspect ratio."""
    if pixel_width <= 0 or pixel_height <= 0:
        raise ValueError("Image dimensions must be positive.")
    if box_width <= 0 or box_height <= 0:
        raise ValueError("Fit box must be positive.")
    aspect = float(pixel_width) / float(pixel_height)
    if (box_width / box_height) > aspect:
        height = box_height
        width = height * aspect
    else:
        width = box_width
        height = width / aspect
    return width, height


def write_solid_png(path: Path, width: int, height: int, rgb: Tuple[int, int, int]) -> None:
    """Write a flat RGB PNG. Used as the ImageStim placeholder before trial 1."""
    if width <= 0 or height <= 0:
        raise ValueError("PNG dimensions must be positive.")

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    row = b"\x00" + bytes(rgb) * width
    raw = row * height
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def format_optional_bool(value: Optional[bool]) -> str:
    if value is None:
        return ""
    return "true" if value else "false"


def _append_unique(values: List[int], item: int) -> None:
    if item not in values:
        values.append(item)
