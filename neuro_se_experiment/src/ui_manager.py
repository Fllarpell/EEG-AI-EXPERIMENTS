"""PsychoPy window, stimuli, and keyboard capture.

The code viewport is either an image (the study default) or a numbered
text field. Both are created once. A trial only switches which one is drawn,
so the answer box, the Next button, and the keystroke clock stay put.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.config import ExperimentConfig
from src.stimulus_format import (
    bracket_paint,
    fit_within,
    format_numbered_code,
    image_pixel_size,
    write_solid_png,
)


class UIManager:
    """Owns the PsychoPy window and the stimuli reused across trials."""

    def __init__(self, config: ExperimentConfig, logger: logging.Logger) -> None:
        self._config = config
        self._logger = logger.getChild("ui")
        self._closed = False
        self._core: Any = None
        self._event: Any = None
        self.win: Any = None
        self.keyboard: Any = None
        self.code_stim: Any = None
        self.code_image: Any = None
        self.badge_box: Any = None
        self.badge_stim: Any = None
        self.prompt_stim: Any = None
        self.input_box: Any = None
        self.next_button: Any = None
        self.code_panel: Any = None
        self.progress_stim: Any = None
        self.line_stims: List[Any] = []
        self.run_stims: List[Any] = []
        self.guide_stims: List[Any] = []
        self._guide_count = 0
        self.button_label: Any = None
        self._show_image = False
        self._show_badge = False
        self._line_style = "mono"
        self._rainbow_count = 0
        self._rainbow_run_count = 0
        self._task: Optional[Dict[str, Any]] = None
        self._wait_message = ""
        self._mode = "wait"
        self._laid_out_size: Optional[Tuple[int, int]] = None
        self._char_advance = 0.0
        self._keystroke_log: List[Dict[str, Any]] = []
        self._live_keys: List[Tuple[Any, Dict[str, Any]]] = []
        self._button_was_down = False
        self._last_click_time = 0.0

        core, event, visual, keyboard = _load_psychopy()
        self._core = core
        self._event = event
        try:
            _quiet_psychopy_console()
            self._visual = visual
            self.win = visual.Window(
                size=config.WINDOW_SIZE,
                fullscr=config.FULLSCREEN,
                color=config.BG_COLOR,
                colorSpace="rgb",
                units=config.UNITS,
                allowGUI=True,
                title=" ",
                winType="pyglet",
            )
            self.win.mouseVisible = True
            self._set_resizable(not config.FULLSCREEN)
            self._release_escape_from_psychopy_quit()
            self.keyboard = keyboard.Keyboard()
            placeholder = self._write_placeholder()

            self.code_stim = visual.TextStim(
                self.win,
                text="",
                font=config.FONT_CODE,
                color=config.CODE_COLOR,
                height=config.CODE_LETTER_HEIGHT,
                units=config.UNITS,
                wrapWidth=1.0,
                anchorHoriz="left",
                anchorVert="top",
                alignText="left",
                autoLog=False,
            )
            self.code_panel = visual.Rect(
                self.win,
                width=1.2,
                height=0.6,
                units=config.UNITS,
                fillColor=(-0.72, -0.72, -0.72),
                lineColor=(-0.45, -0.45, -0.45),
                lineWidth=2,
                autoLog=False,
            )
            self.progress_stim = visual.TextStim(
                self.win,
                text="",
                font=config.FONT_UI,
                color=(0.85, 0.85, 0.85),
                height=0.028,
                units=config.UNITS,
                anchorHoriz="left",
                anchorVert="center",
                alignText="left",
                autoLog=False,
            )
            self.line_stims = [
                visual.TextStim(
                    self.win,
                    text="",
                    font=config.FONT_CODE,
                    color=config.CODE_COLOR,
                    height=config.CODE_LETTER_HEIGHT,
                    units=config.UNITS,
                    anchorHoriz="left",
                    anchorVert="top",
                    alignText="left",
                    wrapWidth=1.4,
                    autoLog=False,
                )
                for _ in range(config.MAX_CODE_LINES)
            ]
            self.code_image = visual.ImageStim(
                self.win,
                image=str(placeholder),
                units=config.UNITS,
                pos=(0, 0.08),
                size=(0.2, 0.2),
                interpolate=True,
                autoLog=False,
            )
            self.badge_box = visual.Rect(
                self.win,
                width=0.62,
                height=0.06,
                units=config.UNITS,
                fillColor=config.BADGE_FILL_COLOR,
                lineColor=None,
                autoLog=False,
            )
            self.badge_stim = visual.TextStim(
                self.win,
                text="",
                font=config.FONT_UI,
                color="white",
                height=0.026,
                units=config.UNITS,
                anchorHoriz="center",
                anchorVert="center",
                alignText="center",
                wrapWidth=0.58,
                autoLog=False,
            )
            self.prompt_stim = visual.TextStim(
                self.win,
                text=config.PROMPT_TEXT,
                font=config.FONT_UI,
                color=config.PROMPT_COLOR,
                height=config.PROMPT_LETTER_HEIGHT,
                units=config.UNITS,
                wrapWidth=1.0,
                anchorHoriz="left",
                anchorVert="center",
                alignText="left",
                autoLog=False,
            )
            self.input_box = visual.TextBox2(
                self.win,
                text="",
                font=config.FONT_CODE,
                letterHeight=config.CODE_LETTER_HEIGHT,
                size=(1.0, 0.11),
                units=config.UNITS,
                color=config.INPUT_TEXT_COLOR,
                fillColor=config.INPUT_FILL_COLOR,
                borderColor="white",
                borderWidth=2,
                alignment="left",
                editable=True,
                placeholder=config.INPUT_PLACEHOLDER,
                autoLog=False,
            )
            # ButtonStim draws with bold Arvo, which has no Cyrillic glyphs,
            # so the label is a separate TextStim in the same face as the prompt.
            self.next_button = visual.ButtonStim(
                self.win,
                text="",
                font=config.FONT_UI,
                bold=False,
                letterHeight=0.024,
                size=(0.56, 0.11),
                units=config.UNITS,
                color=config.BUTTON_TEXT_COLOR,
                fillColor=(-0.05, 0.12, 0.38),
                borderColor="white",
                borderWidth=2,
                autoLog=False,
            )
            self.button_label = visual.TextStim(
                self.win,
                text=config.BUTTON_TEXT,
                font=config.FONT_UI,
                color=config.BUTTON_TEXT_COLOR,
                height=0.024,
                units=config.UNITS,
                anchorHoriz="center",
                anchorVert="center",
                alignText="center",
                wrapWidth=0.52,
                autoLog=False,
            )
            self._line_style = config.LINE_STYLE if config.LINE_STYLE in ("mono", "rainbow") else "mono"
            self._pointer_style = ""
            self._apply_task_layout()
            self._last_click_time = float(core.getTime())
            self._release_writing_cursor()
            self._sync_pointer()
            self._fit_drawable()
            self.win.flip()
        except Exception:
            self._logger.exception("Failed to build the PsychoPy window.")
            self.close()
            raise

        self._logger.info(
            "Window ready (%s, fullscreen=%s).",
            config.WINDOW_SIZE,
            config.FULLSCREEN,
        )

    def prepare_task_screen(
        self,
        code_text: str,
        stimulus_type: str,
        image_path: Optional[Path],
        show_label: bool,
        label_text: str,
        button_text: str,
    ) -> None:
        """Show one snippet, either as a picture or as numbered text.

        The picture is scaled into a fixed viewport. Nothing scrolls, and
        the trial does not end on a timer.
        """
        self._task = {
            "code_text": code_text,
            "stimulus_type": stimulus_type,
            "image_path": image_path,
            "show_label": show_label,
            "label_text": label_text,
            "button_text": button_text,
        }
        self._mode = "task"
        self._paint_task()
        self.input_box.clear()
        self.input_box.hasFocus = True
        self._arm_next_button()

    def refresh_view(self) -> None:
        """Redraw the current snippet after a style change or a resize.

        The answer already typed in the box stays put.
        """
        if self._mode != "task" or self._task is None:
            return
        self._paint_task()

    def update_task_content(
        self,
        code_text: str,
        stimulus_type: str,
        image_path: Optional[Path],
        show_label: bool,
        label_text: str,
        button_text: str,
    ) -> None:
        """Replace the snippet on screen. The answer box is not cleared."""
        if self._task is None:
            return
        self._task["code_text"] = code_text
        self._task["stimulus_type"] = stimulus_type
        self._task["image_path"] = image_path
        self._task["show_label"] = show_label
        self._task["label_text"] = label_text
        self._task["button_text"] = button_text
        self._mode = "task"
        self._paint_task()

    def toggle_fullscreen(self) -> bool:
        """Switch fullscreen. A windowed session stays resizable."""
        if self.win is None:
            return False
        enabled = not bool(self.win.fullscr)
        self.win.fullscr = enabled
        self._set_resizable(not enabled)
        self._laid_out_size = None
        self.win.flip()
        if self._mode == "wait" and self._wait_message:
            self.show_wait_screen(self._wait_message)
        elif self._mode == "task":
            self.refresh_view()
        return enabled

    def set_line_style(self, style: str) -> None:
        """``mono`` is one color. ``rainbow`` colors bracket pairs like the editor plugin."""
        if style not in ("mono", "rainbow"):
            raise ValueError("line style must be 'mono' or 'rainbow'.")
        self._line_style = style

    def set_progress(self, index: int, total: int) -> None:
        self.progress_stim.text = f"Задание {index} из {total}"

    def begin_form(self, prompt: str, button_text: str) -> None:
        """Ask one intake question in the same answer box used for line numbers."""
        self._show_image = False
        self._show_badge = False
        self._apply_form_layout()
        self.code_stim.text = prompt
        self.next_button.text = ""
        if self.button_label is not None:
            self.button_label.text = button_text
        self.input_box.clear()
        self.input_box.hasFocus = True
        self._arm_next_button()

    def show_wait_screen(self, message: str) -> None:
        """Center an instruction. Task chrome is not drawn."""
        self._mode = "wait"
        self._wait_message = message
        self._show_image = False
        self._show_badge = False
        self._rainbow_run_count = 0
        aspect = self._aspect_ratio()
        self.code_stim.anchorHoriz = "center"
        self.code_stim.anchorVert = "center"
        self.code_stim.alignText = "center"
        self.code_stim.pos = (0, 0.05)
        self.code_stim.wrapWidth = max(0.4, aspect * 0.72)
        self.code_stim.height = self._config.PROMPT_LETTER_HEIGHT
        self.code_stim.text = message
        self.input_box.hasFocus = False
        self._laid_out_size = self._current_size()

    def draw_wait_frame(self) -> None:
        """Flip the instruction screen."""
        self._fit_drawable()
        if self._current_size() != self._laid_out_size and self._wait_message:
            self.show_wait_screen(self._wait_message)
        self.code_stim.draw()
        self._sync_pointer()
        self._flip()

    def draw_form_frame(self) -> None:
        """Flip an intake question plus the answer box."""
        self.code_stim.draw()
        self.input_box.hasFocus = True
        self.input_box.draw()
        self.next_button.draw()
        if self.button_label is not None:
            self.button_label.draw()
        self._flip()

    def draw(self) -> None:
        """Draw the current snippet, the badge if this trial has one, and flip."""
        self._fit_drawable()
        if self._current_size() != self._laid_out_size:
            self.refresh_view()
        self.code_panel.draw()
        self.progress_stim.draw()
        if self._show_image:
            self.code_image.draw()
        elif self._line_style == "rainbow" and self._rainbow_run_count:
            for stim in self.guide_stims[: self._guide_count]:
                stim.draw()
            for stim in self.run_stims[: self._rainbow_run_count]:
                if stim.text:
                    stim.draw()
        else:
            self.code_stim.draw()
        if self._show_badge:
            self.badge_box.draw()
            self.badge_stim.draw()
        self.prompt_stim.draw()
        self.input_box.hasFocus = True
        self.input_box.draw()
        self.next_button.draw()
        if self.button_label is not None:
            self.button_label.draw()
        self._sync_pointer()
        self._flip()

    def _sync_pointer(self) -> None:
        """Arrow on the task, a writing mark only over the answer, a hand on Next.

        The window's hidden text view would otherwise show a writing cursor
        over the whole screen.
        """
        if self.win is None:
            return
        style = "arrow"
        if self._mode == "task":
            pointer = getattr(self.win, "_mouse", None)
            pos = None if pointer is None else pointer.getPos()
            if pos is not None and self._pointer_over(self.input_box, pos):
                style = "ibeam"
            elif pos is not None and self._pointer_over(self.next_button, pos):
                style = "hand"
        if style == self._pointer_style:
            return
        self._apply_pointer_style(style)
        self._pointer_style = style

    def _release_writing_cursor(self) -> None:
        """Stop the macOS text view from claiming the pointer over the whole window."""
        view = getattr(getattr(getattr(self.win, "backend", None), "winHandle", None), "_nsview", None)
        if view is None:
            return
        try:
            children = view.subviews()
            for index in range(int(children.count())):
                child = children.objectAtIndex_(index)
                if hasattr(child, "setSelectable_"):
                    child.setSelectable_(False)
                if hasattr(child, "setEditable_"):
                    child.setEditable_(False)
        except Exception:
            self._logger.debug("Could not change the system text cursor.", exc_info=True)

    def _apply_pointer_style(self, style: str) -> None:
        backend = getattr(self.win, "backend", None)
        if style in ("ibeam", "hand") and backend is not None and hasattr(backend, "setMouseCursor"):
            backend.setMouseCursor(style)
            return
        try:
            from pyglet.libs.darwin.cocoapy import ObjCClass

            ObjCClass("NSCursor").arrowCursor().set()
        except Exception:
            if backend is not None and hasattr(backend, "setMouseCursor"):
                backend.setMouseCursor("default")

    def _pointer_over(self, stim: Any, pos: Any) -> bool:
        try:
            return bool(stim.contains(float(pos[0]), float(pos[1])))
        except Exception:
            return False

    def get_user_input(self) -> str:
        """Return the answer box contents exactly as typed."""
        return str(self.input_box.text)

    def check_next_clicked(self) -> bool:
        """Return True on a fresh Next click, with a short debounce.

        Current PsychoPy ``ButtonStim`` exposes ``isClicked`` (held down
        inside the button). Older builds expose ``buttonSelected``. Either
        one is treated as a level signal and converted to a rising edge so
        a held mouse cannot skip the following trial.
        """
        selected = self._next_button_is_down()
        now = float(self._core.getTime())
        triggered = (
            selected
            and not self._button_was_down
            and (now - self._last_click_time) >= self._config.BUTTON_DEBOUNCE_SEC
        )
        self._button_was_down = selected
        if triggered:
            self._last_click_time = now
        return triggered

    def sync_keyboard_clock(self, clock: Any) -> None:
        """Time keystroke reaction times from the trial clock."""
        self.keyboard.clock = clock

    def clear_keyboard_buffer(self) -> None:
        """Drop keys that arrived before the trial and reset the stroke log."""
        self.keyboard.clearEvents()
        self._event.clearEvents()
        self._keystroke_log = []
        self._live_keys = []

    def read_key_names(self) -> List[str]:
        """Read hardware-keyboard names without recording them as trial data."""
        return [str(key.name) for key in self.keyboard.getKeys(waitRelease=False)]

    def poll_keystrokes(self) -> List[Dict[str, Any]]:
        """Append new presses to the trial log and return just those presses.

        Duration is filled later, because PsychoPy only knows it after the
        key is released; the same ``KeyPress`` object is kept so the value
        can be copied at the end of the trial.
        """
        fresh: List[Dict[str, Any]] = []
        for key in self.keyboard.getKeys(waitRelease=False):
            name = str(key.name)
            rt_value = getattr(key, "rt", None)
            if rt_value is None and getattr(self.keyboard, "clock", None) is not None:
                rt_value = self.keyboard.clock.getTime()
            duration_value = getattr(key, "duration", None)
            entry: Dict[str, Any] = {
                "key_name": name,
                "rt": None if rt_value is None else float(rt_value),
                "duration": None if duration_value is None else float(duration_value),
            }
            self._keystroke_log.append(entry)
            self._live_keys.append((key, entry))
            fresh.append(entry)
        return fresh

    def collect_keystroke_log(self) -> List[Dict[str, Any]]:
        """Return a copy of the stroke log with release durations filled in."""
        for key, entry in self._live_keys:
            duration_value = getattr(key, "duration", None)
            if duration_value is not None:
                entry["duration"] = float(duration_value)
        return [dict(item) for item in self._keystroke_log]

    def close(self) -> None:
        """Close the window. A second call is a no-op."""
        if self._closed:
            return
        self._closed = True
        win = self.win
        self.win = None
        if win is None:
            return
        try:
            win.close()
            self._logger.info("PsychoPy window closed.")
        except Exception:
            self._logger.exception("Error while closing the PsychoPy window.")

    def _try_show_image(self, image_path: Optional[Path], code_text: str) -> bool:
        if image_path is None or not image_path.is_file():
            self._logger.error(
                "Image stimulus is missing (%s). Showing numbered text instead.",
                image_path,
            )
            return False
        try:
            pixel_width, pixel_height = image_pixel_size(image_path)
            box_width, box_height, center = self._code_viewport()
            fitted_width, fitted_height = fit_within(
                pixel_width,
                pixel_height,
                box_width,
                box_height,
            )
            self.code_image.image = str(image_path)
            self.code_image.size = (fitted_width, fitted_height)
            self.code_image.pos = center
        except Exception:
            self._logger.exception(
                "Could not load %s. Showing numbered text instead.",
                image_path,
            )
            return False
        self._logger.info("Showing image %s", image_path.name)
        return True

    def _paint_task(self) -> None:
        """Lay out the snippet, the source badge, and the answer bar."""
        task = self._task
        if task is None:
            return
        self._apply_task_layout()
        self.prompt_stim.text = self._config.PROMPT_TEXT
        self.next_button.text = ""
        if self.button_label is not None:
            self.button_label.text = str(task["button_text"])
        self._show_badge = bool(task["show_label"] and str(task["label_text"]).strip())
        self.badge_stim.text = str(task["label_text"])
        self._show_image = False
        self._rainbow_run_count = 0
        self._guide_count = 0
        image_path = task["image_path"]
        if self._line_style != "rainbow" and task["stimulus_type"] == "image":
            self._show_image = self._try_show_image(image_path, str(task["code_text"]))
        if self._show_image:
            self._fit_panel(self.code_image.size, self.code_image.pos)
        else:
            self._show_numbered_text(str(task["code_text"]))
        self._place_source_row()
        self._laid_out_size = self._current_size()

    def _show_numbered_text(self, code_text: str) -> None:
        numbered = format_numbered_code(code_text)
        lines = numbered.split("\n")
        if self._line_style == "rainbow":
            self._layout_rainbow_lines(lines)
            self.code_stim.text = ""
        else:
            self._rainbow_run_count = 0
            self._guide_count = 0
            self._place_text_block(lines)
            self.code_stim.text = numbered
        self._logger.info(
            "Showing numbered text (%d lines, %s).",
            len(lines),
            self._line_style,
        )

    def _layout_rainbow_lines(self, lines: List[str]) -> None:
        count = min(len(lines), self._config.MAX_CODE_LINES)
        if len(lines) > count:
            self._logger.warning("Rainbow view keeps the first %d lines.", count)
        self._rainbow_count = count
        left, top = self._place_text_block(lines[:count])
        step = self._config.CODE_LETTER_HEIGHT * 1.45
        advance = self._mono_advance()
        self._ensure_run_stims()
        painted, guides = bracket_paint(lines[:count])
        used = 0
        max_runs = 24
        for index, runs in enumerate(painted):
            if len(runs) > max_runs:
                head = runs[: max_runs - 1]
                tail = "".join(text for text, _color in runs[max_runs - 1 :])
                head.append((tail, runs[max_runs - 1][1]))
                runs = head
            cursor = left
            y_pos = top - index * step
            for text, color in runs:
                if used >= len(self.run_stims):
                    break
                stim = self.run_stims[used]
                stim.text = text
                stim.color = color
                stim.pos = (cursor, y_pos)
                stim.height = self._config.CODE_LETTER_HEIGHT
                stim.wrapWidth = 8.0
                used += 1
                cursor += len(text) * advance
        self._rainbow_run_count = used
        for stim in self.run_stims[used:]:
            stim.text = ""
        self._place_bracket_guides(guides, left, top, step, advance)

    def _place_bracket_guides(
        self,
        guides: List[Tuple[int, int, int, Tuple[float, float, float]]],
        left: float,
        top: float,
        step: float,
        advance: float,
    ) -> None:
        """Vertical line from an opener down to its closer, in that pair's color."""
        self._ensure_guide_stims(len(guides))
        letter = self._config.CODE_LETTER_HEIGHT
        for index, (open_line, close_line, column, color) in enumerate(guides):
            stim = self.guide_stims[index]
            x_pos = left + column * advance + advance * 0.45
            y_start = top - open_line * step - letter
            y_end = top - close_line * step
            stim.start = (x_pos, y_start)
            stim.end = (x_pos, y_end)
            stim.lineColor = color
        self._guide_count = len(guides)

    def _ensure_guide_stims(self, count: int) -> None:
        if self.win is None:
            return
        visual = self._visual
        while len(self.guide_stims) < count:
            self.guide_stims.append(
                visual.Line(
                    self.win,
                    start=(0, 0),
                    end=(0, -0.1),
                    units=self._config.UNITS,
                    lineColor=(1, 1, 1),
                    lineWidth=2,
                    autoLog=False,
                )
            )

    def _place_text_block(self, lines: List[str]) -> Tuple[float, float]:
        """Size the card to the snippet and return the first line's top-left."""
        step = self._config.CODE_LETTER_HEIGHT * 1.45
        block_height = max(len(lines), 1) * step
        box_width, box_height, center = self._code_viewport()
        panel_height = min(box_height, block_height + 0.06)
        self.code_panel.width = box_width
        self.code_panel.height = panel_height
        self.code_panel.pos = center
        left = center[0] - box_width / 2.0 + 0.04
        top = center[1] + panel_height / 2.0 - 0.03
        self.code_stim.anchorHoriz = "left"
        self.code_stim.anchorVert = "top"
        self.code_stim.alignText = "left"
        self.code_stim.pos = (left, top)
        self.code_stim.wrapWidth = box_width - 0.08
        self.code_stim.height = self._config.CODE_LETTER_HEIGHT
        return left, top

    def _fit_panel(self, size: Tuple[float, float], pos: Tuple[float, float]) -> None:
        self.code_panel.width = float(size[0]) + 0.04
        self.code_panel.height = float(size[1]) + 0.04
        self.code_panel.pos = pos

    def _place_source_row(self) -> None:
        """Put the progress and the source badge on one quiet row above the code."""
        top = self.code_panel.pos[1] + self.code_panel.height / 2.0
        left = self.code_panel.pos[0] - self.code_panel.width / 2.0
        right = left + self.code_panel.width
        y_pos = min(0.46, top + 0.045)
        self.progress_stim.pos = (left, y_pos)
        badge_x = right - 0.31
        self.badge_box.pos = (badge_x, y_pos)
        self.badge_stim.pos = (badge_x, y_pos)

    def _ensure_run_stims(self) -> None:
        if self.run_stims or self.win is None:
            return
        visual = self._visual
        config = self._config
        self.run_stims = [
            visual.TextStim(
                self.win,
                text="",
                font=config.FONT_CODE,
                color=config.CODE_COLOR,
                height=config.CODE_LETTER_HEIGHT,
                units=config.UNITS,
                anchorHoriz="left",
                anchorVert="top",
                alignText="left",
                wrapWidth=8.0,
                autoLog=False,
            )
            for _ in range(config.MAX_CODE_LINES * 24)
        ]

    def _mono_advance(self) -> float:
        """Width of one monospace cell in height units.

        PsychoPy reports ``boundingBox`` in pixels. Treating that number as a
        height-unit offset pushes the code off the right edge of the screen.
        """
        if self._char_advance > 0:
            return self._char_advance
        probe = self.code_stim
        saved = probe.text
        probe.height = self._config.CODE_LETTER_HEIGHT
        probe.text = "M"
        narrow = float(probe.boundingBox[0])
        probe.text = "MM"
        wide = float(probe.boundingBox[0])
        probe.text = saved
        pixels = wide - narrow
        window_height = float(self._current_size()[1]) or 1.0
        advance = pixels / window_height
        letter = self._config.CODE_LETTER_HEIGHT
        if not (letter * 0.35 <= advance <= letter * 1.2):
            advance = letter * 0.6
        self._char_advance = advance
        return advance

    def _set_resizable(self, enabled: bool) -> None:
        """Let the participant drag the window edges.

        Changing the macOS style mask on a fullscreen window grabs the display
        and leaves a black screen that no longer answers the keyboard.
        """
        if self.win is None or bool(getattr(self.win, "fullscr", False)):
            return
        handle = getattr(getattr(self.win, "backend", None), "winHandle", None)
        if handle is None:
            return
        handle._resizable = bool(enabled)
        nswindow = getattr(handle, "_nswindow", None)
        if nswindow is None:
            return
        try:
            from pyglet.libs.darwin.cocoapy.cocoalibs import NSResizableWindowMask
        except Exception:
            return
        mask = int(nswindow.styleMask())
        if enabled:
            mask |= NSResizableWindowMask
        else:
            mask &= ~int(NSResizableWindowMask)
        nswindow.setStyleMask_(mask)

    def _current_size(self) -> Tuple[int, int]:
        if self.win is None:
            return self._config.WINDOW_SIZE
        size = self.win.size
        return int(size[0]), int(size[1])

    def _fit_drawable(self) -> None:
        """Stretch the drawing area to the real window.

        Dragging the edge grows the macOS window, but PsychoPy keeps painting
        the original rectangle. The rest of the window stays black, so the
        task looks shifted into the lower left.
        """
        win = self.win
        if win is None:
            return
        backend = getattr(win, "backend", None)
        handle = getattr(backend, "winHandle", None)
        context = getattr(getattr(handle, "context", None), "_nscontext", None)
        if context is None:
            return
        try:
            view = context.view()
            backing = view.convertRectToBacking_(view.bounds()).size
            points = view.bounds().size
            back_w, back_h = int(backing.width), int(backing.height)
            point_w, point_h = int(points.width), int(points.height)
        except Exception:
            return
        if back_w < 2 or back_h < 2:
            return
        current = tuple(int(value) for value in backend.frameBufferSize)
        if current == (back_w, back_h):
            return
        win.clientSize[:] = (point_w, point_h)
        backend._frameBufferSize[:] = (back_w, back_h)
        win.resetViewport()
        win.resetEyeTransform()
        self._laid_out_size = None

    def _apply_task_layout(self) -> None:
        left, usable_width, _top = self._frame()
        box_width, box_height, center = self._code_viewport()
        self.code_panel.width = box_width
        self.code_panel.height = box_height
        self.code_panel.pos = center

        self.code_stim.anchorHoriz = "left"
        self.code_stim.anchorVert = "top"
        self.code_stim.alignText = "left"
        self.code_stim.pos = (left + 0.04, 0.38)
        self.code_stim.wrapWidth = box_width - 0.08
        self.code_stim.height = self._config.CODE_LETTER_HEIGHT

        self.progress_stim.pos = (left, 0.455)
        badge_x = left + usable_width - 0.31
        badge_y = 0.455
        self.badge_box.pos = (badge_x, badge_y)
        self.badge_stim.pos = (badge_x, badge_y)

        self.prompt_stim.anchorHoriz = "left"
        self.prompt_stim.anchorVert = "center"
        self.prompt_stim.alignText = "left"
        self.prompt_stim.pos = (left, -0.31)
        self.prompt_stim.wrapWidth = usable_width
        self.prompt_stim.height = self._config.PROMPT_LETTER_HEIGHT
        self._place_answer_bar(left, usable_width)

    def _apply_form_layout(self) -> None:
        left, usable_width, _top = self._frame()
        aspect = self._aspect_ratio()
        self.code_stim.anchorHoriz = "center"
        self.code_stim.anchorVert = "center"
        self.code_stim.alignText = "center"
        self.code_stim.pos = (0, 0.12)
        self.code_stim.wrapWidth = aspect * 0.7
        self.code_stim.height = self._config.PROMPT_LETTER_HEIGHT
        self._place_answer_bar(left, usable_width)

    def _place_answer_bar(self, left: float, usable_width: float) -> None:
        button_width = 0.56
        gap = 0.03
        input_width = usable_width - button_width - gap
        y_pos = -0.42
        self.input_box.pos = (left + input_width / 2.0, y_pos)
        self.input_box.size = (input_width, 0.11)
        self.next_button.pos = (left + input_width + gap + button_width / 2.0, y_pos)
        self.next_button.size = (button_width, 0.11)
        if self.button_label is not None:
            self.button_label.pos = self.next_button.pos

    def _code_viewport(self) -> Tuple[float, float, Tuple[float, float]]:
        """Fixed rectangle the snippet must fit inside. No scrolling."""
        left, usable_width, _top = self._frame()
        box_top = 0.40
        box_bottom = -0.24
        box_height = box_top - box_bottom
        center = (left + usable_width / 2.0, (box_top + box_bottom) / 2.0)
        return usable_width, box_height, center

    def _frame(self) -> Tuple[float, float, float]:
        aspect = self._aspect_ratio()
        half_width = aspect / 2.0
        margin = self._config.MARGIN
        left = -half_width + margin
        usable_width = aspect - (2.0 * margin)
        top = 0.5 - margin
        return left, usable_width, top

    def _write_placeholder(self) -> Path:
        path = self._config.resolve_path(self._config.DATA_OUT_DIR) / "_placeholder.png"
        # PsychoPy rgb -0.8 is about 26/255, the same gray as the window.
        write_solid_png(path, 8, 8, (26, 26, 26))
        return path

    def _arm_next_button(self) -> None:
        """Require a new press before Next can advance the trial."""
        if hasattr(self.next_button, "reset"):
            self.next_button.reset()
        # A mouse button still held down from the previous trial must be
        # released before Next can fire. A new press is accepted immediately;
        # the debounce window applies only after a click that was counted.
        self._button_was_down = self._next_button_is_down()
        self._last_click_time = float(self._core.getTime()) - self._config.BUTTON_DEBOUNCE_SEC

    def _next_button_is_down(self) -> bool:
        button = self.next_button
        if hasattr(button, "buttonSelected"):
            return bool(button.buttonSelected)
        return bool(button.isClicked)

    def _aspect_ratio(self) -> float:
        width, height = self._current_size()
        if height <= 0:
            return 1.0
        return float(width) / float(height)

    def _flip(self) -> None:
        if self._closed or self.win is None:
            raise RuntimeError("The PsychoPy window is already closed.")
        self.win.flip()

    def _release_escape_from_psychopy_quit(self) -> None:
        """Stop PsychoPy from quitting the window when Escape is pressed.

        A default install binds Escape to ``core.quit()``. Participants do
        not end the session. The operator stops it from the session page.
        """
        removed = False
        for kwargs in ({"name": "shutdown"}, {"key": "escape"}):
            try:
                self._event.globalKeys.remove(**kwargs)
                removed = True
            except Exception:
                continue
        if removed:
            self._logger.debug("Disabled PsychoPy's built-in Escape quit handler.")


def _load_psychopy() -> Tuple[Any, Any, Any, Any]:
    try:
        from psychopy import core, event, visual
        from psychopy.hardware import keyboard
    except ImportError as exc:
        raise ImportError(
            "PsychoPy is required to open the experiment window. "
            "From neuro_se_experiment/, install dependencies with: "
            "pip install -r requirements.txt"
        ) from exc
    return core, event, visual, keyboard


def _quiet_psychopy_console() -> None:
    """Keep PsychoPy's per-frame logs out of the experiment console."""
    try:
        from psychopy import logging as psychopy_logging

        psychopy_logging.console.setLevel(psychopy_logging.WARNING)
    except Exception:
        logging.getLogger("neuro_se.ui").debug(
            "Could not adjust PsychoPy console logging.",
            exc_info=True,
        )
