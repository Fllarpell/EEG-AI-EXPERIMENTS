# Context 04: The Experiment Runner
This document specifies `src/experiment.py` and `main.py`. This is the orchestrator that brings Config, Data, UI, and LSL together.

## 1. Class: `ExperimentRunner`
**Dependencies:** Injected via constructor or initialized inside using `ExperimentConfig`.
- `data_manager: DataManager`
- `ui_manager: UIManager`
- `lsl_manager: LSLManager`

## 2. The `run()` Method (Event Loop)
1. Generate a unique `session_id` (e.g., timestamp).
2. Load tasks via `data_manager`.
3. Wait for operator to press 'Space' to begin.
4. Push LSL marker: `EXP_START`.
5. **Iterate over tasks:**
   - Call `ui_manager.prepare_task_screen(task.code_text)`.
   - Push LSL marker: `TASK_START` (with task details).
   - Initialize a `core.Clock()` for the trial.
   - Clear keyboard event buffer.
   - Initialize an empty list for `keystroke_log`.
   - **Inner Loop (`while not task_done`):**
     - Call `ui_manager.draw()`.
     - Check `psychopy.event.getKeys(['escape'])` -> gracefully abort if pressed.
     - Fetch keyboard events via PsychoPy's hardware keyboard. For each key pressed:
       - Append to `keystroke_log` with its `name` and exact `rt` (reaction time).
     - Check if `ui_manager.check_next_clicked()` is True:
       - Push LSL marker: `TASK_END`.
       - Create a `TrialResult` dataclass instance using elapsed time, `ui_manager.get_user_input()`, and the `keystroke_log`.
       - Pass it to `data_manager.save_trial_result()`.
       - Break inner loop to proceed to next task.
6. Push LSL marker: `EXP_END`.
7. Call `ui_manager.close()`.

## 3. `main.py`
The entry point of the application.
- Loads `ExperimentConfig`.
- Initializes `ExperimentRunner`.
- Wraps the `run()` call in a `try...except` block to ensure `ui_manager.close()` is called even if an exception occurs (preventing fullscreen crashes requiring a hard reboot).
