# Context 01: Data Management & Logging
This document specifies the `src/data_manager.py` module for the Neuro-SE experiment.

## 1. Responsibilities
The `DataManager` class handles reading the input stimuli (code snippets) and persisting the high-frequency telemetry collected during the experiment.

## 2. Input Data Format (`assets/tasks.json`)
The experiment is driven by a JSON payload. The `DataManager.load_tasks()` method must parse this into a list of typed dictionaries or dataclasses (`TaskPayload`).
Example JSON structure:
```json
[
  {
    "task_id": "human_sort_01",
    "condition": "human_written",
    "code_text": "def sort(arr):\n    return sorted(arr)"
  },
  {
    "task_id": "ai_search_02",
    "condition": "ai_generated",
    "code_text": "def binary_search(arr, val):\n    pass"
  }
]
```

## 3. High-Frequency Behavioral Logging
The system must log every single keystroke the user makes in the input box, along with its precise reaction time (RT) from the start of the trial.
- Define a `TrialResult` dataclass containing:
  - `session_id`: str (timestamp-based)
  - `task_id`: str
  - `condition`: str
  - `final_input`: str (what the user typed to find the bug)
  - `total_duration_sec`: float
  - `keystroke_log`: List[Dict[str, Any]] (A list of dicts containing `key_name`, `rt`, and `duration`).

## 4. Output Generation
- `DataManager.save_trial_result(result: TrialResult)`: Appends the result to a CSV file in the `DATA_OUT_DIR`. The `keystroke_log` should be serialized to a JSON string within the CSV column to maintain flat CSV structure while keeping nested behavioral data intact for later Pandas/Python analysis.
