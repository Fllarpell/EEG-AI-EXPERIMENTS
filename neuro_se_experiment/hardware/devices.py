"""Swappable EEG and eye-tracker readers.

Dummy readers publish LSL streams and write the same kind of files the live
blocks write, so LabRecorder can be tested before the amp and the tracker
are in the room. Live readers are the RDA thread and the EyeLink calls from
the image-reconstruction experiment.
"""

from __future__ import annotations

import json
import logging
import math
import threading
import time
from pathlib import Path
from typing import List, Optional, Sequence


EEG_CHANNELS: List[str] = [
    "Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4", "O1", "O2",
]
EEG_SAMPLE_RATE = 250.0
GAZE_SAMPLE_RATE = 60.0


class DeviceSession:
    """What the experiment loop is allowed to call."""

    def prepare(self) -> None:
        """Connect and, for a tracker, calibrate. Must not record yet."""

    def start(self) -> None:
        """Begin writing samples."""

    def stop(self) -> None:
        """Stop writing and close the device. A second call is safe."""


def open_eeg(
    use_dummy: bool,
    enable_lsl: bool,
    output_dir: Path,
    host: str,
    port: int,
    logger: logging.Logger,
) -> DeviceSession:
    if use_dummy:
        return DummyEEG(output_dir, enable_lsl, logger)
    return LiveRDA(host, port, output_dir, logger)


def open_eyetracker(
    use_dummy: bool,
    enable_lsl: bool,
    output_dir: Path,
    host: str,
    edf_name: str,
    screen_size: Sequence[int],
    logger: logging.Logger,
) -> DeviceSession:
    if use_dummy:
        return DummyEyeTracker(output_dir, enable_lsl, screen_size, logger)
    return LiveEyeLink(host, edf_name, output_dir, logger)


class DummyEEG(DeviceSession):
    """Synthetic EEG with the same start/stop lifecycle as the RDA thread.

    Files match the RDA writer closely enough to open later:
    datablocks.csv, properties.json, markers.csv.
    """

    def __init__(self, output_dir: Path, enable_lsl: bool, logger: logging.Logger) -> None:
        self._dir = output_dir
        self._enable_lsl = enable_lsl
        self._logger = logger.getChild("eeg")
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._outlet: Optional[object] = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._dir.mkdir(parents=True, exist_ok=True)
        self._write_properties()
        self._outlet = _lsl_outlet(
            self._enable_lsl,
            name="NeuroSE_EEG",
            stream_type="EEG",
            channel_count=len(EEG_CHANNELS),
            sample_rate=EEG_SAMPLE_RATE,
            source_id="neuro_se_eeg_dummy",
            channel_names=EEG_CHANNELS,
            logger=self._logger,
        )
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="dummy-eeg", daemon=True)
        self._thread.start()
        self._logger.info("[EEG-DUMMY] recording %d Hz -> %s", int(EEG_SAMPLE_RATE), self._dir)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._outlet = None
        self._logger.info("[EEG-DUMMY] stopped")

    def _write_properties(self) -> None:
        payload = {
            "sampling_interval": 1_000_000.0 / EEG_SAMPLE_RATE,
            "resolutions": [0.1] * len(EEG_CHANNELS),
            "channel_names": EEG_CHANNELS,
        }
        (self._dir / "properties.json").write_text(json.dumps(payload), encoding="utf-8")
        (self._dir / "markers.csv").write_text("", encoding="utf-8")

    def _run(self) -> None:
        path = self._dir / "datablocks.csv"
        period = 1.0 / EEG_SAMPLE_RATE
        next_tick = time.perf_counter()
        sample_index = 0
        block_id = 1
        with path.open("w", encoding="utf-8") as handle:
            while not self._stop.is_set():
                timestamp = time.time()
                sample = _eeg_sample(sample_index, period)
                channels = ",".join(f"{value:.4f}" for value in sample)
                handle.write(f"{block_id},{timestamp},{channels};\n")
                if self._outlet is not None:
                    self._outlet.push_sample(sample)
                sample_index += 1
                if sample_index % EEG_SAMPLE_RATE == 0:
                    block_id += 1
                    handle.flush()
                next_tick += period
                delay = next_tick - time.perf_counter()
                if delay > 0:
                    self._stop.wait(delay)
                else:
                    next_tick = time.perf_counter()


