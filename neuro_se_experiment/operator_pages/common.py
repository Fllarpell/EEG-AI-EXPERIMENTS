"""Shared paths and file helpers for the operator pages."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
TASKS_PATH = ROOT / "assets" / "tasks.json"
PHOTOS_DIR = ROOT / "assets" / "code_photos"
LOG_PATH = ROOT / "data" / "experiment.log"
CONSOLE_LOG = ROOT / "data" / "operator_console.log"
PYTHON = ROOT / ".venv" / "bin" / "python"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
LABELS = {
    "human_written": "Написано человеком",
    "ai_generated": "Сгенерировано ИИ",
}


def inject_css() -> None:
    st.markdown(
        """
        <style>
          .stApp, [data-testid="stSidebar"] {
            background: #f6f4f1;
            color: #1c1b19;
          }
          .block-container { padding-top: 1.2rem; max-width: 1100px; }
          .stMarkdown, .stMarkdown p, [data-testid="stWidgetLabel"] p,
          [data-testid="stHeading"] {
            color: #1c1b19;
          }
          .hero { margin-bottom: 0.8rem; }
          .kicker {
            letter-spacing: 0.06em;
            text-transform: uppercase;
            color: #5c6570;
            font-size: 0.75rem;
            margin-bottom: 0.2rem;
          }
          h1 { font-weight: 560; letter-spacing: -0.02em; margin: 0; color: #1c1b19; }
          .lede { color: #3e4650; max-width: 42rem; }
          .note {
            margin-top: 1rem;
            padding: 0.8rem 0.9rem;
            border: 1px solid #e4dfd6;
            border-radius: 10px;
            background: #ffffff;
            color: #1c1b19;
            line-height: 1.55;
          }
          input, textarea, [data-baseweb="select"] {
            color: #1c1b19 !important;
            -webkit-text-fill-color: #1c1b19 !important;
            background-color: #ffffff !important;
            caret-color: #1c1b19 !important;
          }
          textarea {
            font-family: ui-monospace, "SF Mono", Menlo, monospace !important;
            font-size: 0.95rem !important;
            line-height: 1.45 !important;
          }
          button[kind="primary"] {
            background: #3c4f66 !important;
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            border: none !important;
          }
          div[data-testid="stImage"] img { border-radius: 8px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def load_tasks() -> List[Dict[str, Any]]:
    if not TASKS_PATH.is_file():
        return []
    payload = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    return payload


def save_tasks(tasks: List[Dict[str, Any]]) -> None:
    """Replace tasks.json in one step so the experiment never reads a half file."""
    TASKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(tasks, ensure_ascii=False, indent=2) + "\n"
    if TASKS_PATH.is_file() and TASKS_PATH.read_text(encoding="utf-8") == encoded:
        return
    temporary = TASKS_PATH.with_suffix(".json.tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(TASKS_PATH)


def list_photos() -> List[str]:
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    names = [
        path.name
        for path in PHOTOS_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    ]
    return sorted(names)


def origin_caption(origin: str) -> str:
    if origin == "ai_generated":
        return "ИИ"
    if origin == "human_written":
        return "человек"
    return origin


def latest_recording() -> str:
    """List every file of the newest hardware session, with sizes."""
    root = ROOT / "data" / "hardware"
    lines: List[str] = []
    if root.is_dir():
        sessions = sorted(path for path in root.iterdir() if path.is_dir())
        if sessions:
            session = sessions[-1]
            lines.append(str(session.relative_to(ROOT)))
            files = sorted(path for path in session.rglob("*") if path.is_file())
            if not files:
                lines.append("(папка пустая)")
            for path in files:
                lines.append(f"{path.relative_to(session)}   {path.stat().st_size} байт")
    trials = ROOT / "data" / "trials.csv"
    log_path = ROOT / "data" / "experiment.log"
    if trials.is_file():
        lines.append(f"data/trials.csv   {trials.stat().st_size} байт")
    if log_path.is_file():
        lines.append(f"data/experiment.log   {log_path.stat().st_size} байт")
    return "\n".join(lines) if lines else "Записей ещё нет."


def tail(path: Path, limit: int = 40) -> str:
    if not path.is_file():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-limit:])


def launch(
    line_style: str,
    dummy_eeg: bool,
    dummy_gaze: bool,
    use_lsl: bool,
    fullscreen: bool,
) -> subprocess.Popen[bytes]:
    python = PYTHON if PYTHON.is_file() else Path(sys.executable)
    command = [
        str(python),
        "-u",
        str(ROOT / "main.py"),
        "--line-style",
        line_style,
        "--dummy-eeg" if dummy_eeg else "--no-dummy-eeg",
        "--dummy-gaze" if dummy_gaze else "--no-dummy-gaze",
        "--lsl" if use_lsl else "--no-lsl",
        "--fullscreen" if fullscreen else "--no-fullscreen",
    ]
    CONSOLE_LOG.parent.mkdir(parents=True, exist_ok=True)
    handle = CONSOLE_LOG.open("ab")
    return subprocess.Popen(command, cwd=str(ROOT), stdout=handle, stderr=subprocess.STDOUT)


def stop_process(proc: Optional[subprocess.Popen[bytes]]) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
