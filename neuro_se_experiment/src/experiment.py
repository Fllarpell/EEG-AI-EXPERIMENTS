"""Session state machine. Wires config, data, UI, and LSL together."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from core.config import ExperimentConfig
from core.logger import setup_logger
from hardware.devices import DeviceSession, open_eeg, open_eyetracker
from src.data_manager import DataManager, TaskPayload, TrialResult
from src.lsl_manager import LSLManager, Marker, task_start_marker
from src.stimulus_format import displayed_label
from src.ui_manager import UIManager


class ExperimentAborted(Exception):
    """The session stopped before the last trial. The window must still close."""


class ExperimentRunner:
    """Runs one participant session.

    Managers can be injected. When they are omitted, the runner builds them
    from ``ExperimentConfig``, which is what ``main.py`` does.
    """

    def __init__(
        self,
        config: ExperimentConfig,
        data_manager: Optional[DataManager] = None,
        ui_manager: Optional[UIManager] = None,
        lsl_manager: Optional[LSLManager] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._config = config
        self._logger = logger or setup_logger(
            "neuro_se",
            config.resolve_path(config.DATA_OUT_DIR),
        )
        self._started = False
        self._shutdown_done = False
        self._line_style = config.LINE_STYLE
        self._tasks_stamp = -1.0
        self._eeg: Optional[DeviceSession] = None
        self._gaze: Optional[DeviceSession] = None
        self.data_manager = data_manager or DataManager(config, self._logger)
        self.lsl_manager = lsl_manager or LSLManager(config.ENABLE_LSL, self._logger)
        # The task window waits until EyeLink setup is finished. Camera image
        # and calibration targets need the display to themselves.
        self.ui_manager = ui_manager

    def run(self) -> None:
        """Show the instructions, present every task, then close the window."""
        try:
            self._run_session()
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        """Push the end marker once and close the window.

        Safe to call more than once. ``main.py`` calls it again from
        ``finally`` so a failure inside ``run`` cannot leave a fullscreen
        window open.
        """
        if self._shutdown_done:
            return
        self._shutdown_done = True
        for device in (self._eeg, self._gaze):
            if device is None:
                continue
            try:
                device.stop()
            except Exception:
                self._logger.exception("Failed to stop a hardware reader.")
        try:
            if self._started and self.lsl_manager is not None:
                self.lsl_manager.push_marker(Marker.EXP_END.value)
        except Exception:
            self._logger.exception("Failed to push the experiment_end marker.")
        finally:
            if self.ui_manager is not None:
                self.ui_manager.close()

    def _run_session(self) -> None:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        data_dir = self._config.resolve_path(self._config.DATA_OUT_DIR)
        hardware_dir = data_dir / "hardware" / session_id
        self._logger.info("Session %s starting.", session_id)
        self._logger.info(
            "EEG: %s -> %s",
            "заглушка" if self._config.USE_DUMMY_EEG else f"RDA {self._config.EEG_HOST}:{self._config.EEG_PORT}",
            hardware_dir / "eeg",
        )
        self._logger.info(
            "Gaze: %s -> %s",
            "заглушка" if self._config.USE_DUMMY_EYETRACKER else f"EyeLink {self._config.EYELINK_HOST}",
            hardware_dir / "gaze",
        )
        self._logger.info("Журнал: %s", data_dir / "experiment.log")
        self._logger.info("Ответы: %s", data_dir / self._config.TRIALS_FILENAME)
        tasks = self.data_manager.load_tasks()
        self._eeg = open_eeg(
            use_dummy=self._config.USE_DUMMY_EEG,
            enable_lsl=self._config.ENABLE_LSL,
            output_dir=hardware_dir / "eeg",
            host=self._config.EEG_HOST,
            port=self._config.EEG_PORT,
            logger=self._logger,
        )
        self._gaze = open_eyetracker(
            use_dummy=self._config.USE_DUMMY_EYETRACKER,
            enable_lsl=self._config.ENABLE_LSL,
            output_dir=hardware_dir / "gaze",
            host=self._config.EYELINK_HOST,
            edf_name=session_id,
            screen_size=self._config.WINDOW_SIZE,
            logger=self._logger,
        )
        self._gaze.prepare()
        if self.ui_manager is None:
            self.ui_manager = UIManager(self._config, self._logger)
        self._tasks_stamp = self._tasks_mtime()
        self._wait_for_start(session_id, len(tasks))
        self._eeg.start()
        self._gaze.start()
        self.lsl_manager.push_marker(Marker.EXP_START.value)
        self._started = True
        self.ui_manager.set_line_style(self._line_style)
        completed: list[str] = []
        while True:
            latest = self._reload_tasks()
            if latest is not None:
                tasks = latest
            remaining = [task for task in tasks if task.task_id not in completed]
            if not remaining:
                break
            task = remaining[0]
            index = len(completed) + 1
            total = len(completed) + len(remaining)
            self._logger.info("Trial %d/%d: %s", index, total, task.task_id)
            self._run_trial(session_id, task, len(remaining) == 1, index, total)
            completed.append(task.task_id)
        self._logger.info("Session %s complete.", session_id)

    def _wait_for_start(self, session_id: str, task_count: int) -> None:
        from psychopy import event

        self._show_start_screen(task_count)
        self.ui_manager.clear_keyboard_buffer()
        while True:
            self.ui_manager.draw_wait_frame()
            task_count = self._live_task_count(task_count)
            names = self.ui_manager.read_key_names()
            event.clearEvents()
            if "space" in names:
                self._logger.info(
                    "Operator started session %s (%s).",
                    session_id,
                    self._line_style,
                )
                return

    def _show_start_screen(self, task_count: int) -> None:
        message = (
            f"{self._config.INSTRUCTION_TEXT}\n\n"
            f"Заданий: {task_count}."
        )
        self.ui_manager.show_wait_screen(message)

    def _run_trial(
        self,
        session_id: str,
        task: TaskPayload,
        is_last: bool,
        index: int,
        total: int,
    ) -> None:
        from psychopy import core

        image_path = None
        if task.image_path:
            image_path = self._config.resolve_path(task.image_path)
        button_text = self._config.FINISH_BUTTON_TEXT if is_last else self._config.BUTTON_TEXT
        self.ui_manager.set_line_style(self._line_style)
        self.ui_manager.set_progress(index, total)
        self.ui_manager.prepare_task_screen(
            code_text=task.code_text,
            stimulus_type=task.stimulus_type,
            image_path=image_path,
            show_label=True,
            label_text=displayed_label(task.origin, task.label_text),
            button_text=button_text,
        )
        # Flip once so TASK_START marks visual onset, not the previous frame.
        # The behavioral clock starts on that same onset. The loop has no
        # deadline: only Next ends the trial. The operator stops the process
        # from the session page.
        self.ui_manager.draw()
        self.lsl_manager.push_marker(task_start_marker(task.task_id, task.origin))
        trial_clock = core.Clock()
        self.ui_manager.sync_keyboard_clock(trial_clock)
        self.ui_manager.clear_keyboard_buffer()
        self._tasks_stamp = self._tasks_mtime()

        while True:
            self.ui_manager.draw()
            task = self._sync_open_task(task, index, total, is_last)
            new_keys = self.ui_manager.poll_keystrokes()
            for _key in new_keys:
                self.lsl_manager.push_marker(Marker.USER_TYPING.value)
            if self.ui_manager.check_next_clicked():
                self.lsl_manager.push_marker(Marker.TASK_END.value)
                result = TrialResult(
                    session_id=session_id,
                    task_id=task.task_id,
                    final_input=self.ui_manager.get_user_input(),
                    total_duration_sec=float(trial_clock.getTime()),
                    keystroke_log=self.ui_manager.collect_keystroke_log(),
                    line_style=self._line_style,
                )
                self.data_manager.save_trial_result(result, task)
                break

    def _tasks_path(self):
        return self._config.resolve_path(self._config.TASKS_FILE)

    def _tasks_mtime(self) -> float:
        try:
            return self._tasks_path().stat().st_mtime
        except OSError:
            return -1.0

    def _reload_tasks(self):
        """Read tasks.json. A half-written edit keeps the list already on screen."""
        try:
            return self.data_manager.load_tasks()
        except Exception:
            self._logger.warning("tasks.json is not ready. The open task stays as it is.")
            return None

    def _live_task_count(self, task_count: int) -> int:
        stamp = self._tasks_mtime()
        if stamp == self._tasks_stamp:
            return task_count
        self._tasks_stamp = stamp
        loaded = self._reload_tasks()
        if loaded is None or len(loaded) == task_count:
            return task_count
        self._show_start_screen(len(loaded))
        return len(loaded)

    def _sync_open_task(
        self,
        task: TaskPayload,
        index: int,
        total: int,
        is_last: bool,
    ) -> TaskPayload:
        """If the editor saved this task, redraw it without clearing the answer."""
        stamp = self._tasks_mtime()
        if stamp == self._tasks_stamp:
            return task
        self._tasks_stamp = stamp
        loaded = self._reload_tasks()
        if not loaded:
            return task
        fresh = next((item for item in loaded if item.task_id == task.task_id), None)
        if fresh is None:
            return task
        self.ui_manager.set_progress(index, max(total, len(loaded)))
        changed = (
            fresh.code_text,
            fresh.stimulus_type,
            fresh.image_path,
            fresh.origin,
            fresh.label_text,
        ) != (
            task.code_text,
            task.stimulus_type,
            task.image_path,
            task.origin,
            task.label_text,
        )
        if changed:
            image_path = self._config.resolve_path(fresh.image_path) if fresh.image_path else None
            button_text = self._config.FINISH_BUTTON_TEXT if is_last else self._config.BUTTON_TEXT
            self.ui_manager.update_task_content(
                code_text=fresh.code_text,
                stimulus_type=fresh.stimulus_type,
                image_path=image_path,
                show_label=True,
                label_text=displayed_label(fresh.origin, fresh.label_text),
                button_text=button_text,
            )
            self._logger.info("Updated open task %s from the editor.", fresh.task_id)
        return fresh
