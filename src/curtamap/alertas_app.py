"""Demonstração histórica de alertas: streamlit run src/curtamap/alertas_app.py."""

import os
from datetime import timedelta
from pathlib import Path

import plotly.graph_objects as go
import polars as pl
import streamlit as st

from curtamap.previsao.alertas import rank_alerts, validate_alerts

st.set_page_config(page_title="CurtaMap · Alertas", page_icon="⚡", layout="wide")
st.title("CurtaMap · Radar de cortes")
st.caption("Onde e quando concentrar a atenção da operação no dia seguinte")
st.info(
    "Reprodução histórica · emissão às 20h da véspera para 48 meias-horas do dia seguinte. "
    "Agosto/2026 já foi usado em desenvolvimento; esta tela não é uma previsão em tempo real."
)


@st.cache_data
def read_replay(path: str, modified: int) -> pl.DataFrame:
    return validate_alerts(pl.read_parquet(path))


def reais(value: float) -> str:
    return f"R$ {value:,.2f}".translate(str.maketrans({",": ".", ".": ","}))


directory = Path(os.getenv("CURTAMAP_ALERTAS_DIR", "data/interim/alertas"))
files = sorted(directory.glob("*.parquet"), key=lambda p: ("fotovoltaica" not in p.name, p.name))
if not files:
    st.warning("Nenhuma reprodução de alertas disponível. Gere os arquivos com o comando abaixo.")
    st.code(
        "uv run python -m curtamap.previsao.alertas 2026-08-01 2026-08-31 "
        "--fonte fotovoltaica\n"
        "uv run python -m curtamap.previsao.alertas 2026-08-01 2026-08-31 --fonte eolica"
    )
    st.stop()

chosen = st.sidebar.selectbox("Reprodução", files, format_func=lambda p: p.stem)
try:
    replay = read_replay(str(chosen), chosen.stat().st_mtime_ns)
except (ValueError, pl.exceptions.PolarsError) as error:
    st.error(f"Arquivo de reprodução inválido: {error}")
    st.stop()
days = replay["dia"].unique().sort().to_list()
day = st.sidebar.selectbox("Dia previsto", days, format_func=lambda d: d.strftime("%d/%m/%Y"))
daily = replay.filter(pl.col("dia") == day)
states = st.sidebar.multiselect("UF", sorted(daily["id_estado"].drop_nulls().unique().to_list()))
if states:
    daily = daily.filter(pl.col("id_estado").is_in(states))
ranking = rank_alerts(daily).join(
    daily.select("fonte", "id_ons", "nom_usina").unique(subset=["fonte", "id_ons"]),
    on=["fonte", "id_ons"],
    how="left",
)
row = daily.row(0, named=True)
st.caption(
    f"Emissão: {row['emitido_em']} · corte de publicação (exclusivo): {row['corte_dados']} · "
    f"rótulos de treino até {row['treino_ate']} · idade da informação: {row['idade']} dias. "
    "Disponibilidade simulada pelo calendário conservador do ONS."
)
a, b, c = st.columns(3)
a.metric(
    "Usinas em alerta", f"{ranking.filter(pl.col('janelas_alerta') > 0).height} / {ranking.height}"
)
b.metric("Janelas em alerta", int(ranking["janelas_alerta"].sum()))
c.metric("Janelas sem previsão", int(ranking["janelas_sem_previsao"].sum()))
st.subheader("Prioridade de acompanhamento")
st.caption(
    "Mais janelas em alerta primeiro; desempate pela maior probabilidade de corte. "
    "Horas em alerta medem duração sinalizada, não energia cortada. "
    "Sem alerta não significa risco zero."
)
st.dataframe(
    ranking.select(
        "nom_usina",
        "fonte",
        "id_ons",
        "status",
        "horas_alerta",
        "probabilidade_maxima",
        "primeiro_alerta",
        "janelas_sem_previsao",
    ),
    hide_index=True,
    width="stretch",
    column_config={
        "probabilidade_maxima": st.column_config.ProgressColumn(
            "Maior P(corte) em uma meia-hora", min_value=0, max_value=1, format="percent"
        )
    },
)
keys = list(zip(ranking["fonte"], ranking["id_ons"], strict=True))
names = dict(zip(keys, ranking["nom_usina"], strict=True))
key = st.selectbox("Usina", keys, format_func=lambda k: f"{names[k] or k[1]} · {k[0]} · {k[1]}")
profile = daily.filter((pl.col("fonte") == key[0]) & (pl.col("id_ons") == key[1])).sort("tau")
st.subheader("As 48 meias-horas do dia")
figure = go.Figure()
for column, label, color in [
    ("p_corte", "HGB · P(corte)", "#187c74"),
    ("hist_28d", "Frequência histórica · 28 dias", "#98a3ae"),
]:
    figure.add_trace(
        go.Scatter(
            x=profile["tau"].to_list(),
            y=profile[column].to_list(),
            mode="lines",
            name=label,
            line={"color": color},
            connectgaps=False,
        )
    )
