"""Stimulus loading and flat-file persistence of behavioral telemetry."""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core.config import ExperimentConfig
from src.stimulus_format import (
    format_optional_bool,
    label_matches_origin,
    parse_reported_lines,
    score_bug_lines,
    source_lines,
)

CSV_COLUMNS: List[str] = [
    "session_id",
    "task_id",
    "set_id",
    "origin",
    "difficulty",
    "language",
    "show_label",
    "label_text",
    "label_matches_origin",
    "has_bug",
    "bug_lines",
    "stimulus_type",
    "line_style",
    "condition",
    "final_input",
    "reported_lines",
    "hit_count",
    "false_alarm_count",
    "miss_count",
    "total_duration_sec",
    "keystroke_log",
]

PARTICIPANT_COLUMNS: List[str] = [
    "session_id",
    "role",
    "experience_years",
    "language_experience",
]


@dataclass(frozen=True)
class TaskPayload:
    """One code stimulus.

    ``origin`` is the true source. ``label_text`` is the badge the
    participant may see, and it is allowed to disagree with ``origin``.
    ``bug_lines`` is ground truth and is never drawn.
    """

    task_id: str
    set_id: str
    origin: str
    difficulty: str
    language: str
    show_label: bool
    label_text: str
    has_bug: bool
    bug_lines: Tuple[int, ...]
    stimulus_type: str
    image_path: str
    code_text: str
    condition: str


@dataclass(frozen=True)
class TrialResult:
    """Behavioral record for a single code trial.

    ``keystroke_log`` entries are dicts with ``key_name``, ``rt``, and
    ``duration``. ``rt`` is seconds from stimulus onset. There is no
    deadline: ``total_duration_sec`` is however long the participant took.
    """

    session_id: str
    task_id: str
    final_input: str
    total_duration_sec: float
    keystroke_log: List[Dict[str, Any]]
    line_style: str


@dataclass(frozen=True)
class ParticipantIntake:
    """Background collected before the first code trial."""

    session_id: str
    role: str
    experience_years: str
    language_experience: str


