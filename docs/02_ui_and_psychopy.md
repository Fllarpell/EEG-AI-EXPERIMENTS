# Context 02: PsychoPy UI Manager
This document specifies the `src/ui_manager.py` module. PsychoPy can be tricky with memory leaks and window contexts, so we encapsulate it here.

## 1. Class: `UIManager`
**Initialization:** Receives an `ExperimentConfig` object. Initializes the `psychopy.visual.Window` and a `psychopy.hardware.keyboard.Keyboard` object.

## 2. UI Components
Initialize the following components once during `__init__` to avoid memory reallocation during the event loop:
1. `code_stim`: `visual.TextStim` (monospace font like 'Courier', left-aligned, anchored top-left, positioned appropriately).
2. `prompt_stim`: `visual.TextStim` (Instructions text: "Enter bug line numbers (comma separated):", yellow color).
3. `input_box`: `visual.TextBox2` (Editable text box for participant input, white background, black text).
4. `next_button`: `visual.ButtonStim` (Clickable button to proceed).

## 3. Public Methods
- `prepare_task_screen(code_text: str)`: 
  - **Crucial Logic:** Takes raw `code_text`, splits it by newline, and prepends line numbers to each line (e.g., ` 1 | def init():\n 2 |     pass`). 
  - Updates `code_stim.text` with this numbered code.
  - Clears the `input_box.text`.
  - Sets focus to `input_box` (`input_box.hasFocus = True`).
- `draw()`: Calls `.draw()` on all components and executes `win.flip()`.
- `get_user_input() -> str`: Returns the current value of `input_box.text`.
- `check_next_clicked() -> bool`: Returns True if `next_button.buttonSelected` is triggered. Includes a small debounce mechanism.
- `close()`: Safely closes the PsychoPy window.
