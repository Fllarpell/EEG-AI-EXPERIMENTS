"""Live editor for snippets, photos, and the source badge.

Every change is written to tasks.json. An open PsychoPy trial reloads the
task that is on screen and leaves the typed answer in place.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

from operator_pages.common import (
    LABELS,
    PHOTOS_DIR,
    inject_css,
    list_photos,
    load_tasks,
    origin_caption,
    save_tasks,
)
from src.stimulus_format import format_numbered_code, source_lines

_DIFFICULTIES = ("easy", "hard", "control")


def main() -> None:
    inject_css()
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    st.markdown(
        """
        <div class="hero">
          <p class="kicker">Neuro-SE · задания</p>
          <h1>Код и фото</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tasks = load_tasks()
    if not tasks:
        with st.sidebar:
            if st.button("Добавить", width="stretch"):
                fresh = _blank_task(tasks)
                tasks.append(fresh)
                save_tasks(tasks)
                st.session_state.editor_task = fresh["task_id"]
                st.session_state.task_radio = fresh["task_id"]
                st.rerun()
        st.info("Заданий нет. Нажмите «Добавить».")
        return

    task_id = _select_task(tasks)
    index = [str(item.get("task_id", "")) for item in tasks].index(task_id)
    task = tasks[index]
    edited, warning = _edit_task(task, list_photos())
    if warning:
        st.warning(warning)
    if edited["task_id"] != task.get("task_id") and any(
        str(item.get("task_id")) == edited["task_id"] for item in tasks
    ):
        st.warning("Такое имя уже есть. Оставлено прежнее.")
        edited["task_id"] = task.get("task_id")
    if edited != task:
        tasks[index] = edited
        save_tasks(tasks)


def _select_task(tasks: List[Dict[str, Any]]) -> str:
    """Pick the open task from the left sidebar. The editor stays on the page."""
    ids = [str(item.get("task_id", "")) for item in tasks]
    if st.session_state.get("editor_task") not in ids:
        st.session_state.editor_task = ids[0]
    labels = {
        str(item.get("task_id", "")): f"{number}. {item.get('task_id', '')}"
        for number, item in enumerate(tasks, start=1)
    }
    with st.sidebar:
        _structure_buttons(tasks, ids)
        if st.session_state.get("task_radio") not in ids:
            st.session_state.task_radio = st.session_state.editor_task
        picked = st.radio(
            "Задание",
            ids,
            format_func=lambda task_id: labels.get(task_id, task_id),
            label_visibility="collapsed",
            key="task_radio",
        )
    st.session_state.editor_task = picked
    return str(picked)


def _structure_buttons(tasks: List[Dict[str, Any]], ids: List[str]) -> None:
    current = st.session_state.get("task_radio", st.session_state.get("editor_task", ids[0]))
    if current not in ids:
        current = ids[0]
    index = ids.index(current)
    if st.button("Добавить", width="stretch"):
        fresh = _blank_task(tasks)
        tasks.append(fresh)
        save_tasks(tasks)
        st.session_state.editor_task = fresh["task_id"]
        st.session_state.task_radio = fresh["task_id"]
        st.rerun()
    up, down = st.columns(2)
    with up:
        if st.button("Выше", width="stretch", disabled=index == 0):
            tasks[index - 1], tasks[index] = tasks[index], tasks[index - 1]
            save_tasks(tasks)
            st.rerun()
    with down:
        if st.button("Ниже", width="stretch", disabled=index == len(tasks) - 1):
            tasks[index + 1], tasks[index] = tasks[index], tasks[index + 1]
            save_tasks(tasks)
            st.rerun()
    if st.button("Удалить", width="stretch", disabled=len(tasks) == 1):
        removed = tasks.pop(index)
        save_tasks(tasks)
        nxt = str(tasks[min(index, len(tasks) - 1)].get("task_id", ""))
        st.session_state.editor_task = nxt
        st.session_state.task_radio = nxt
        _drop_widget_state(str(removed.get("task_id", "")))
        st.rerun()


