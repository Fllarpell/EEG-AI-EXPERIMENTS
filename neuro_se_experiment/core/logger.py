"""Process-wide logger that stays independent of PsychoPy's root logger."""

from __future__ import annotations

import logging
from pathlib import Path


def setup_logger(name: str, log_dir: Path) -> logging.Logger:
    """Create a console + file logger.

    Propagation is disabled so PsychoPy, which installs its own handler on
    the root logger, cannot swallow or duplicate these records.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    if logger.handlers:
        return logger

    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_dir / "experiment.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    return logger
