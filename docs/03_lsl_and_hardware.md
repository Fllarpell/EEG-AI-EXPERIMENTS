# Context 03: Lab Streaming Layer (LSL) Integration
This document specifies `src/lsl_manager.py`. In neurophysiological experiments (EEG, Eye-Tracking), sending sub-millisecond precision markers is critical for analyzing Event-Related Potentials (ERPs) and saccades.

## 1. Class: `LSLManager`
**Initialization:** Receives `enable_lsl: bool` from config.
If `True`, imports `pylsl`.
Creates a `StreamInfo` object:
- Name: 'NeuroSE_Markers'
- Type: 'Markers'
- Channel Count: 1
- Nominal srate: `pylsl.IRREGULAR_RATE`
- Channel Format: `pylsl.cf_string`
- Source ID: 'neuro_se_exp_1'

Creates a `StreamOutlet` from this info.

## 2. Marker Protocol
Implement a `push_marker(marker: str)` method.
- If `enable_lsl` is False, simply log the marker to the console/logger (e.g., `[LSL-STUB] -> {marker}`).
- If True, call `outlet.push_sample([marker])`.

## 3. Marker Dictionary (Standardization)
To avoid magic strings in the main loop, define constants or an Enum for standard markers:
- `EXP_START` = "experiment_start"
- `EXP_END` = "experiment_end"
- `TASK_START` (needs dynamic formatting: "task_start_{task_id}_{condition}")
- `TASK_END` = "task_end"
- `USER_TYPING` = "user_keystroke"
