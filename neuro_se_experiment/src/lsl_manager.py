"""Lab Streaming Layer markers for EEG and eye-tracker alignment."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Optional


class Marker(str, Enum):
    """Fixed marker names. Dynamic task-onset markers are built separately."""

    EXP_START = "experiment_start"
    EXP_END = "experiment_end"
    TASK_END = "task_end"
    USER_TYPING = "user_keystroke"


def task_start_marker(task_id: str, condition: str) -> str:
    """Build the onset marker for one stimulus."""
    return f"task_start_{task_id}_{condition}"


class LSLManager:
    """Pushes string markers to an LSL outlet, or logs them when LSL is off.

    The outlet is created without waiting for a consumer. LabRecorder can
    connect after the process is already running; ``push_sample`` buffers
    samples until then instead of blocking the participant.
    """

    def __init__(self, enable_lsl: bool, logger: logging.Logger) -> None:
        self._enabled = enable_lsl
        self._logger = logger.getChild("lsl")
        self._outlet: Optional[Any] = None
        if enable_lsl:
            self._outlet = self._open_outlet()
            self._logger.info("LSL outlet ready: NeuroSE_Markers")
        else:
            self._logger.info("LSL disabled. Markers will be logged and not streamed.")

    def push_marker(self, marker: str) -> None:
        """Send one marker sample, or log a stub line when LSL is off."""
        if not self._enabled or self._outlet is None:
            # Keystroke markers fire on every press. Keep those off the
            # console; onset and offset markers stay visible.
            log = self._logger.debug if marker == Marker.USER_TYPING.value else self._logger.info
            log("[LSL-STUB] -> %s", marker)
            return
        try:
            self._outlet.push_sample([marker])
        except Exception:
            self._logger.exception("Failed to push LSL marker: %s", marker)
            raise
        if marker == Marker.USER_TYPING.value:
            self._logger.debug("LSL marker pushed: %s", marker)
        else:
            self._logger.info("LSL marker pushed: %s", marker)

    @staticmethod
    def _open_outlet() -> Any:
        try:
            from pylsl import IRREGULAR_RATE, StreamInfo, StreamOutlet, cf_string
        except ImportError as exc:
            raise ImportError(
                "ENABLE_LSL is True but pylsl is not installed. "
                "Install it with 'pip install pylsl', or set ENABLE_LSL = False "
                "in core/config.py to run the behavioral task without hardware."
            ) from exc

        info = StreamInfo(
            name="NeuroSE_Markers",
            type="Markers",
            channel_count=1,
            nominal_srate=IRREGULAR_RATE,
            channel_format=cf_string,
            source_id="neuro_se_exp_1",
        )
        return StreamOutlet(info)
