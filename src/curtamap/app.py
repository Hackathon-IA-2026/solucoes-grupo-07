"""Ponto de entrada: configura a página, o contexto comum e registra as telas."""

import streamlit as st

from curtamap.ui import contexto, metodologia, operacao, tatica

st.set_page_config(page_title="CurtaMap", page_icon="⚡", layout="wide")

pages = st.navigation(
    [
        # A página padrão é servida na raiz; `url_path` seria ignorado.
        st.Page(operacao.render, title="Operação D+1", icon="⚡", default=True),
        st.Page(tatica.render, title="Visão tática", icon="📊", url_path="tatica"),
        st.Page(
            metodologia.render, title="Metodologia e limites", icon="📐", url_path="metodologia"
        ),
    ]
)
st.sidebar.markdown("### CurtaMap")
st.sidebar.caption("Nome de trabalho · protótipo do Hackathon IA COPPE 2026")
context = contexto.load()
contexto.store(context)
if context is not None:
    contexto.seal(context)
pages.run()
