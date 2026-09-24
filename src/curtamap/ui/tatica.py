"""Tela de Visão Tática de Perdas Históricas do CurtaMap."""

from datetime import datetime
import polars as pl
import streamlit as st

from curtamap.config import settings
from curtamap.forecasting import load_history
from curtamap.ui.components import render_baseline_badge
from curtamap.ui_logic import compute_tactical_history_summary


@st.cache_data(show_spinner="Agregando histórico de perdas registradas...")
def _get_historical_summary(data_dir_str: str) -> pl.DataFrame:
    from pathlib import Path
    data_dir = Path(data_dir_str)
    raw_dir = data_dir / "raw"

    if not raw_dir.exists() or not list(raw_dir.glob("*.parquet")):
        return pl.DataFrame()

    # Carregar uma janela histórica recente (ex: 2025/2026)
    history = load_history(data_dir, datetime(2025, 1, 1), datetime(2026, 4, 30))
    return compute_tactical_history_summary(history)


def render_tatica_page() -> None:
    """Renderiza a visão tática de perdas históricas."""
    st.header("📈 Visão Tática: Histórico de Perdas por Regime e Causa")
    st.caption("Resumo agregado de perdas observadas por mês, subsistema, estado e causa de corte.")

    render_baseline_badge()

    summary = _get_historical_summary(str(settings.data_dir))

    if summary.is_empty():
        st.warning(
            "⚠️ Nenhum dado histórico disponível em `data/raw/`. "
            "Execute `python -m curtamap.download_data` para obter a base histórica do ONS."
        )
        return

    # Métricas globais históricas
    total_mwh = summary.select(pl.col("corte_mwh").sum()).item()
    intervalos_total = summary.select(pl.col("intervalos_com_corte").sum()).item()

    # Causa com maior impacto
    by_cause = (
        summary.group_by("razao_limite")
        .agg(pl.col("corte_mwh").sum().alias("total"))
        .sort("total", descending=True)
    )
    top_cause = by_cause["razao_limite"][0] if len(by_cause) > 0 else "N/A"
    top_cause_mwh = by_cause["total"][0] if len(by_cause) > 0 else 0.0

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Total Cortado no Período", f"{total_mwh:,.1f} MWh")
    with m2:
        st.metric("Intervalos de 30min com Corte", f"{intervalos_total:,}")
    with m3:
        st.metric("Causa Dominante", f"{top_cause}", delta=f"{top_cause_mwh:,.1f} MWh")

    st.markdown("---")
    st.subheader("📊 Perdas de Energia (MWh) por Causa ao Longo do Tempo")

    # Tabela agregada por Mês e Causa
    monthly_cause = (
        summary.group_by(["mes", "razao_limite"])
        .agg(pl.col("corte_mwh").sum().round(1).alias("corte_mwh"))
        .sort(["mes", "razao_limite"])
    )

    pdf_month = monthly_cause.to_pandas()
    pdf_month["Mês"] = pdf_month["mes"].dt.strftime("%Y-%m")

    # Pivot para gráfico de barras empilhadas
    pivoted = pdf_month.pivot(index="Mês", columns="razao_limite", values="corte_mwh").fillna(0.0)
    st.bar_chart(pivoted)

    st.markdown("---")
    st.subheader("📋 Tabela Consolidada de Histórico Tático")

    pdf_summary = summary.to_pandas()
    pdf_summary["Mês"] = pdf_summary["mes"].dt.strftime("%Y-%m")
    pdf_summary = pdf_summary.rename(
        columns={
            "fonte": "Fonte",
            "razao_limite": "Causa (Razão)",
            "subsistema": "Subsistema",
            "uf": "UF",
            "corte_mwh": "Corte Acumulado (MWh)",
            "intervalos_com_corte": "Janelas c/ Corte",
        }
    )

    st.dataframe(
        pdf_summary[["Mês", "Fonte", "Causa (Razão)", "Subsistema", "UF", "Corte Acumulado (MWh)", "Janelas c/ Corte"]],
        use_container_width=True,
        hide_index=True,
    )