def _edit_task(task: Dict[str, Any], photos: List[str]) -> tuple[Dict[str, Any], str]:
    task_id = str(task.get("task_id", "task"))
    form, preview = st.columns([1.05, 1.15], gap="large")
    with form:
        new_id = st.text_input("Имя задания", value=task_id, key=f"id_{task_id}").strip() or task_id
        origin_now = str(task.get("origin", "human_written"))
        origin = st.radio(
            "Истинный источник, пишется в журнал",
            options=("human_written", "ai_generated"),
            index=0 if origin_now != "ai_generated" else 1,
            format_func=origin_caption,
            key=f"origin_{task_id}",
            horizontal=True,
        )
        badge_now = str(task.get("label_text", "")).strip() or LABELS.get(origin_now, "")
        badge = st.text_input("Что видит участник", value=badge_now, key=f"badge_{task_id}")
        difficulty_now = str(task.get("difficulty", "easy"))
        difficulty = st.selectbox(
            "Сложность",
            _DIFFICULTIES,
            index=_DIFFICULTIES.index(difficulty_now) if difficulty_now in _DIFFICULTIES else 0,
            key=f"difficulty_{task_id}",
        )
        bug_now = ", ".join(str(line) for line in task.get("bug_lines") or [])
        bug_text = st.text_input(
            "Строки с багами",
            value=bug_now,
            key=f"bugs_{task_id}",
            placeholder="2, 5",
        )
        upload = st.file_uploader(
            "Загрузить фото кода",
            type=["png", "jpg", "jpeg", "webp"],
            key=f"upload_{task_id}",
        )
        uploaded_name = ""
        if upload is not None:
            destination = PHOTOS_DIR / _safe_name(upload.name)
            token = f"{destination.name}:{getattr(upload, 'size', 0)}"
            if st.session_state.get(f"applied_upload_{task_id}") != token:
                destination.write_bytes(upload.getvalue())
                st.session_state[f"applied_upload_{task_id}"] = token
                st.session_state[f"mode_{task_id}"] = "image"
                st.session_state[f"file_{task_id}"] = destination.name
            uploaded_name = destination.name
            photos = list_photos()
        mode = st.radio(
            "Что на экране",
            options=("text", "image"),
            index=0 if task.get("stimulus_type") != "image" else 1,
            format_func=lambda value: "Текст" if value == "text" else "Фото",
            horizontal=True,
            key=f"mode_{task_id}",
        )
        options = photos or ["(нет файлов)"]
        current_name = Path(str(task.get("image_path", ""))).name
        if uploaded_name:
            current_name = uploaded_name
        photo_index = options.index(current_name) if current_name in options else 0
        if mode == "image":
            photo_name = st.selectbox(
                "Файл фото",
                options,
                index=photo_index,
                key=f"file_{task_id}",
            )
        else:
            photo_name = current_name
    with preview:
        code = st.text_area(
            "Код",
            value=str(task.get("code_text", "")),
            key=f"code_{task_id}",
            height=360,
        )
        numbered = format_numbered_code(code)
        st.caption(f"Строк: {len(source_lines(code))}. Участник называет эти номера.")
        st.code(numbered or " ", language="text")
        if mode == "image" and photo_name and not str(photo_name).startswith("("):
            st.image(str(PHOTOS_DIR / photo_name), use_container_width=True)

    code_text = code.replace("\r\n", "\n")
    line_count = len(source_lines(code_text))
    bug_lines, warning = _bug_lines(bug_text, line_count)
    image_path = str(task.get("image_path", ""))
    if mode == "image" and photo_name and not str(photo_name).startswith("("):
        chosen_path = f"assets/code_photos/{photo_name}"
        if (PHOTOS_DIR / photo_name).is_file():
            image_path = chosen_path
    label_text, show_label = _stored_badge(task, origin, badge)
    edited = dict(task)
    edited.update(
        {
            "task_id": new_id,
            "origin": origin,
            "show_label": show_label,
            "label_text": label_text,
            "difficulty": difficulty,
            "has_bug": bool(bug_lines),
            "bug_lines": bug_lines,
            "stimulus_type": "image" if mode == "image" and image_path else "text",
            "image_path": image_path,
            "code_text": code_text,
            "language": str(task.get("language", "python")),
            "set_id": str(task.get("set_id", "set_1")),
        }
    )
    return edited, warning


def _stored_badge(task: Dict[str, Any], origin: str, badge: str) -> tuple[str, bool]:
    """Keep an empty badge empty until the operator actually types another phrase."""
    old_origin = str(task.get("origin", "human_written"))
    old_label = str(task.get("label_text", ""))
    old_derived = old_label.strip() or LABELS.get(old_origin, "")
    if badge.strip() == old_derived:
        if origin != old_origin and not old_label.strip():
            return "", True
        return old_label, bool(task.get("show_label", False))
    return badge.strip() or LABELS.get(origin, ""), True


def _bug_lines(text: str, line_count: int) -> tuple[List[int], str]:
    numbers = [int(piece) for piece in re.findall(r"\d+", text)]
    kept: List[int] = []
    dropped: List[int] = []
    for number in numbers:
        if number in kept:
            continue
        if line_count and 1 <= number <= line_count:
            kept.append(number)
        else:
            dropped.append(number)
    warning = ""
    if dropped:
        warning = "Эти номера не попали в файл, их нет в коде: " + ", ".join(
            str(number) for number in dropped
        )
    return kept, warning


def _blank_task(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    taken = {str(item.get("task_id", "")) for item in tasks}
    number = 1
    while f"task_{number:02d}" in taken:
        number += 1
    return {
        "task_id": f"task_{number:02d}",
        "set_id": "set_1",
        "origin": "human_written",
        "difficulty": "easy",
        "language": "python",
        "show_label": True,
        "label_text": LABELS["human_written"],
        "has_bug": True,
        "bug_lines": [1],
        "stimulus_type": "text",
        "image_path": "",
        "code_text": "def example():\n    return 0\n",
    }


def _drop_widget_state(task_id: str) -> None:
    for key in list(st.session_state.keys()):
        if str(key).endswith("_" + task_id):
            del st.session_state[key]


def _safe_name(name: str) -> str:
    cleaned = Path(name).name.replace("\\", "_").replace("/", "_")
    return cleaned or "photo.png"


main()