class LiveRDA(DeviceSession):
    """The BrainVision RDA thread from the image-reconstruction experiment."""

    def __init__(self, host: str, port: int, output_dir: Path, logger: logging.Logger) -> None:
        self._host = host
        self._port = port
        self._dir = output_dir
        self._logger = logger.getChild("eeg")
        self._rda: Optional[object] = None

    def start(self) -> None:
        from hardware.rda_client import run_rda_thread

        self._dir.mkdir(parents=True, exist_ok=True)
        self._logger.info("[EEG-RDA] connecting %s:%s -> %s", self._host, self._port, self._dir)
        self._rda = run_rda_thread(self._host, self._port, self._dir, self._logger)

    def stop(self) -> None:
        if self._rda is not None:
            self._rda.stop_thread()
            self._rda = None
        self._logger.info("[EEG-RDA] stopped")


class DummyEyeTracker(DeviceSession):
    """Gaze samples with the same start/stop shape as the EyeLink block.

    The live tracker writes an EDF on the host PC. The dummy writes
    gaze.csv (time, x, y, pupil) and, when LSL is on, a Gaze stream.
    """

    def __init__(
        self,
        output_dir: Path,
        enable_lsl: bool,
        screen_size: Sequence[int],
        logger: logging.Logger,
    ) -> None:
        self._dir = output_dir
        self._enable_lsl = enable_lsl
        self._width = float(screen_size[0])
        self._height = float(screen_size[1])
        self._logger = logger.getChild("gaze")
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._outlet: Optional[object] = None

    def prepare(self) -> None:
        self._logger.info("[GAZE-DUMMY] calibration skipped")

    def start(self) -> None:
        if self._thread is not None:
            return
        self._dir.mkdir(parents=True, exist_ok=True)
        self._outlet = _lsl_outlet(
            self._enable_lsl,
            name="NeuroSE_Gaze",
            stream_type="Gaze",
            channel_count=3,
            sample_rate=GAZE_SAMPLE_RATE,
            source_id="neuro_se_gaze_dummy",
            channel_names=["x", "y", "pupil"],
            logger=self._logger,
        )
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="dummy-gaze", daemon=True)
        self._thread.start()
        self._logger.info("[GAZE-DUMMY] recording %.0f Hz -> %s", GAZE_SAMPLE_RATE, self._dir)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._outlet = None
        self._logger.info("[GAZE-DUMMY] stopped")

    def _run(self) -> None:
        path = self._dir / "gaze.csv"
        period = 1.0 / GAZE_SAMPLE_RATE
        next_tick = time.perf_counter()
        step = 0
        with path.open("w", encoding="utf-8") as handle:
            handle.write("timestamp,x,y,pupil\n")
            while not self._stop.is_set():
                x_pos, y_pos, pupil = _gaze_sample(step, self._width, self._height)
                timestamp = time.time()
                handle.write(f"{timestamp:.6f},{x_pos:.2f},{y_pos:.2f},{pupil:.2f}\n")
                if self._outlet is not None:
                    self._outlet.push_sample([x_pos, y_pos, pupil])
                step += 1
                if step % int(GAZE_SAMPLE_RATE) == 0:
                    handle.flush()
                next_tick += period
                delay = next_tick - time.perf_counter()
                if delay > 0:
                    self._stop.wait(delay)
                else:
                    next_tick = time.perf_counter()