figure.add_hline(
    y=profile["limiar_alerta"][0], line_dash="dash", annotation_text="Limiar congelado jan–abr"
)
figure.update_layout(
    yaxis={"range": [0, 1], "tickformat": ".0%", "title": "P(corte)"},
    xaxis_title="Horário previsto",
    height=350,
    margin={"t": 30, "b": 30},
)
st.plotly_chart(figure, width="stretch")
st.caption("As probabilidades das 48 janelas não representam P(algum corte no dia).")
alerts = profile.filter(pl.col("alerta").fill_null(False))
if alerts.height:
    st.write(
        f"**Acompanhamento:** {alerts.height} janelas sinalizadas "
        f"({alerts.height * 0.5:g} h no total), começando às {alerts['tau'].min():%H:%M}. "
        "Revisar programação e acompanhar os avisos oficiais da operação. "
        "O alerta não determina causa nem autoriza alteração de despacho."
    )
else:
    st.write("Nenhuma janela ultrapassa o limiar nesta usina. Mantenha o acompanhamento habitual.")
with st.expander("Conferir o observado e exportar as 48 janelas"):
    st.caption("O observado foi anexado após a previsão, apenas para conferência retrospectiva.")
    table = profile.select("tau", "p_corte", "limiar_alerta", "alerta", "y_corte")
    st.dataframe(table, hide_index=True, width="stretch")
    st.download_button(
        "Baixar janelas (CSV)",
        table.write_csv().encode("utf-8-sig"),
        file_name=f"alertas_{key[0]}_{key[1]}_{day}.csv",
        mime="text/csv",
    )
st.download_button(
    "Baixar prioridades do dia (CSV)",
    ranking.write_csv().encode("utf-8-sig"),
    file_name=f"prioridades_{day}.csv",
    mime="text/csv",
)

business_dir = Path(os.getenv("CURTAMAP_NEGOCIO_DIR", "data/interim/negocio"))
context_path = business_dir / f"{chosen.stem}_causas.parquet"
if context_path.exists():
    st.subheader("Contexto da causa · histórico publicado")
    causes = (
        pl.read_parquet(context_path)
        .filter((pl.col("fonte") == key[0]) & (pl.col("id_ons") == key[1]) & (pl.col("dia") == day))
        .sort("n_ordens", descending=True)
    )
    st.caption(
        "Distribuição das causas registradas nas ordens dos últimos 28 dias liberados. "
        "A causa não é prevista pelo modelo e não determina a causa do próximo evento."
    )
    if causes.is_empty():
        st.info("Sem ordens publicadas para caracterizar a causa neste recorte.")
    else:
        st.write(
            f"Amostra: {causes['n_ordens'].sum()} registros de meia-hora com ordem de restrição."
        )
        labels = {
            "REL": "indisponibilidade externa",
            "CNF": "confiabilidade elétrica",
            "ENE": "razão energética",
            "PAR": "limite do parecer de acesso",
            "DESCONHECIDA": "causa sem classificação conhecida",
        }
        dominant = causes["causa"][0]
        st.write(f"Mais frequente no histórico: **{dominant} · {labels.get(dominant, dominant)}**.")
        st.dataframe(
            causes.select("causa", "n_ordens", "participacao"),
            hide_index=True,
            column_config={"participacao": st.column_config.NumberColumn(format="percent")},
        )
        st.write(
            "**Próxima ação:** levar os horários sinalizados e este histórico ao centro de "
            "operação para avaliar uma janela de manutenção flexível já necessária. "
            "Confirmar a causa e a autorização com o operador antes de executar."
        )

