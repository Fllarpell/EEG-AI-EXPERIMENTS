"""Operator console. The participant window is PsychoPy.

Run from this directory:

    .venv/bin/streamlit run operator_app.py
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Neuro-SE",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

page = st.navigation(
    [
        st.Page("operator_pages/session.py", title="Сессия", default=True),
        st.Page("operator_pages/tasks.py", title="Задания", url_path="tasks"),
    ]
)
page.run()
