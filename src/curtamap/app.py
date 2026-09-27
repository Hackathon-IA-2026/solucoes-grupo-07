"""Ponto de entrada do CurtaMap: `uv run streamlit run src/curtamap/app.py`."""

import streamlit as st

from curtamap.ui import painel

st.set_page_config(
    page_title="CurtaMap · aviso diário de cortes",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)
painel.render()