class DataManager:
    """Reads the task payload and appends trial rows to a CSV file."""

    def __init__(self, config: ExperimentConfig, logger: logging.Logger) -> None:
        self._config = config
        self._logger = logger.getChild("data")
        self._tasks_path = config.resolve_path(config.TASKS_FILE)
        self._output_dir = config.resolve_path(config.DATA_OUT_DIR)
        self._trials_path = self._output_dir / config.TRIALS_FILENAME
        self._participants_path = self._output_dir / config.PARTICIPANTS_FILENAME

    @property
    def trials_path(self) -> Path:
        return self._trials_path

    @property
    def participants_path(self) -> Path:
        return self._participants_path

    def load_tasks(self) -> List[TaskPayload]:
        """Parse ``tasks.json`` into typed payloads.

        Raises:
            FileNotFoundError: The tasks file does not exist.
            ValueError: The JSON is malformed or a task contradicts itself.
        """
        if not self._tasks_path.is_file():
            raise FileNotFoundError(f"Tasks file not found: {self._tasks_path}")

        try:
            payload = json.loads(self._tasks_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Tasks file is not valid JSON: {self._tasks_path}") from exc

        if not isinstance(payload, list):
            raise ValueError("Tasks file must contain a JSON list of task objects.")

        tasks = [self._parse_task(index, item) for index, item in enumerate(payload)]
        if not tasks:
            raise ValueError(f"Tasks file contains no tasks: {self._tasks_path}")

        labeled = sum(1 for task in tasks if task.show_label)
        mismatched = sum(
            1
            for task in tasks
            if label_matches_origin(task.origin, task.label_text, task.show_label) is False
        )
        self._logger.info(
            "Loaded %d task(s) from %s (bugs=%d, labels=%d, mismatched_labels=%d, images=%d).",
            len(tasks),
            self._tasks_path,
            sum(1 for task in tasks if task.has_bug),
            labeled,
            mismatched,
            sum(1 for task in tasks if task.stimulus_type == "image"),
        )
        return tasks

    def save_participant(self, intake: ParticipantIntake) -> None:
        """Append the pre-task questionnaire row."""
        self._append_row(
            self._participants_path,
            PARTICIPANT_COLUMNS,
            {
                "session_id": intake.session_id,
                "role": intake.role,
                "experience_years": intake.experience_years,
                "language_experience": intake.language_experience,
            },
        )
        self._logger.info("Saved intake for session %s", intake.session_id)

    def save_trial_result(self, result: TrialResult, task: TaskPayload) -> None:
        """Append one trial. Keystrokes stay nested JSON inside one CSV cell."""
        reported = parse_reported_lines(result.final_input)
        hits, false_alarms, misses = score_bug_lines(reported, task.bug_lines)
        matches = label_matches_origin(task.origin, task.label_text, task.show_label)
        self._append_row(
            self._trials_path,
            CSV_COLUMNS,
            {
                "session_id": result.session_id,
                "task_id": result.task_id,
                "set_id": task.set_id,
                "origin": task.origin,
                "difficulty": task.difficulty,
                "language": task.language,
                "show_label": "true" if task.show_label else "false",
                "label_text": task.label_text,
                "label_matches_origin": format_optional_bool(matches),
                "has_bug": "true" if task.has_bug else "false",
                "bug_lines": json.dumps(list(task.bug_lines)),
                "stimulus_type": task.stimulus_type,
                "line_style": result.line_style,
                "condition": task.condition,
                "final_input": result.final_input,
                "reported_lines": json.dumps(reported),
                "hit_count": hits,
                "false_alarm_count": false_alarms,
                "miss_count": misses,
                "total_duration_sec": result.total_duration_sec,
                "keystroke_log": json.dumps(result.keystroke_log, ensure_ascii=False),
            },
        )
        self._logger.info(
            "Saved trial %s (%s): hits=%d false_alarms=%d misses=%d duration=%.3fs",
            result.task_id,
            result.session_id,
            hits,
            false_alarms,
            misses,
            result.total_duration_sec,
        )

    def _append_row(self, path: Path, columns: List[str], row: Dict[str, Any]) -> None:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        write_header = (not path.exists()) or path.stat().st_size == 0
        try:
            with path.open("a", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=columns)
                if write_header:
                    writer.writeheader()
                writer.writerow(row)
        except OSError:
            self._logger.exception("Failed to write %s", path)
            raise

    def _parse_task(self, index: int, item: Any) -> TaskPayload:
        if not isinstance(item, dict):
            raise ValueError(f"Task at index {index} must be a JSON object.")
        if "task_id" not in item:
            raise ValueError(f"Task at index {index} is missing task_id.")
        if "code_text" not in item:
            raise ValueError(f"Task at index {index} is missing code_text.")

        new_schema = any(key in item for key in ("origin", "has_bug", "bug_lines", "stimulus_type"))
        origin = str(item.get("origin", item.get("condition", "unspecified")))
        bug_lines = _parse_bug_lines(index, item.get("bug_lines", []))
        if "has_bug" in item:
            has_bug = bool(item["has_bug"])
        elif new_schema:
            has_bug = bool(bug_lines)
        else:
            has_bug = True

        if new_schema and has_bug and not bug_lines:
            raise ValueError(f"Task at index {index} is marked with a bug but bug_lines is empty.")
        if new_schema and not has_bug and bug_lines:
            raise ValueError(f"Task at index {index} is clean but bug_lines is not empty.")

        code_text = str(item["code_text"])
        line_count = len(source_lines(code_text))
        for line_number in bug_lines:
            if line_number < 1 or line_number > line_count:
                raise ValueError(
                    f"Task at index {index} bug line {line_number} is outside 1..{line_count}."
                )
        if line_count > self._config.MAX_CODE_LINES:
            self._logger.warning(
                "Task %s has %d lines. The screen limit is %d, and there is no scrolling.",
                item["task_id"],
                line_count,
                self._config.MAX_CODE_LINES,
            )

        stimulus_type = str(item.get("stimulus_type", "text"))
        if stimulus_type not in ("image", "text"):
            raise ValueError(
                f"Task at index {index} stimulus_type must be 'image' or 'text'."
            )
        image_path = str(item.get("image_path", ""))
        if stimulus_type == "image" and not image_path:
            raise ValueError(f"Task at index {index} is an image trial without image_path.")
        if stimulus_type == "image":
            resolved = self._config.resolve_path(image_path)
            if not resolved.is_file():
                self._logger.warning(
                    "Image for %s is missing (%s). The trial will fall back to numbered text.",
                    item["task_id"],
                    resolved,
                )

        show_label = bool(item.get("show_label", False))
        label_text = str(item.get("label_text", ""))
        difficulty = str(item.get("difficulty", "unspecified"))
        set_id = str(item.get("set_id", ""))
        language = str(item.get("language", "python"))
        condition = str(
            item.get(
                "condition",
                f"{origin}|{difficulty}|label:{int(show_label)}|bug:{int(has_bug)}",
            )
        )
        return TaskPayload(
            task_id=str(item["task_id"]),
            set_id=set_id,
            origin=origin,
            difficulty=difficulty,
            language=language,
            show_label=show_label,
            label_text=label_text,
            has_bug=has_bug,
            bug_lines=tuple(bug_lines),
            stimulus_type=stimulus_type,
            image_path=image_path,
            code_text=code_text,
            condition=condition,
        )


def _parse_bug_lines(index: int, raw: Any) -> List[int]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"Task at index {index} bug_lines must be a list of integers.")
    lines: List[int] = []
    for entry in raw:
        if isinstance(entry, bool) or not isinstance(entry, int):
            raise ValueError(f"Task at index {index} bug_lines must be a list of integers.")
        lines.append(entry)
    return lines
