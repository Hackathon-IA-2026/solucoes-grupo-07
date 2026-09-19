from pathlib import Path

import streamlit as st

from curtamap.config import settings


def _count_parquet_files(directory: Path) -> int:
    return len(list(directory.rglob("*.parquet"))) if directory.exists() else 0


st.set_page_config(page_title="CurtaMap", page_icon="⚡", layout="wide")

st.title("CurtaMap")
st.caption("Nome de trabalho · protótipo do Hackathon IA COPPE 2026")

raw_dir = settings.data_dir / "raw"
parquet_count = _count_parquet_files(raw_dir)

if parquet_count == 0:
    st.warning(
        "Nenhum Parquet foi encontrado em data/raw. O dashboard está em modo de preparação "
        "e não exibe previsões simuladas como se fossem resultados reais."
    )
else:
    st.success(f"{parquet_count} arquivo(s) Parquet encontrado(s) para validação.")

operational, strategic, methodology = st.tabs(
    ["Operação D+1", "Visão tática", "Metodologia e limites"]
)

with operational:
    st.subheader("Próximas 24 horas")
    st.write(
        "A tela operacional mostrará 48 janelas de 30 minutos por usina: risco de corte, "
        "volume esperado, causa provável, incerteza e ação recomendada."
    )
    st.info("Aguardando ingestão e validação das bases oficiais.")

with strategic:
    st.subheader("Perdas e oportunidades")
    st.write(
        "Resumo semanal e mensal por usina, causa e subsistema, com cenários de MWh "
        "recuperáveis, valor financeiro e CO2 evitado."
    )
    st.info("Aguardando definição das premissas financeira e de carbono.")

with methodology:
    st.subheader("O que o modelo pode e não pode afirmar")
    st.markdown(
        """
        - O núcleo preditivo será comparado com baselines temporais em backtest.
        - Vento e irradiância verificados não serão tratados como previsão meteorológica D+1.
        - Explicações de features não provam causalidade.
        - Recomendações de investimento serão cenários com premissas visíveis.
        """
    )
