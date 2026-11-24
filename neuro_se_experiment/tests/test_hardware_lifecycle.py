from __future__ import annotations

import asyncio
import io
import logging
from unittest.mock import Mock, patch

from core.config import ExperimentConfig
from hardware.devices import LiveEyeLink, LiveRDA
from hardware.rda_client import RDA
from main import _acquire_instance_lock
from src.experiment import ExperimentRunner


class _Data:
    def load_tasks(self):
        return []


class _UI:
    def __init__(self, calls):
        self._calls = calls

    def close(self):
        self._calls.append('ui.close')

    def set_line_style(self, line_style):
        self._calls.append(f'ui.style:{line_style}')


class _LSL:
    def __init__(self, calls):
        self._calls = calls

    def push_marker(self, marker):
        self._calls.append(f'marker:{marker}')


class _Device:
    def __init__(self, name, calls):
        self._name = name
        self._calls = calls

    def prepare(self):
        self._calls.append(f'{self._name}.prepare')

    def start(self):
        self._calls.append(f'{self._name}.start')

    def stop(self):
        self._calls.append(f'{self._name}.stop')


def _logger():
    stream = io.StringIO()
    logger = logging.getLogger(f'lifecycle-test-{id(stream)}')
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(logging.StreamHandler(stream))
    return logger, stream


def test_live_rda_prepares_before_recording(tmp_path):
    logger, _ = _logger()
    receiver = Mock()
    receiver.wait_until_ready = Mock()
    receiver.begin_recording = Mock()
    receiver.stop_thread = Mock()
    device = LiveRDA('100.1.1.3', 51244, tmp_path, logger)

    with patch('hardware.rda_client.run_rda_thread', return_value=receiver):
        device.prepare()
        receiver.wait_until_ready.assert_called_once_with()
        receiver.begin_recording.assert_not_called()
        device.start()
        receiver.begin_recording.assert_called_once_with()
        device.stop()
    receiver.stop_thread.assert_called_once_with()


def test_live_rda_timeout_keeps_background_receiver(tmp_path):
    logger, stream = _logger()
    receiver = Mock()
    receiver.wait_until_ready.side_effect = TimeoutError('properties pending')
    device = LiveRDA('100.1.1.3', 51244, tmp_path, logger)

    with patch('hardware.rda_client.run_rda_thread', return_value=receiver):
        device.prepare()
        receiver.stop_thread.assert_not_called()
        device.start()
        receiver.begin_recording.assert_called_once_with()
        device.stop()

    assert 'receiver remains active in the background' in stream.getvalue()


def test_rda_can_arm_recording_before_properties_arrive(tmp_path):
    logger, stream = _logger()
    rda = RDA('100.1.1.3', 51244, tmp_path, logger)

    rda.begin_recording()

    assert rda._recording.is_set()
    assert 'recording armed in the background' in stream.getvalue()


def test_eyelink_opens_calibration_with_explicit_display_mode(tmp_path):
    logger, _ = _logger()
    pylink = Mock()
    tracker = Mock()
    pylink.EyeLink.return_value = tracker
    device = LiveEyeLink(
        '100.1.1.1',
        '20261124_161637',
        tmp_path,
        (1280, 740),
        logger,
    )

    with patch('hardware.devices._load_pylink', return_value=pylink):
        device.prepare()

    pylink.openGraphics.assert_called_once_with((1280, 740), 32)
    tracker.doTrackerSetup.assert_called_once_with()
    pylink.closeGraphics.assert_called_once_with()


def test_rda_timeout_waits_for_receiver_cleanup(tmp_path):
    logger, _ = _logger()
    rda = RDA('100.1.1.3', 51244, tmp_path, logger)

    async def never_connect(*args, **kwargs):
        await asyncio.Event().wait()

    with patch('hardware.rda_client.asyncio.open_connection', side_effect=never_connect):
        rda.run_thread()
        try:
            rda.wait_until_ready(timeout=0.05)
        except TimeoutError:
            pass
        else:
            raise AssertionError('RDA setup unexpectedly became ready')
        rda.stop_thread()

    assert rda._receiver_done.is_set()
    assert rda.thread is not None
    assert not rda.thread.is_alive()


def test_only_one_experiment_process_can_hold_the_instance_lock():
    first = _acquire_instance_lock()
    try:
        try:
            _acquire_instance_lock()
        except Exception as exc:
            assert 'already running' in str(exc)
        else:
            raise AssertionError('a second experiment acquired the same lock')
    finally:
        first.close()


