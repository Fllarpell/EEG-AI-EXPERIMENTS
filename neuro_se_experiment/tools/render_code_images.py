"""Render numbered code pictures for the image stimuli.

The participant never sees a live text layout of these snippets. Line numbers
are baked into the PNG with the same formatter the scorer uses.

    pip install pillow
    python tools/render_code_images.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.config import ExperimentConfig
from core.logger import setup_logger
from src.data_manager import DataManager
from src.stimulus_format import format_numbered_code, source_lines

_FONT_CANDIDATES: Tuple[str, ...] = (
    "/System/Library/Fonts/Supplemental/Courier New.ttf",
    "/Library/Fonts/Courier New.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
)


def main() -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise SystemExit(
            "Pillow is required to render stimuli. Install it with: pip install pillow"
        ) from exc

    config = ExperimentConfig()
    logger = setup_logger("neuro_se_render", config.resolve_path(config.DATA_OUT_DIR))
    tasks = DataManager(config, logger).load_tasks()
    font = ImageFont.truetype(_find_font(), 30)
    background = _psychopy_rgb_to_bytes(config.BG_COLOR)
    written = 0
    for task in tasks:
        if task.stimulus_type != "image":
            continue
        if not task.image_path:
            raise SystemExit(f"{task.task_id} is an image trial without image_path.")
        if len(source_lines(task.code_text)) > config.MAX_CODE_LINES:
            raise SystemExit(
                f"{task.task_id} has more than {config.MAX_CODE_LINES} lines "
                "and would not fit one screen."
            )
        image = _render(
            format_numbered_code(task.code_text),
            font,
            background,
            Image,
            ImageDraw,
        )
        destination = config.resolve_path(task.image_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        image.save(destination, format="PNG")
        written += 1
        logger.info("Wrote %s", destination)
    logger.info("Rendered %d stimulus image(s).", written)


def _render(numbered: str, font: object, background: Tuple[int, int, int], image_module: object, draw_module: object) -> object:
    """A tight card. Empty canvas below the snippet reads as a blank screen."""
    lines = numbered.split("\n")
    measure = draw_module.Draw(image_module.new("RGB", (8, 8), background))
    text_width = max(measure.textlength(line, font=font) for line in lines)
    ascent = font.getmetrics()[0] if hasattr(font, "getmetrics") else 30
    line_height = int(ascent) + 16
    width = max(640, int(text_width) + 80)
    height = 56 + len(lines) * line_height
    canvas = image_module.new("RGB", (width, height), background)
    draw = draw_module.Draw(canvas)
    draw.multiline_text(
        (36, 24),
        numbered,
        font=font,
        fill=(236, 236, 236),
        spacing=12,
    )
    return canvas


def _find_font() -> str:
    for candidate in _FONT_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    raise SystemExit(
        "No monospace font found. Install Courier New, Menlo, or DejaVu Sans Mono."
    )


def _psychopy_rgb_to_bytes(color: Tuple[float, float, float]) -> Tuple[int, int, int]:
    channels: List[int] = []
    for channel in color:
        value = int(round((float(channel) + 1.0) / 2.0 * 255.0))
        channels.append(min(255, max(0, value)))
    return channels[0], channels[1], channels[2]


if __name__ == "__main__":
    main()
