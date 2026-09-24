"""Componentes visuais reutilizáveis para a interface do CurtaMap em Streamlit."""

from datetime import datetime
import polars as pl
import streamlit as st


def render_baseline_badge() -> None:
    """Exibe o selo global de aviso do Preditor Provisório Baseline."""
    st.info(
        "⚡ **Modo de Operação Provisório:** As previsões exibidas nesta tela utilizam o "
        "preditor de referência `SameSlotRecentBaseline` (última observação no mesmo horário com latência ONS). "
        "Este modelo provisório define o benchmark a ser superado pelos modelos definitivos de Machine Learning."
    )


def render_provenance_card(forecasts: pl.DataFrame) -> None:
    """Renderiza os metadados de proveniência do contrato de dados."""
    if forecasts.is_empty():
        return

    first = forecasts.row(0, named=True)

    corte_dados = first.get("corte_dados")
    cenario_disp = first.get("cenario_disponibilidade")
    gerado_em = first.get("gerado_em")
    instante_obs = first.get("instante_observacao")
    cobertura = first.get("cobertura_historico")
    tipo_saida = first.get("tipo_saida", "baseline")
    modelo_id = first.get("modelo_id", "SameSlotRecentBaseline")

    st.markdown("### 📋 Proveniência e Auditoria da Previsão")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Tipo de Saída", tipo_saida.upper())
        st.caption(f"ID do Modelo: `{modelo_id}`")

    with c2:
        val_corte = corte_dados.strftime("%d/%m/%Y %H:%M") if isinstance(corte_dados, datetime) else str(corte_dados)
        st.metric("Corte de Dados", val_corte)
        st.caption(f"Cenário: `{cenario_disp}`")

    with c3:
        val_obs = instante_obs.strftime("%d/%m/%Y %H:%M") if isinstance(instante_obs, datetime) else str(instante_obs or "N/A")
        st.metric("Dado Histórico Usado", val_obs)
        st.caption("Última observação liberada ex-ante")

    with c4:
        val_cob = f"{cobertura * 100:.1f}%" if cobertura is not None else "100%"
        st.metric("Cobertura de Histórico", val_cob)
        val_gerado = gerado_em.strftime("%d/%m/%Y %H:%M") if isinstance(gerado_em, datetime) else str(gerado_em or "N/A")
        st.caption(f"Emissão: {val_gerado}")


def render_recommendation_card(rec: dict) -> None:
    """Exibe o painel de recomendação com destaque visual e aviso de fixture simulada."""
    st.markdown(
        """
        <div style="background-color: #f0f7ff; border-left: 5px solid #0066cc; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
            <span style="background-color: #0066cc; color: white; padding: 3px 8px; border-radius: 3px; font-size: 0.8em; font-weight: bold;">
                ⚠️ EXEMPLO SIMULADO (Etapa 3 em andamento)
            </span>
            <h4 style="margin-top: 10px; color: #003366;">💡 Recomendação Sugerida</h4>
        </div>
        """,
        unsafe_allow_html=True,
    )

    causa = rec.get("causa_base", "ENE")
    acao_cod = rec.get("acao_codigo", "REC_ENE_01")
    acao_desc = rec.get("acao_descricao", "Reprogramar despacho operacional")

    e_risco = rec.get("energia_em_risco_mwh", 0.0)
    e_rec = rec.get("energia_recuperavel_mwh", 0.0)
    val_brl = rec.get("valor_estimado_brl", 0.0)
    co2 = rec.get("co2_evitado_t", 0.0)

    st.write(f"**Causa Base:** `{causa}` | **Ação (`{acao_cod}`):** {acao_desc}")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Energia em Risco", f"{e_risco:,.1f} MWh")
    with col2:
        st.metric("Energia Recuperável (Est.)", f"{e_rec:,.1f} MWh")
    with col3:
        st.metric("Valor Estimado", f"R$ {val_brl:,.2f}")
    with col4:
        st.metric("CO₂ Evitado", f"{co2:,.1f} tCO₂")

    st.caption("Nota: Estimativas financeiras e ambientais baseiam-se em premissas simuladas rastreáveis (v1-simulada).")
