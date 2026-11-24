"""EEG and gaze readers.

Both the dummy and the live reader expose start() and stop(). Flip
USE_DUMMY_EEG / USE_DUMMY_EYETRACKER in core/config.py when the bench
hardware is connected. The live classes call the same blocks as
Leon-Parepko/EEG-Experiment-Script: BrainVision RDA and EyeLink.
"""

from hardware.devices import open_eeg, open_eyetracker

__all__ = ["open_eeg", "open_eyetracker"]
