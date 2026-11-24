"""Session launcher. Task editing lives on its own page."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional

import streamlit as st

from operator_pages.common import LOG_PATH, inject_css, latest_recording, launch, stop_process, tail


@st.cache_resource
def _autostart_session(
    line_style: str,
    dummy_eeg: bool,
    dummy_gaze: bool,
    use_lsl: bool,
    fullscreen: bool,
) -> subprocess.Popen[bytes]:
    """Start at most one automatic session for the whole Streamlit server."""
    return launch(line_style, dummy_eeg, dummy_gaze, use_lsl, fullscreen)


def main() -> None:
    inject_css()
    if "proc" not in st.session_state:
        st.session_state.proc = None

    live_default = os.environ.get('NEURO_SE_LIVE_DEFAULT') == '1'

    st.markdown(
        """
        <div class="hero">
          <p class="kicker">Neuro-SE · пульт оператора</p>
          <h1>Сессия</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p><a href="/tasks" target="_blank">Открыть редактор заданий отдельным окном</a></p>',
        unsafe_allow_html=True,
    )

    controls, hardware = st.columns([1.1, 1.0], gap="large")
    proc: Optional[subprocess.Popen[bytes]] = st.session_state.proc
    running = proc is not None and proc.poll() is None

    with controls:
        st.subheader("Запуск")
        line_style = st.radio(
            "Вид кода",
            options=("mono", "rainbow"),
            format_func=lambda value: "Однотонный" if value == "mono" else "Радужные скобки",
            horizontal=True,
            key="line_style",
        )
        fullscreen = st.toggle("Полный экран", value=False, key="start_fullscreen")
        dummy_eeg = st.toggle("Заглушка ЭЭГ", value=not live_default, key="dummy_eeg")
        dummy_gaze = st.toggle("Заглушка айтрекера", value=not live_default, key="dummy_gaze")
        use_lsl = st.toggle("Маркеры и потоки LSL", value=True, key="use_lsl")
        if (
            os.environ.get('NEURO_SE_AUTOSTART') == '1'
            and not st.session_state.get('autostart_done', False)
        ):
            st.session_state.autostart_done = True
            st.session_state.proc = _autostart_session(
                line_style, dummy_eeg, dummy_gaze, use_lsl, fullscreen
            )
            st.rerun()
        if running:
            st.success("Окно PsychoPy открыто.")
            if st.button("Остановить сессию", type="primary", use_container_width=True):
                stop_process(proc)
                st.session_state.proc = None
                st.rerun()
        else:
            if st.button("Открыть окно PsychoPy", type="primary", use_container_width=True):
                st.session_state.proc = launch(
                    line_style, dummy_eeg, dummy_gaze, use_lsl, fullscreen
                )
                st.rerun()
        st.markdown(
            """
            <div class="note">
            <b>Участник</b><br>
            На экране только задание. Пробел начинает сессию.<br>
            Остановить может только кнопка на этой странице.
            </div>
            """,
            unsafe_allow_html=True,
        )

    with hardware:
        st.subheader("Устройства")
        st.markdown(
            """
            | Поток LSL | Что это |
            | --- | --- |
            | `NeuroSE_Markers` | старт, задание, клавиша |
            | `NeuroSE_EEG` | отсчёты ЭЭГ |
            | `NeuroSE_Gaze` | x, y, зрачок у заглушки; живой трекер пишет EDF |
            """
        )
        st.caption(
            "Живые приборы: BrainVision RDA `100.1.1.3:51244`, EyeLink `100.1.1.1`. "
            "Заглушку айтрекера выключить до открытия окна: сначала появятся экраны камеры и калибровки, затем задания."
        )
        st.markdown("**Скрипты**")
        if sys.platform == "win32":
            st.code("start.bat\nstart.bat live", language="bat")
            st.caption(
                "Первая команда открывает пульт и окно заданий с заглушками. "
                "Вторая подключает усилитель 100.1.1.3:51244 и EyeLink 100.1.1.1."
            )
        else:
            st.code(
                "\n".join(
                    [
                        "cd neuro_se_experiment",
                        ".venv/bin/streamlit run operator_app.py --server.port 8765",
                        ".venv/bin/python main.py",
                        ".venv/bin/python main.py --no-dummy-eeg --no-dummy-gaze",
                        ".venv/bin/python hardware/rda_client.py",
                    ]
                ),
                language="bash",
            )
            st.caption(
                "Пульт — вторая команда. Сессия с заглушками — третья. "
                "Живые ЭЭГ и айтрекер — четвёртая. Пятая пишет только усилитель в текущую папку."
            )
        st.markdown("**Последняя запись**")
        st.code(latest_recording(), language="text")

    st.subheader("Журнал")
    st.caption("Полный файл data/experiment.log: соединение, каналы, каждый маркер усилителя, калибровка, каждый старт задания и каждая клавиша.")
    st.code(tail(LOG_PATH, limit=80) or "Журнал появится после первой сессии.", language="text")


main()
