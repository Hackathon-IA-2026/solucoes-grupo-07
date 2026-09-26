"""Operação D+1: quais usinas estão em risco nas próximas 24 h e o que fazer."""

import polars as pl
import streamlit as st

from curtamap.painel.ranking import (
    STATUS_ALERT,
    STATUS_NO_EVIDENCE,
    filter_ranking,
    rank_entities,
    window_profile,
)
from curtamap.painel.resumo import operational_summary, ranking_totals
from curtamap.painel.rotulos import (
    SOURCE_LABELS,
    cause_label,
    describe_reason,
    format_mwh,
    format_number,
)
from curtamap.ui import contexto, dados, graficos

_STATUS_ICON = {STATUS_ALERT: "🔴 em risco", STATUS_NO_EVIDENCE: "⚪ sem evidência"}


def _options(ranking: pl.DataFrame, column: str) -> list[str]:
    return sorted(ranking[column].drop_nulls().unique().to_list())


def _filters(ranking: pl.DataFrame) -> pl.DataFrame:
    fonte, uf, sub = st.columns(3)
    fontes = fonte.multiselect(
        "Fonte",
        _options(ranking, "fonte"),
        format_func=lambda s: SOURCE_LABELS.get(s, s),
        placeholder="Todas",
    )
    ufs = uf.multiselect("UF", _options(ranking, "id_estado"), placeholder="Todas")
    subsistemas = sub.multiselect(
        "Subsistema", _options(ranking, "id_subsistema"), placeholder="Todos"
    )
    return filter_ranking(ranking, fontes=fontes, ufs=ufs, subsistemas=subsistemas)


def _headline(ranking: pl.DataFrame) -> None:
    totals = ranking_totals(ranking)
    a, b, c, d = st.columns(4)
    a.metric("Usinas em risco", f"{totals.at_risk} de {totals.entities}")
    b.metric(
        "Energia em risco (24 h)",
        format_mwh(totals.energy_at_risk_mwh),
        help="Soma da energia esperada nas janelas em alerta, só com volumes conhecidos."
        + (
            f" {totals.at_risk_unknown_energy} usina(s) em alerta com volume desconhecido "
            "ficam fora da soma."
            if totals.at_risk_unknown_energy
            else ""
        ),
    )
    c.metric(
        "Primeiro alerta",
        f"{totals.first_alert:%d/%m %H:%M}" if totals.first_alert else "—",
    )
    d.metric(
        "Sem evidência",
        totals.no_evidence,
        help="Usinas sem nenhuma janela prevista. Não entram como zero em nenhuma soma.",
    )


def _table(ranking: pl.DataFrame, baseline: bool, example_actions: bool) -> pl.DataFrame:
    """Só formatação de exibição; nulos aparecem como texto explícito."""
    return ranking.select(
        pl.col("status").replace(_STATUS_ICON).alias("Status"),
        pl.coalesce("nom_usina", pl.concat_str("fonte", pl.lit("/"), "id_ons")).alias("Usina"),
        pl.col("fonte").replace(SOURCE_LABELS).alias("Fonte"),
        pl.col("id_estado").alias("UF"),
        pl.col("id_subsistema").alias("Subsistema"),
        pl.col("energia_em_risco_mwh").alias("Energia em risco (MWh)"),
        pl.col("primeira_janela_alerta").alias("Primeira janela"),
        pl.col("causa_provavel")
        .map_elements(cause_label, return_dtype=pl.String)
        .fill_null("—")
        .alias("Causa provável"),
        pl.col("causa_mista").alias("Causa mista"),
        (pl.lit(None, pl.Float64) if baseline else pl.col("confianca")).alias("Confiança"),
        pl.col("acao_codigo")
        .fill_null("aguarda Etapa 3" if example_actions else "—")
        .alias("Ação sugerida"),
        pl.col("janelas_sem_evidencia").alias("Janelas sem evidência"),
        pl.col("motivo_sem_previsao")
        .map_elements(describe_reason, return_dtype=pl.String)
        .alias("Motivo sem previsão"),
        pl.col("id_ons").alias("id_ons"),
    )


def _ranking_section(ranking: pl.DataFrame, baseline: bool, example_actions: bool) -> None:
    st.subheader("Usinas por risco nas próximas 24 h")
    st.caption(
        "Ordenação: em risco (maior energia primeiro), depois sem evidência, depois sem "
        "alerta. A chave é fonte + id_ons."
        + (" Confiança omitida: o baseline só produz 0 ou 1." if baseline else "")
    )
    st.dataframe(
        _table(ranking, baseline, example_actions),
        hide_index=True,
        use_container_width=True,
        height=420,
        column_config={
            "Energia em risco (MWh)": st.column_config.NumberColumn(format="%.1f"),
            "Primeira janela": st.column_config.DatetimeColumn(format="DD/MM HH:mm"),
            "Confiança": st.column_config.ProgressColumn(
                format="percent", min_value=0.0, max_value=1.0,
                help="p(corte) médio nas janelas em alerta.",
            ),
            "Causa mista": st.column_config.CheckboxColumn(
                help="Mais de uma causa prevista entre as janelas em alerta."
            ),
        },
    )  # fmt: skip


