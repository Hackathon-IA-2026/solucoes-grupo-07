"""Tela Operacional D+1 do CurtaMap em Streamlit."""

from datetime import datetime, time, timedelta
import polars as pl
import streamlit as st

from curtamap.config import settings
from curtamap.contracts import RESERVED_TEST_START
from curtamap.forecasting import SameSlotRecentBaseline, known_entities, load_history, nightly_cutoff
from curtamap.ui.components import (
    render_baseline_badge,
    render_provenance_card,
    render_recommendation_card,
)
from curtamap.ui_logic import (
    filter_forecasts,
    format_no_forecast_reason,
    generate_simulated_recommendations,
    get_entity_horizon_profile,
    rank_entities_at_risk,
)


@st.cache_data(show_spinner="Carregando histórico e gerando previsões ex-ante...")
def _get_forecasts(data_dir_str: str, t0: datetime) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Lê 28 dias de histórico liberados sob o corte noturno e executa o preditor."""
    from pathlib import Path
    data_dir = Path(data_dir_str)
    raw_dir = data_dir / "raw"

    if not raw_dir.exists() or not list(raw_dir.glob("*.parquet")):
        return pl.DataFrame(), pl.DataFrame()

    corte = nightly_cutoff(t0)
    inicio = corte - timedelta(days=28)
    history = load_history(data_dir, inicio, corte)

    predictor = SameSlotRecentBaseline()
    forecasts = predictor.predict(history, t0, corte)
    entities = known_entities(history, corte)

    if not forecasts.is_empty() and not entities.is_empty():
        cols = [pl.col("fonte"), pl.col("id_ons")]
        if "id_subsistema" in entities.columns:
            cols.append(pl.col("id_subsistema").alias("subsistema"))
        elif "subsistema" in entities.columns:
            cols.append(pl.col("subsistema"))

        if "id_estado" in entities.columns:
            cols.append(pl.col("id_estado").alias("uf"))
        elif "uf" in entities.columns:
            cols.append(pl.col("uf"))

        entity_meta = entities.select(cols)
        forecasts = forecasts.join(
            entity_meta,
            on=["fonte", "id_ons"],
            how="left",
        )

    return forecasts, history


def render_operacao_page() -> None:
    """Renderiza a página principal Operacional D+1."""
    st.header("⚡ Operação D+1: Riscos e Previsões (Próximas 24 Horas)")
    st.caption("Previsão antecedente por usina/conjunto em 48 janelas de 30 minutos.")

    render_baseline_badge()

    # Controles de Emissão (t0) e Filtros na Barra Lateral
    st.sidebar.subheader("⚙️ Parâmetros da Operação")

    # Data de teste reservada limita t0 <= 2026-04-30
    max_t0_date = (RESERVED_TEST_START - timedelta(days=1)).date()
    default_date = datetime(2026, 4, 15).date()

    selected_date = st.sidebar.date_input(
        "Data de Emissão (t0)",
        value=default_date,
        max_value=max_t0_date,
        help="Instante real em que o gerador consulta a previsão para as próximas 24h.",
    )

    times = [time(h, m) for h in range(24) for m in (0, 30)]
    selected_time = st.sidebar.selectbox("Hora de Emissão (t0)", times, index=20)  # 10:00

    t0 = datetime.combine(selected_date, selected_time)

    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 Filtros de Segmentação")

    fonte_filter = st.sidebar.selectbox("Fonte de Geração", ["Todas", "eolica", "fotovoltaica"])
    subsistema_filter = st.sidebar.selectbox("Subsistema (Região)", ["Todos", "NE", "SE/CO", "S", "N"])
    uf_filter = st.sidebar.selectbox("Estado (UF)", ["Todas", "RN", "BA", "MG", "PI", "CE", "PE", "RS", "PR"])

    # Carregar previsões
    data_dir_str = str(settings.data_dir)
    forecasts, history = _get_forecasts(data_dir_str, t0)

    if forecasts.is_empty():
        st.warning(
            "⚠️ Nenhum dado de histórico foi encontrado em `data/raw/` para executar as previsões. "
            "Execute `python -m curtamap.download_data` para baixar os arquivos Parquet oficiais do ONS."
        )
        return

    # Aplicar filtros
    filtered_forecasts = filter_forecasts(
        forecasts,
        fonte=fonte_filter,
        subsistema=subsistema_filter,
        uf=uf_filter,
    )

    if filtered_forecasts.is_empty():
        st.info("Nenhuma usina atende aos filtros selecionados.")
        return

    # Ranking e Métricas
    ranked = rank_entities_at_risk(filtered_forecasts)
    total_usinas = len(ranked)
    usinas_alerta = sum(1 for r in ranked if r["total_alertas"] > 0)
    energia_risco_total = sum(r["energia_em_risco_mwh"] for r in ranked)

    # Painel de Métricas Principais
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Usinas Monitoradas", total_usinas)
    with m2:
        st.metric("Usinas em Alerta de Corte", usinas_alerta, delta=f"{usinas_alerta/total_usinas*100:.0f}% em risco" if total_usinas else "")
    with m3:
        st.metric("Energia Total em Risco (24h)", f"{energia_risco_total:,.1f} MWh")
    with m4:
        causes = [r["causa_predominante"] for r in ranked if r["causa_predominante"]]
        top_cause = max(set(causes), key=causes.count) if causes else "N/A"
        st.metric("Causa Predominante", top_cause)

    st.markdown("---")
    st.subheader("📊 Ranking de Usinas em Risco (Próximas 24 Horas)")

    # Tabela de Ranking
    table_rows = []
    for r in ranked:
        if r["tem_previsao"]:
            status = f"🔴 {r['total_alertas']} alerta(s)" if r["total_alertas"] > 0 else "🟢 Sem alerta"
            janela_str = r["primeira_janela_alerta"].strftime("%H:%M") if r["primeira_janela_alerta"] else "-"
            table_rows.append(
                {
                    "Fonte": r["fonte"].upper(),
                    "Usina / Conjunto": r["id_ons"],
                    "Status": status,
                    "Energia em Risco (MWh)": round(r["energia_em_risco_mwh"], 1),
                    "Primeiro Alerta": janela_str,
                    "Máx. Prob. Corte": f"{r['max_p_corte']*100:.0f}%" if r["max_p_corte"] is not None else "-",
                    "Causa Provável": r["causa_predominante"] or "-",
                    "Origem": r["origem_prevista"] or "-",
                }
            )
        else:
            table_rows.append(
                {
                    "Fonte": r["fonte"].upper(),
                    "Usina / Conjunto": r["id_ons"],
                    "Status": f"⚪ {format_no_forecast_reason(r['motivo_sem_previsao'])}",
                    "Energia em Risco (MWh)": "-",
                    "Primeiro Alerta": "-",
                    "Máx. Prob. Corte": "-",
                    "Causa Provável": "-",
                    "Origem": "-",
                }
            )

    st.dataframe(table_rows, use_container_width=True, hide_index=True)

    # Inspeção Detalhada por Usina
    st.markdown("---")
    st.subheader("🔍 Inspeção da Usina e Recomendação Operacional")

    entity_list = [f"{r['fonte']} | {r['id_ons']}" for r in ranked if r["tem_previsao"]]
    if not entity_list:
        st.info("Nenhuma usina com previsão ativa no momento.")
        return

    selected_entity_str = st.selectbox("Selecione a Usina para Inspecionar o Perfil das 48 Janelas:", entity_list)
    sel_fonte, sel_id_ons = [s.strip() for s in selected_entity_str.split("|")]

    # Perfil temporal de 48 janelas
    profile = get_entity_horizon_profile(filtered_forecasts, sel_fonte, sel_id_ons)

    if not profile.is_empty():
        # Gráficos de volume e probabilidade
        st.markdown(f"#### Perfil Preditivo - {sel_id_ons} ({sel_fonte.upper()})")

        pdf = profile.to_pandas()
        pdf["Hora"] = pdf["tau"].dt.strftime("%H:%M")

        tab_vol, tab_prob = st.tabs(["Volume Esp. (MWmed)", "Probabilidade de Corte (%)"])

        with tab_vol:
            st.line_chart(pdf, x="Hora", y="volume_esperado_mwmed", color="#d9534f")
            st.caption("Volume médio de corte esperado por patamar de 30 minutos.")

        with tab_prob:
            pdf["prob_perc"] = pdf["p_corte"] * 100.0
            st.line_chart(pdf, x="Hora", y="prob_perc", color="#0275d8")
            st.caption("Probabilidade estimada de corte em cada meia-hora.")

        # Recomendações para a usina selecionada
        st.markdown("---")
        sim_recs = generate_simulated_recommendations(profile)
        if not sim_recs.is_empty():
            rec_dict = sim_recs.row(0, named=True)
            render_recommendation_card(rec_dict)

        # Proveniência da Previsão
        st.markdown("---")
        render_provenance_card(profile)
