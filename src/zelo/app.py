"""Ponto de entrada do Zelo: `uv run streamlit run src/zelo/app.py`."""

import streamlit as st

from zelo.ui import painel

st.set_page_config(
    page_title="Zelo · aviso diário de cortes",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)
painel.render()