def _profile_section(context: contexto.Context, ranking: pl.DataFrame) -> None:
    st.subheader("Perfil das 48 janelas")
    if ranking.is_empty():
        st.info("Nenhuma usina com os filtros atuais.")
        return
    keys = list(zip(ranking["fonte"], ranking["id_ons"], strict=True))
    names = dict(zip(keys, ranking["nom_usina"], strict=True))
    fonte, id_ons = st.selectbox(
        "Usina",
        keys,
        format_func=lambda k: f"{names[k] or k[1]} · {SOURCE_LABELS.get(k[0], k[0])} · {k[1]}",
    )
    profile = window_profile(context.bundle.forecast, fonte, id_ons)
    row = ranking.filter((pl.col("fonte") == fonte) & (pl.col("id_ons") == id_ons)).row(
        0, named=True
    )
    if row["status"] == STATUS_NO_EVIDENCE:
        st.warning(
            f"Sem evidência para prever esta usina: {describe_reason(row['motivo_sem_previsao'])}."
            " As janelas aparecem sombreadas, sem valor, e nunca como zero."
        )
    has_interval = profile["volume_p10_mwmed"].is_not_null().any()
    st.plotly_chart(
        graficos.energy_profile(profile, has_interval=has_interval), use_container_width=True
    )
    st.plotly_chart(graficos.probability_profile(profile), use_container_width=True)
    with st.expander("Tabela das 48 janelas"):
        st.dataframe(
            profile.select(
                pl.col("tau").alias("Janela"),
                "status",
                "p_corte",
                "energia_esperada_mwh",
                (pl.col("volume_p10_mwmed") * 0.5).alias("p10 (MWh)"),
                (pl.col("volume_p90_mwmed") * 0.5).alias("p90 (MWh)"),
                "causa_prevista",
                "p_causa_rel",
                "p_causa_cnf",
                "p_causa_ene",
                pl.col("motivo_sem_previsao").map_elements(describe_reason, return_dtype=pl.String),
                pl.col("motivo_sem_causa").map_elements(describe_reason, return_dtype=pl.String),
            ),
            hide_index=True,
            use_container_width=True,
        )


def _actions_section(recs: dados.Recommendations) -> None:
    st.subheader("Ações sugeridas")
    if recs.is_example:
        st.warning(
            "🧪 **EXEMPLO SIMULADO — não são recomendações reais.** O módulo de recomendação "
            "(Etapa 3) ainda não está no `main`. As linhas abaixo usam usinas fictícias "
            "`EXEMPLO-*` e números escritos à mão só para mostrar o formato do painel."
        )
    frame = recs.frame.select(
        pl.col("id_ons").alias("Usina"),
        pl.col("fonte").replace(SOURCE_LABELS).alias("Fonte"),
        pl.col("inicio").alias("Início"),
        pl.col("fim").alias("Fim"),
        pl.col("causa_base")
        .map_elements(cause_label, return_dtype=pl.String)
        .fill_null("indeterminada")
        .alias("Causa"),
        pl.col("acao_codigo").alias("Ação"),
        pl.col("acao_descricao").alias("Descrição"),
        pl.col("energia_em_risco_mwh").alias("Em risco (MWh)"),
        pl.col("energia_recuperavel_mwh").alias("Recuperável (MWh, cenário)"),
        pl.col("valor_estimado_brl").alias("Valor (R$, cenário)"),
        pl.col("co2_evitado_t").alias("CO₂ evitado (t, cenário)"),
        pl.col("tipo_saida").alias("Tipo"),
        pl.col("premissas_versao").alias("Premissas"),
    )
    st.dataframe(
        frame,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Início": st.column_config.DatetimeColumn(format="DD/MM HH:mm"),
            "Fim": st.column_config.DatetimeColumn(format="DD/MM HH:mm"),
        },
    )
    st.caption(
        "Energia recuperável, valor e CO₂ são cenários sob premissas versionadas, não "
        "garantias. Valor ou CO₂ vazios significam premissa sem fonte."
    )


def render() -> None:
    context = contexto.current()
    if context is None:
        return
    st.title("Operação D+1")
    recs = dados.recommendations_for(context.t0)
    ranking_all = rank_entities(context.bundle.forecast, context.bundle.entities, recs.frame)
    ranking = _filters(ranking_all)
    _headline(ranking)
    with st.container(border=True):
        st.markdown("**Resumo do dia** · texto gerado por regras a partir dos números abaixo")
        st.write(operational_summary(ranking, context.provenance))
    _ranking_section(ranking, context.provenance.is_baseline, recs.is_example)
    _profile_section(context, ranking)
    _actions_section(recs)
    st.caption(
        f"{format_number(context.provenance.windows, 0)} janelas previstas para "
        f"{context.provenance.entities} usinas. Detalhes em Metodologia e limites."
    )
