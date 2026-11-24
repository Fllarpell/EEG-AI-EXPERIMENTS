"""Strict, code-defined settings for the Neuro-SE experiment.

Every color, timing, path, and hardware flag lives here so the experiment
loop and the managers stay free of magic numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class ExperimentConfig:
    """Immutable experiment settings.

    ``BG_COLOR`` is a dark neutral gray in PsychoPy's rgb space (-1..1).
    A mid-gray field keeps the pupillary light reflex from contaminating
    eye-tracking and EEG when the window opens.
    """

    # Lab monitors are 1920x1080. This Mac's desktop is 1470x956 points,
    # so the demo window stays inside the screen and the answer button remains visible.
    # Short enough to sit above a Mac dock. The window can still be resized,
    # and the operator can open it fullscreen.
    WINDOW_SIZE: Tuple[int, int] = (1280, 740)
    FULLSCREEN: bool = False
    BG_COLOR: Tuple[float, float, float] = (-0.8, -0.8, -0.8)
    # Markers, dummy EEG and dummy gaze all go out through LSL.
    # LabRecorder can connect while the window is already open.
    ENABLE_LSL: bool = True
    # Flip these off when the amp and the tracker are on the bench.
    # The live readers call the same start/stop blocks as the cloned
    # EEG-Experiment-Script (BrainVision RDA and EyeLink).
    USE_DUMMY_EEG: bool = True
    USE_DUMMY_EYETRACKER: bool = True
    EEG_HOST: str = "100.1.1.3"
    EEG_PORT: int = 51244
    EYELINK_HOST: str = "100.1.1.1"
    LINE_STYLE: str = "mono"
    CODE_PHOTOS_DIR: str = "assets/code_photos"
    DATA_OUT_DIR: str = "data/"
    TASKS_FILE: str = "assets/tasks.json"

    UNITS: str = "height"
    FONT_CODE: str = "Courier New"
    FONT_UI: str = "Arvo"
    CODE_COLOR: str = "white"
    CODE_LETTER_HEIGHT: float = 0.026
    # Achromatic gray. Yellow sits at the peak of the eye's brightness curve
    # and pulls a visual response that is not the task.
    PROMPT_COLOR: Tuple[float, float, float] = (0.62, 0.62, 0.62)
    PROMPT_TEXT: str = "В коде возможны баги. Введите номера строк через запятую:"
    PROMPT_LETTER_HEIGHT: float = 0.028
    INPUT_TEXT_COLOR: str = "black"
    INPUT_FILL_COLOR: str = "white"
    INPUT_PLACEHOLDER: str = "например 3, 7"
    BUTTON_TEXT: str = "Следующее задание"
    FINISH_BUTTON_TEXT: str = "Завершить"
    FORM_BUTTON_TEXT: str = "Далее"
    BUTTON_FILL_COLOR: Tuple[float, float, float] = (-0.2, -0.2, 0.1)
    BUTTON_TEXT_COLOR: str = "white"
    BADGE_FILL_COLOR: Tuple[float, float, float] = (-0.35, -0.28, -0.55)
    MARGIN: float = 0.04
    BUTTON_DEBOUNCE_SEC: float = 0.3
    MAX_CODE_LINES: int = 16
    TRIALS_FILENAME: str = "trials.csv"
    PARTICIPANTS_FILENAME: str = "participants.csv"
    INSTRUCTION_TEXT: str = (
        "В коде возможны баги.\n\n"
        "Введите номера строк через запятую.\n"
        "На части заданий над кодом есть подпись об источнике.\n\n"
        "Пробел — начать"
    )
    INTAKE_ROLE_PROMPT: str = "Кто вы?\nстудент, джуниор или мидл"
    INTAKE_EXPERIENCE_PROMPT: str = "Опыт работы, в годах.\nЕсли опыта нет, введите 0."
    INTAKE_LANGUAGE_PROMPT: str = (
        "Опыт в языке заданий.\nНапример: Python, 2 года, пишу уверенно."
    )

    def resolve_path(self, relative: str) -> Path:
        """Resolve a config path against the experiment package root."""
        candidate = Path(relative)
        if candidate.is_absolute():
            return candidate
        return PROJECT_ROOT / candidate
