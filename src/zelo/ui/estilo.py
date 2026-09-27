"""Identidade visual do painel: editorial, papel e tinta, com uma única cor de alerta."""

from html import escape

import streamlit as st

TINTA = "#16181D"
TEXTO_SUAVE = "#6B6F76"
PAPEL = "#F7F5F0"
FILETE = "#DDD8CC"
ALERTA = "#C4391D"
ALERTA_CLARO = "#F1C9BC"
ALERTA_FORTE = "#7A1E0E"
LIVRE = "#3F7D5C"
LIVRE_CLARO = "#CFE3D6"
SEM_GERACAO = "#E9E5DC"
FONTE_TEXTO = "Geist, 'Helvetica Neue', Arial, sans-serif"
FONTE_TITULO = "'Instrument Serif', Georgia, serif"

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@400;500;600&display=swap');
[data-testid="stMarkdownContainer"] .cm {{ font-family: {FONTE_TEXTO}; color: {TINTA}; }}
.stApp {{ background: {PAPEL}; }}
#MainMenu, footer, header[data-testid="stHeader"] {{ visibility: hidden; height: 0; }}
.block-container {{ padding-top: 2.4rem; padding-bottom: 3rem; max-width: 1360px; }}
/* A Instrument Serif só tem peso 400; um contorno fino da própria cor equivale a um passo
   acima sem o negrito sintético do navegador. */
.cm-mast h1, .cm-valor, .cm-secao, .cm-aviso h3, .cm-hora {{
  -webkit-text-stroke: 0.6px currentColor; }}
.cm-kicker {{ font-size: 12px; letter-spacing: .18em; text-transform: uppercase;
  color: {TEXTO_SUAVE}; font-weight: 500; }}
.cm-kicker b {{ color: {TINTA}; font-weight: 600; }}
.cm-mast {{ border-bottom: 1px solid {TINTA}; padding-bottom: 18px; margin-bottom: 6px; }}
.cm-mast h1 {{ font-family: {FONTE_TITULO}; font-weight: 400; font-size: 64px;
  line-height: 1.02; margin: 10px 0 12px; color: {TINTA}; padding: 0; }}
.cm-mast h1 em {{ color: {ALERTA}; }}
.cm-stats {{ display: grid; grid-template-columns: repeat(4, 1fr);
  border-bottom: 1px solid {FILETE}; margin: 4px 0 8px; }}
.cm-stat {{ padding: 18px 22px 20px; border-left: 1px solid {FILETE}; }}
.cm-stat:first-child {{ border-left: none; padding-left: 0; }}
.cm-rotulo {{ font-size: 12px; letter-spacing: .12em; text-transform: uppercase;
  color: {TEXTO_SUAVE}; font-weight: 500; }}
.cm-valor {{ font-family: {FONTE_TITULO}; font-size: 54px; line-height: 1.05;
  margin-top: 6px; color: {TINTA}; }}
.cm-valor small {{ font-size: 22px; color: {TEXTO_SUAVE}; }}
.cm-valor.texto {{ font-size: 32px; line-height: 1.15; padding-top: 8px; }}
.cm-nota {{ font-size: 13px; color: {TEXTO_SUAVE}; margin-top: 4px; line-height: 1.4; }}
.cm-secao {{ font-family: {FONTE_TITULO}; font-size: 34px; color: {TINTA};
  margin: 30px 0 6px; }}
.cm-legenda {{ display: flex; gap: 20px; color: {TEXTO_SUAVE}; font-size: 13px;
  margin: 0 0 6px; }}
.cm-legenda i {{ display: inline-block; width: 10px; height: 10px; margin-right: 7px; }}
.cm-aviso {{ border-top: 2px solid {TINTA}; padding-top: 14px; }}
.cm-aviso h3 {{ font-family: {FONTE_TITULO}; font-weight: 400; font-size: 38px;
  margin: 0; padding: 0; color: {TINTA}; line-height: 1.1; }}
.cm-meta {{ color: {TEXTO_SUAVE}; font-size: 13px; margin: 4px 0 8px;
  letter-spacing: .04em; }}
.cm-janela {{ display: grid; grid-template-columns: 190px 1fr; gap: 18px; padding: 14px 0;
  border-top: 1px solid {FILETE}; }}
.cm-hora {{ font-family: {FONTE_TITULO}; font-size: 34px; line-height: 1; color: {ALERTA}; }}
.cm-hora.livre {{ color: {LIVRE}; font-size: 26px; }}
.cm-hora.neutra {{ color: {TINTA}; font-size: 26px; }}
.cm-detalhe {{ font-size: 15px; line-height: 1.5; }}
.cm-detalhe .s {{ color: {TEXTO_SUAVE}; font-size: 14px; }}
.cm-tag {{ font-size: 11px; letter-spacing: .12em; text-transform: uppercase; font-weight: 600;
  color: {ALERTA}; margin-right: 8px; }}
.cm-tag.livre {{ color: {LIVRE}; }}
.cm-tag.neutra {{ color: {TEXTO_SUAVE}; }}
.cm-rodape {{ color: {TEXTO_SUAVE}; font-size: 13px; line-height: 1.6; }}
</style>
"""


def aplicar() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def html(conteudo: str) -> None:
    st.markdown(f'<div class="cm">{conteudo}</div>', unsafe_allow_html=True)


def stat(rotulo: str, valor: str, nota: str = "", *, texto: bool = False) -> str:
    classe = "cm-valor texto" if texto else "cm-valor"
    nota_html = f'<div class="cm-nota">{escape(nota)}</div>' if nota else ""
    return (
        f'<div class="cm-stat"><div class="cm-rotulo">{escape(rotulo)}</div>'
        f'<div class="{classe}">{valor}</div>{nota_html}</div>'
    )