def test_runner_orders_setup_window_recording_and_shutdown(tmp_path):
    calls = []
    logger, stream = _logger()
    eeg = _Device('eeg', calls)
    gaze = _Device('gaze', calls)
    runner = ExperimentRunner(
        ExperimentConfig(
            ENABLE_LSL=False,
            USE_DUMMY_EEG=True,
            USE_DUMMY_EYETRACKER=True,
            DATA_OUT_DIR=str(tmp_path),
        ),
        data_manager=_Data(),
        ui_manager=_UI(calls),
        lsl_manager=_LSL(calls),
        logger=logger,
    )
    runner._wait_for_start = lambda session_id, task_count: None

    with (
        patch('src.experiment.open_eeg', return_value=eeg),
        patch('src.experiment.open_eyetracker', return_value=gaze),
    ):
        runner.run()

    assert calls[:4] == [
        'eeg.prepare',
        'gaze.prepare',
        'eeg.start',
        'gaze.start',
    ]
    assert calls[6:9] == ['eeg.stop', 'gaze.stop', 'marker:experiment_end']
    assert calls[-1] == 'ui.close'

    text = stream.getvalue()
    boundaries = [
        'BEGIN session',
        'BEGIN eeg-setup',
        'END eeg-setup status=ok',
        'BEGIN eyelink-setup',
        'END eyelink-setup status=ok',
        'BEGIN project-window',
        'BEGIN recording',
        'END recording',
        'END project-window',
        'END session',
    ]
    positions = [text.index(boundary) for boundary in boundaries]
    assert positions == sorted(positions)


def test_setup_failure_still_writes_end_boundary(tmp_path):
    logger, stream = _logger()
    runner = ExperimentRunner(
        ExperimentConfig(DATA_OUT_DIR=str(tmp_path)),
        data_manager=_Data(),
        ui_manager=_UI([]),
        lsl_manager=_LSL([]),
        logger=logger,
    )
    broken = Mock()
    broken.prepare.side_effect = RuntimeError('setup broke')

    assert runner._prepare_device('eeg-setup', broken) is False
    broken.stop.assert_called_once_with()

    text = stream.getvalue()
    assert 'BEGIN eeg-setup' in text
    assert 'END eeg-setup status=unavailable action=continue' in text


def test_runner_continues_when_live_devices_are_unavailable(tmp_path):
    calls = []
    logger, stream = _logger()
    eeg = Mock()
    eeg.prepare.side_effect = OSError('EEG offline')
    gaze = Mock()
    gaze.prepare.side_effect = OSError('EyeLink offline')
    runner = ExperimentRunner(
        ExperimentConfig(
            ENABLE_LSL=False,
            USE_DUMMY_EEG=False,
            USE_DUMMY_EYETRACKER=False,
            DATA_OUT_DIR=str(tmp_path),
        ),
        data_manager=_Data(),
        ui_manager=_UI(calls),
        lsl_manager=_LSL(calls),
        logger=logger,
    )
    runner._wait_for_start = lambda session_id, task_count: None

    with (
        patch('src.experiment.open_eeg', return_value=eeg),
        patch('src.experiment.open_eyetracker', return_value=gaze),
    ):
        runner.run()

    eeg.stop.assert_called_once_with()
    gaze.stop.assert_called_once_with()
    assert 'ui.style:mono' in calls
    assert calls[-1] == 'ui.close'
    text = stream.getvalue()
    assert 'END eeg-setup status=unavailable action=continue' in text
    assert 'END eyelink-setup status=unavailable action=continue' in text
    assert '[EEG-UNAVAILABLE] recording skipped' in text
    assert '[EYELINK-UNAVAILABLE] recording skipped' in text
    assert 'END session' in text


def test_short_dummy_session_logs_skipped_setup(tmp_path):
    calls = []
    logger, stream = _logger()
    runner = ExperimentRunner(
        ExperimentConfig(
            ENABLE_LSL=False,
            USE_DUMMY_EEG=True,
            USE_DUMMY_EYETRACKER=True,
            DATA_OUT_DIR=str(tmp_path),
        ),
        data_manager=_Data(),
        ui_manager=_UI(calls),
        lsl_manager=_LSL(calls),
        logger=logger,
    )
    runner._wait_for_start = lambda session_id, task_count: None
    runner.run()

    text = stream.getvalue()
    assert '[EEG-DUMMY] setup skipped' in text
    assert '[GAZE-DUMMY] calibration skipped' in text
    assert 'BEGIN recording' in text
    assert 'END recording' in text
    assert list((tmp_path / 'hardware').glob('*/eeg/properties.json'))
    assert list((tmp_path / 'hardware').glob('*/gaze/gaze.csv'))
