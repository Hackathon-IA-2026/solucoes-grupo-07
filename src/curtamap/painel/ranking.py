"""Ranking operacional D+1: quais usinas estão em risco nas próximas 24 h e por quê.

A chave é sempre `fonte + id_ons`. Previsão nula nunca vira zero: uma usina sem nenhuma
janela prevista fica "sem evidência", com o motivo do contrato, e uma janela em alerta com
volume desconhecido deixa a energia em risco da usina desconhecida.
"""

from collections.abc import Sequence

import polars as pl

STATUS_ALERT = "em risco"
STATUS_NO_EVIDENCE = "sem evidência"
STATUS_NO_ALERT = "sem alerta"
_STATUS_ORDER = {STATUS_ALERT: 0, STATUS_NO_EVIDENCE: 1, STATUS_NO_ALERT: 2}
_KEY = ["fonte", "id_ons"]
_ATTRIBUTES = ["nom_usina", "id_estado", "id_subsistema"]


def _known_sum(values: pl.Expr) -> pl.Expr:
    """Soma que fica nula se algum termo for nulo ou se não houver termos."""
    return pl.when((values.null_count() == 0) & (values.len() > 0)).then(values.sum())


def _main_cause(forecast: pl.DataFrame) -> pl.DataFrame:
    """Causa com mais energia nas janelas em alerta (desempate: janelas, depois código)."""
    return (
        forecast.filter(pl.col("alerta") & pl.col("causa_prevista").is_not_null())
        .group_by([*_KEY, "causa_prevista"])
        .agg(pl.col("energia_esperada_mwh").fill_null(0.0).sum().alias("_e"), pl.len().alias("_n"))
        .sort([*_KEY, "_e", "_n", "causa_prevista"], descending=[False, False, True, True, False])
        .group_by(_KEY, maintain_order=True)
        .agg(
            pl.col("causa_prevista").first().alias("causa_provavel"),
            (pl.len() > 1).alias("causa_mista"),
        )
    )


def _first_action(recommendations: pl.DataFrame | None, t0s: pl.Series) -> pl.DataFrame:
    schema = {**dict.fromkeys(_KEY, pl.String), "t0": t0s.dtype}
    schema |= dict.fromkeys(["acao_codigo", "acao_descricao", "acao_tipo_saida"], pl.String)
    if recommendations is None or recommendations.is_empty():
        return pl.DataFrame(schema=schema)
    return (
        recommendations.filter(pl.col("t0").is_in(t0s.unique().implode()))
        .sort([*_KEY, "t0", "inicio", "acao_codigo"])
        .group_by([*_KEY, "t0"], maintain_order=True)
        .agg(
            pl.col("acao_codigo").first(),
            pl.col("acao_descricao").first(),
            pl.col("tipo_saida").first().alias("acao_tipo_saida"),
        )
    )


def rank_entities(
    forecast: pl.DataFrame,
    attributes: pl.DataFrame,
    recommendations: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Uma linha por `fonte + id_ons + t0`, ordenada pela decisão que o gerador precisa tomar.

    `energia_em_risco_mwh` soma a energia esperada das janelas em alerta (a mesma regra dos
    episódios da recomendação); `confianca` é o `p_corte` médio dessas janelas.
    """
    alert = pl.col("alerta").fill_null(False)
    energy = pl.col("energia_esperada_mwh")
    has_evidence = pl.col("p_corte").is_not_null()
    summary = forecast.group_by([*_KEY, "t0"]).agg(
        alert.sum().cast(pl.Int32).alias("janelas_alerta"),
        (~has_evidence).sum().cast(pl.Int32).alias("janelas_sem_evidencia"),
        has_evidence.any().alias("_tem_evidencia"),
        _known_sum(energy.filter(alert)).alias("_energia_alerta"),
        pl.when(energy.is_not_null().any()).then(energy.sum()).alias("energia_esperada_24h_mwh"),
        pl.col("tau").filter(alert).min().alias("primeira_janela_alerta"),
        pl.col("p_corte").filter(alert).mean().alias("confianca"),
        pl.col("motivo_sem_previsao")
        .drop_nulls()
        .mode()
        .sort()
        .first()
        .alias("motivo_sem_previsao"),
    )
    status = (
        pl.when(pl.col("janelas_alerta") > 0)
        .then(pl.lit(STATUS_ALERT))
        .when(~pl.col("_tem_evidencia"))
        .then(pl.lit(STATUS_NO_EVIDENCE))
        .otherwise(pl.lit(STATUS_NO_ALERT))
    )
    at_risk = (
        pl.when(pl.col("janelas_alerta") > 0)
        .then(pl.col("_energia_alerta"))
        .when(pl.col("_tem_evidencia"))
        .then(0.0)
    )
    ranked = (
        summary.with_columns(status.alias("status"), at_risk.alias("energia_em_risco_mwh"))
        .join(attributes.select([*_KEY, *_ATTRIBUTES]), on=_KEY, how="left")
        .join(_main_cause(forecast), on=_KEY, how="left")
        .join(_first_action(recommendations, forecast["t0"]), on=[*_KEY, "t0"], how="left")
        .with_columns(
            pl.col("causa_mista").fill_null(False),
            pl.col("status").replace_strict(_STATUS_ORDER).alias("_ordem"),
        )
        .sort(
            ["_ordem", "energia_em_risco_mwh", "primeira_janela_alerta", *_KEY],
            descending=[False, True, False, False, False],
            nulls_last=True,
        )
    )
    return ranked.select(
        *_KEY,
        "t0",
        *_ATTRIBUTES,
        "status",
        "energia_em_risco_mwh",
        "primeira_janela_alerta",
        "causa_provavel",
        "causa_mista",
        "confianca",
        "janelas_alerta",
        "janelas_sem_evidencia",
        "energia_esperada_24h_mwh",
        "motivo_sem_previsao",
        "acao_codigo",
        "acao_descricao",
        "acao_tipo_saida",
    )


def filter_ranking(
    ranking: pl.DataFrame,
    *,
    fontes: Sequence[str] = (),
    ufs: Sequence[str] = (),
    subsistemas: Sequence[str] = (),
) -> pl.DataFrame:
    """Filtro vazio não restringe; atributo nulo só passa quando o campo não está filtrado."""
    condition = pl.lit(True)
    for column, chosen in (("fonte", fontes), ("id_estado", ufs), ("id_subsistema", subsistemas)):
        if chosen:
            condition &= pl.col(column).is_in(list(chosen)).fill_null(False)
    return ranking.filter(condition)


def window_profile(forecast: pl.DataFrame, fonte: str, id_ons: str) -> pl.DataFrame:
    """As 48 janelas de uma usina, cada uma com o estado mostrado ao usuário."""
    status = (
        pl.when(pl.col("p_corte").is_null())
        .then(pl.lit(STATUS_NO_EVIDENCE))
        .when(pl.col("alerta"))
        .then(pl.lit(STATUS_ALERT))
        .otherwise(pl.lit(STATUS_NO_ALERT))
    )
    return (
        forecast.filter((pl.col("fonte") == fonte) & (pl.col("id_ons") == id_ons))
        .sort("horizonte")
        .with_columns(status.alias("status"))
    )
