"""CurtaMap - Ponto de Entrada da Interface Streamlit.

Configura a navegação multipágina via st.navigation e conecta as telas de Operação D+1,
Visão Tática e Metodologia/Limites.
"""

from pathlib import Path
import sys

# Garante que o diretório 'src' esteja no PYTHONPATH independente da forma de execução
src_path = Path(__file__).resolve().parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import streamlit as st

from curtamap.ui.metodologia import render_metodologia_page
from curtamap.ui.operacao import render_operacao_page
from curtamap.ui.tatica import render_tatica_page

# Configuração da página principal
st.set_page_config(
    page_title="CurtaMap ⚡ Previsão e Diagnóstico de Curtailment",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Definição das páginas com funções puras
page_operacao = st.Page(
    render_operacao_page,
    title="Operação D+1",
    icon="⚡",
    default=True,
)

page_tatica = st.Page(
    render_tatica_page,
    title="Visão Tática",
    icon="📈",
)

page_metodologia = st.Page(
    render_metodologia_page,
    title="Metodologia e Limites",
    icon="📚",
)

# Registro de navegação multipágina
pg = st.navigation(
    {
        "CurtaMap Platform": [page_operacao, page_tatica, page_metodologia]
    }
)

# Execução da página selecionada
pg.run()
