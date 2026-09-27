"""Identidade visual do painel: paleta, CSS e componentes HTML pequenos."""

from html import escape

import streamlit as st

TINTA = "#0B1F3A"
TEXTO_SUAVE = "#5B6B82"
FUNDO = "#F4F7FB"
ALERTA = "#E4572E"
ALERTA_FORTE = "#B3193A"
LIVRE = "#14A89A"
SEM_GERACAO = "#E3E8EF"
DESTAQUE = "#F2A541"
FONTE_TEXTO = "Inter, 'Segoe UI', sans-serif"

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
[data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] * {{
  font-family: {FONTE_TEXTO}; }}
.stApp {{ background: {FUNDO}; }}
#MainMenu, footer, header[data-testid="stHeader"] {{ visibility: hidden; height: 0; }}
.block-container {{ padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1480px; }}
.cm-topo {{
  background: linear-gradient(120deg, {TINTA} 0%, #173B6C 60%, #1F5C8F 100%);
  border-radius: 22px; padding: 26px 32px; color: #fff; margin-bottom: 8px;
  box-shadow: 0 12px 32px rgba(11, 31, 58, .18);
}}
.cm-marca {{ font-size: 15px; letter-spacing: .14em; text-transform: uppercase; opacity: .75;
  font-weight: 600; }}
.cm-marca b {{ color: {DESTAQUE}; }}
.cm-titulo {{ font-size: 34px; font-weight: 800; margin: 6px 0 4px; line-height: 1.15; }}
.cm-sub {{ font-size: 16px; opacity: .85; }}
.cm-card {{
  background: #fff; border-radius: 18px; padding: 18px 22px; height: 100%;
  box-shadow: 0 4px 18px rgba(11, 31, 58, .07); border: 1px solid #E8EDF4;
}}
.cm-rotulo {{ color: {TEXTO_SUAVE}; font-size: 13px; font-weight: 600; text-transform: uppercase;
  letter-spacing: .06em; }}
.cm-valor {{ color: {TINTA}; font-size: 34px; font-weight: 800; margin-top: 4px; }}
.cm-valor small {{ font-size: 16px; font-weight: 600; color: {TEXTO_SUAVE}; }}
.cm-nota {{ color: {TEXTO_SUAVE}; font-size: 13px; margin-top: 2px; }}
.cm-secao {{ color: {TINTA}; font-size: 21px; font-weight: 700; margin: 22px 0 8px; }}
.cm-aviso {{
  background: #fff; border-radius: 20px; padding: 22px 26px;
  border-left: 8px solid {ALERTA}; box-shadow: 0 6px 22px rgba(11, 31, 58, .08);
}}
.cm-aviso.livre {{ border-left-color: {LIVRE}; }}
.cm-aviso h3 {{ color: {TINTA}; font-size: 22px; font-weight: 800; margin: 0 0 4px; }}
.cm-meta {{ color: {TEXTO_SUAVE}; font-size: 14px; margin-bottom: 12px; }}
.cm-janela {{ display: flex; align-items: baseline; gap: 14px; padding: 10px 0;
  border-top: 1px solid #EEF2F7; }}
.cm-hora {{ font-size: 24px; font-weight: 800; color: {ALERTA_FORTE}; min-width: 170px; }}
.cm-hora.livre {{ color: {LIVRE}; font-size: 18px; min-width: 170px; }}
.cm-detalhe {{ color: {TINTA}; font-size: 15px; }}
.cm-detalhe span {{ color: {TEXTO_SUAVE}; }}
.cm-pill {{ display: inline-block; padding: 3px 12px; border-radius: 999px; font-size: 13px;
  font-weight: 700; background: #FDECE7; color: {ALERTA_FORTE}; margin-right: 6px; }}
.cm-pill.livre {{ background: #E3F6F3; color: #0B7A70; }}
.cm-pill.neutra {{ background: #EEF2F7; color: {TEXTO_SUAVE}; }}
.cm-acerto {{ background: {TINTA}; color: #fff; border-radius: 18px; padding: 18px 24px;
  display: grid; grid-template-columns: 1.1fr repeat(var(--n), 1fr); gap: 24px;
  align-items: center; }}
.cm-acerto .fonte {{ font-size: 13px; text-transform: uppercase; letter-spacing: .08em;
  opacity: .7; font-weight: 700; }}
.cm-acerto b {{ color: {DESTAQUE}; font-size: 26px; font-weight: 800; }}
.cm-acerto .t {{ font-size: 14px; opacity: .9; }}
.cm-legenda {{ display: flex; gap: 18px; color: {TEXTO_SUAVE}; font-size: 13px;
  margin: -4px 0 4px; }}
.cm-motivo {{ font-size: 21px; line-height: 1.2; display: block; padding: 4px 0; }}
.cm-legenda i {{ display: inline-block; width: 12px; height: 12px; border-radius: 3px;
  margin-right: 6px; vertical-align: -1px; }}
.cm-rodape {{ color: {TEXTO_SUAVE}; font-size: 13px; }}
div[data-testid="stDataFrame"] {{ border-radius: 14px; overflow: hidden; }}
</style>
"""


def aplicar() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def html(conteudo: str) -> None:
    st.markdown(conteudo, unsafe_allow_html=True)


def card(rotulo: str, valor: str, nota: str = "") -> str:
    nota_html = f'<div class="cm-nota">{escape(nota)}</div>' if nota else ""
    return (
        f'<div class="cm-card"><div class="cm-rotulo">{escape(rotulo)}</div>'
        f'<div class="cm-valor">{valor}</div>{nota_html}</div>'
    )
