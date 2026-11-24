"""Entry point for the Neuro-SE experiment.

Run from this directory:

    python main.py

The operator console passes the same flags:

    python main.py --line-style rainbow --dummy-eeg --dummy-gaze
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.config import ExperimentConfig
from core.logger import setup_logger
from src.experiment import ExperimentAborted, ExperimentRunner


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Neuro-SE PsychoPy session")
    parser.add_argument("--line-style", choices=("mono", "rainbow"), default="mono")
    parser.add_argument("--dummy-eeg", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--dummy-gaze", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--lsl", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--fullscreen", action=argparse.BooleanOptionalAction, default=False)
    return parser.parse_args()


def main() -> None:
    """Build the runner and guarantee the window is closed on any failure."""
    args = parse_args()
    config = ExperimentConfig(
        ENABLE_LSL=args.lsl,
        USE_DUMMY_EEG=args.dummy_eeg,
        USE_DUMMY_EYETRACKER=args.dummy_gaze,
        LINE_STYLE=args.line_style,
        FULLSCREEN=args.fullscreen,
    )
    logger = setup_logger("neuro_se", config.resolve_path(config.DATA_OUT_DIR))
    runner: Optional[ExperimentRunner] = None
    try:
        runner = ExperimentRunner(config, logger=logger)
        runner.run()
    except ExperimentAborted as exc:
        logger.info("%s", exc)
    except Exception:
        logger.exception("Experiment failed.")
        raise
    finally:
        if runner is not None:
            runner.shutdown()


if __name__ == "__main__":
    main()