business_path = business_dir / f"{chosen.stem}.parquet"
if business_path.exists():
    st.subheader("Quanto a escolha do horário teria custado?")
    if key[0] == "eolica":
        st.error(
            "Experimento não recomendado para manutenção eólica: em agosto, escolher só "
            "pelo alerta custou mais que usar o horário de menor geração histórica. "
            "Os valores abaixo permitem auditar essa limitação."
        )
    else:
        st.info(
            "Candidato a piloto solar: resultado médio positivo em agosto, com perdas em "
            "parte dos casos e em uma semana. Ainda exige confirmação prospectiva e "
            "validação da agenda de manutenção com o gerador."
        )
    st.warning(
        "Cenário retrospectivo, não economia realizada: parada de 2h dentro de 08h–18h. "
        "A janela foi escolhida só pelos alertas. Geração e PLD observados entram depois, "
        "para avaliar a escolha. Custos de equipe, mobilização e contratos não estão incluídos."
    )
    business = pl.read_parquet(business_path)
    fraction = st.slider("Fração hipotética da geração afetada pela parada (%)", 1, 100, 10)
    baseline = st.selectbox(
        "Comparar com",
        ["menor_geracao_historica", "fixo_08h", "historico_corte"],
        format_func=lambda x: {
            "menor_geracao_historica": "Menor geração histórica (28 dias)",
            "fixo_08h": "Horário fixo · 08h–10h",
            "historico_corte": "Maior frequência histórica de corte",
        }[x],
    )
    scenario = st.selectbox(
        "Preço para a conferência",
        ["PLD_CCEE_observado", "cenario_50", "cenario_100", "cenario_200"],
        format_func=lambda x: {
            "PLD_CCEE_observado": "CCEE · PLD horário observado",
            "cenario_50": "Cenário · R$ 50/MWh",
            "cenario_100": "Cenário · R$ 100/MWh",
            "cenario_200": "Cenário · R$ 200/MWh",
        }[x],
    )
    case = business.filter(
        (pl.col("fonte") == key[0])
        & (pl.col("id_ons") == key[1])
        & (pl.col("dia") == day)
        & (pl.col("cenario") == scenario)
    )
    if case.height and case["avaliavel"][0]:
        case_row = case.row(0, named=True)
        scale = fraction / (100 * case_row["fracao_indisponivel"])
        proposal, reference = case_row["inicio_curtamap"], case_row[f"inicio_{baseline}"]
        st.write(
            f"Janela CurtaMap: **{proposal:%H:%M}–{proposal + timedelta(hours=2):%H:%M}**. "
            f"Referência: **{reference:%H:%M}–{reference + timedelta(hours=2):%H:%M}**."
        )
        st.metric("Custo de oportunidade · CurtaMap", reais(case_row["custo_curtamap_brl"] * scale))
        st.metric(
            "Custo de oportunidade · referência",
            reais(case_row[f"custo_{baseline}_brl"] * scale),
        )
        gain = case_row[f"diferenca_vs_{baseline}_brl"] * scale
        st.metric("Diferença · positiva = custo menor", reais(gain))
        if gain < 0:
            st.error("Neste caso, seguir o alerta teria custado mais que a referência.")
    else:
        st.info("Não há observações completas para comparar todas as estratégias neste caso.")
    st.caption(
        "Conta: geração observada (MW) × 0,5h × fração indisponível × preço (R$/MWh). "
        "A fração é uma premissa linear e não reproduz a redistribuição real do corte. "
        "PLD é uma referência de valoração, não o preço do contrato do gerador."
    )
    with st.expander("Resultado de todas as oportunidades · ganhos e perdas"):
        totals = pl.read_csv(business_path.with_suffix(".csv")).filter(
            (pl.col("cenario") == scenario) & (pl.col("baseline") == baseline)
        )
        st.dataframe(totals, hide_index=True)
        st.caption(
            "Tabela no cenário original de 10%. Cada usina/dia é uma oportunidade independente. "
            "A soma não é economia mensal: não se presume manutenção diária de todas as usinas."
        )
    st.markdown(
        "Preço: [CCEE · PLD horário](https://dadosabertos.ccee.org.br/dataset/pld_horario), "
        "CC-BY-4.0. Geração e causas: snapshot ONS auditado no repositório."
    )
with st.expander("Evidência e limites da entrega"):
    st.write(
        "O classificador é o componente de ocorrência existente na v1/v3, com os mesmos "
        "parâmetros e 14 features. Não houve novo ajuste em agosto. Os dados são um snapshot "
        "histórico revisável e a publicação é simulada. Não há previsão meteorológica nem "
        "avaliação prospectiva desta tela. A previsão de volume foi adiada; o valor em reais "
        "é um cenário contrafactual com geração observada. As faixas da v3 descrevem volume e não "
        "são convertidas em classes de probabilidade de ocorrência."
    )
    metrics_path = chosen.with_suffix(".csv")
    if metrics_path.exists():
        st.dataframe(
            pl.read_csv(metrics_path).filter(pl.col("recorte") == "mes"),
            hide_index=True,
            width="stretch",
        )