class LiveEyeLink(DeviceSession):
    """EyeLink calls copied from Main.eyelink_* in the source experiment.

    The tracker only accepts an 8-character file name. The full session id is
    written in the log; the EDF itself uses the last six digits.
    """

    def __init__(self, host: str, edf_name: str, output_dir: Path, logger: logging.Logger) -> None:
        self._host = host
        self._dir = output_dir
        self._stem = _eyelink_stem(edf_name)
        self._tracker_file = f"{self._stem}.edf"
        self._local_file = output_dir / self._tracker_file
        self._logger = logger.getChild("gaze")
        self._eyelink: Optional[object] = None
        self._recording = False

    def prepare(self) -> None:
        try:
            import pylink
        except ImportError as exc:
            raise ImportError(
                "Живой айтрекер включён, а библиотеки pylink нет. "
                "Нужен SR Research EyeLink Developers Kit, либо оставьте заглушку айтрекера."
            ) from exc
        self._logger.info("[EYELINK] connecting %s", self._host)
        self._logger.info(
            "[EYELINK] session file %s on the tracker, local copy %s",
            self._tracker_file,
            self._local_file,
        )
        self._eyelink = pylink.EyeLink(self._host)
        self._eyelink.setFileEventFilter("LEFT,RIGHT,FIXATION,SACCADE,BLINK,MESSAGE,BUTTON")
        self._eyelink.setFileSampleFilter("LEFT,RIGHT,GAZE,AREA,GAZERES,STATUS,HTARGET")
        self._eyelink.setLinkEventFilter("LEFT,RIGHT,FIXATION,SACCADE,BLINK,MESSAGE,BUTTON")
        self._eyelink.setLinkSampleFilter("LEFT,RIGHT,GAZE,GAZERES,AREA,STATUS,HTARGET")
        self._logger.info(
            "[EYELINK] opening camera setup and calibration. "
            "C calibrates, V validates, Escape leaves the setup screen."
        )
        for handler in logging.getLogger("neuro_se").handlers:
            handler.flush()
        pylink.openGraphics()
        try:
            self._eyelink.doTrackerSetup()
        finally:
            pylink.closeGraphics()
        self._logger.info("[EYELINK] setup screens closed")

    def start(self) -> None:
        if self._eyelink is None:
            raise RuntimeError("EyeLink.prepare() was not called.")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._logger.info("[EYELINK] openDataFile %s", self._tracker_file)
        self._eyelink.openDataFile(self._tracker_file)
        self._eyelink.startRecording(1, 1, 1, 1)
        self._recording = True
        self._logger.info("[EYELINK] recording file, link, events and samples")

    def stop(self) -> None:
        if self._eyelink is None:
            return
        try:
            if self._recording:
                self._eyelink.stopRecording()
                self._eyelink.closeDataFile()
                self._dir.mkdir(parents=True, exist_ok=True)
                received = self._eyelink.receiveDataFile(self._tracker_file, str(self._local_file))
                size = self._local_file.stat().st_size if self._local_file.is_file() else 0
                self._logger.info(
                    "[EYELINK] received %s bytes, saved %s (%d bytes)",
                    received,
                    self._local_file,
                    size,
                )
        finally:
            self._eyelink.close()
            self._eyelink = None
            self._recording = False
            self._logger.info("[EYELINK] connection closed")


def _eyelink_stem(session_id: str) -> str:
    """Eight characters or fewer. EyeLink rejects a longer data-file name."""
    digits = "".join(char for char in session_id if char.isdigit())
    stem = digits[-6:] if digits else "gaze"
    return stem[:8]


def _eeg_sample(index: int, period: float) -> List[float]:
    """A 10 Hz rhythm plus a little noise, in microvolts, one value per channel."""
    t = index * period
    sample: List[float] = []
    for channel_index in range(len(EEG_CHANNELS)):
        phase = channel_index * 0.4
        alpha = 12.0 * math.sin(2.0 * math.pi * 10.0 * t + phase)
        drift = 2.0 * math.sin(2.0 * math.pi * 0.2 * t + phase)
        sample.append(alpha + drift)
    return sample


def _gaze_sample(step: int, width: float, height: float) -> tuple:
    """A slow sweep across the code area, in screen pixels, plus a pupil size."""
    phase = step / GAZE_SAMPLE_RATE
    x_pos = width * (0.35 + 0.30 * math.sin(2.0 * math.pi * 0.15 * phase))
    y_pos = height * (0.30 + 0.15 * math.sin(2.0 * math.pi * 0.07 * phase))
    pupil = 800.0 + 40.0 * math.sin(2.0 * math.pi * 0.3 * phase)
    return x_pos, y_pos, pupil


def _lsl_outlet(
    enabled: bool,
    name: str,
    stream_type: str,
    channel_count: int,
    sample_rate: float,
    source_id: str,
    channel_names: Sequence[str],
    logger: logging.Logger,
) -> Optional[object]:
    if not enabled:
        return None
    try:
        from pylsl import StreamInfo, StreamOutlet, cf_float32
    except ImportError:
        logger.error("pylsl is missing, %s will be written to disk only.", name)
        return None
    info = StreamInfo(name, stream_type, channel_count, sample_rate, cf_float32, source_id)
    channels = info.desc().append_child("channels")
    for channel_name in channel_names:
        channels.append_child("channel").append_child_value("label", channel_name)
    logger.info("LSL outlet ready: %s", name)
    return StreamOutlet(info)
