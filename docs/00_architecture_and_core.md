# Context 00: Core Architecture & Project Overview
You are an expert Python Software Engineer and a Neuroscience Researcher. We are building a highly modular, enterprise-grade experiment using `psychopy` for a Neuro-Software Engineering (Neuro-SE) study. 

## 1. Project Goal
The system will present code snippets (Human-written vs AI-generated) to software developers while recording high-frequency behavioral data (keystrokes, reaction times) and synchronizing with external hardware (EEG and Eye-Trackers) via Lab Streaming Layer (LSL).

## 2. Architectural Principles
- **Separation of Concerns (SoC):** UI rendering, hardware synchronization (LSL), data I/O, and business logic must be completely isolated.
- **Dependency Injection:** The main experiment loop must receive pre-initialized UI, LSL, and Data managers to make testing and swapping components (e.g., changing Text UI to Image UI) seamless.
- **Strict Typing:** Use Python `typing` module extensively (`Dict`, `List`, `Optional`, `Any`).
- **Configuration as Code:** All settings (colors, timings, LSL flags) must reside in a strictly typed `config.py` using `dataclasses`.

## 3. Directory Structure
Generate the following strict directory structure:
```text
neuro_se_experiment/
├── main.py
├── core/
│   ├── __init__.py
│   ├── config.py          # Dataclass-based configuration
│   └── logger.py          # Internal logging system (logging module)
├── data/                  # Output directory for logs (ignored in git)
├── assets/
│   └── tasks.json         # Input JSON payload with code snippets
├── src/
│   ├── __init__.py
│   ├── data_manager.py    # File I/O and state persistence
│   ├── lsl_manager.py     # Lab Streaming Layer integration
│   ├── ui_manager.py      # PsychoPy visual wrappers
│   └── experiment.py      # State machine and event loop
└── requirements.txt
```

## 4. `core/config.py` Specification
Implement `ExperimentConfig` as a `@dataclass`.
- `WINDOW_SIZE`: Tuple[int, int] = (1920, 1080)
- `FULLSCREEN`: bool = False
- `BG_COLOR`: Tuple[float, float, float] = (-0.8, -0.8, -0.8) # Crucial: neutral gray to avoid pupillary light reflex artifacts.
- `ENABLE_LSL`: bool = True # Feature flag for EEG/Eye-tracking
- `DATA_OUT_DIR`: str = "data/"
- `TASKS_FILE`: str = "assets/tasks.json"

Stop generating here for this context file. Wait for the next specifications to implement the modules.
