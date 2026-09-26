"""Perdas observadas para a visão tática: energia cortada por período e por um recorte.

Agregação mínima sobre a saída de `derive_targets`, até a Etapa 3 entregar a sua. Só
entram meias-horas com limitação registrada. `energia_mwh` soma apenas volumes válidos; as
meias-horas com volume inválido ficam contadas em `janelas_volume_nulo`, nunca somadas
como zero.
"""

from datetime import datetime

import polars as pl

from curtamap.contracts import RESERVED_TEST_START

GRAINS = {"semana": "1w", "mes": "1mo"}
DIMENSIONS = ("causa", "fonte", "id_estado", "id_subsistema", "usina")
MISSING = "não informado"


def _group(dimension: str) -> pl.Expr:
    if dimension == "usina":
        key = pl.concat_str("fonte", pl.lit("/"), "id_ons")
        return (
            pl.when(pl.col("nom_usina").is_not_null())
            .then(pl.concat_str("nom_usina", pl.lit(" · "), key))
            .otherwise(key)
        )
    return pl.col(dimension).fill_null(MISSING)


def historical_losses(
    history: pl.DataFrame,
    *,
    grain: str,
    dimension: str,
    window: tuple[datetime, datetime] | None = None,
) -> pl.DataFrame:
    """`window` é o intervalo `[início, fim)` carregado; marca períodos cortados por ele."""
    if grain not in GRAINS:
        raise ValueError(f"grain deve ser um de {tuple(GRAINS)}")
    if dimension not in DIMENSIONS:
        raise ValueError(f"dimension deve ser uma de {DIMENSIONS}")
    if history.filter(pl.col("din_instante") >= RESERVED_TEST_START).height:
        raise ValueError(
            f"histórico inclui o período reservado (a partir de {RESERVED_TEST_START:%d/%m/%Y})"
        )
    every = GRAINS[grain]
    start = pl.col("din_instante").dt.truncate(every)
    partial = pl.lit(None, pl.Boolean)
    if window is not None:
        partial = (start < window[0]) | (start.dt.offset_by(every) > window[1])
    return (
        history.filter(pl.col("restricao_registrada"))
        .with_columns(
            start.dt.date().alias("periodo"),
            _group(dimension).alias("grupo"),
            partial.alias("periodo_parcial"),
        )
        .group_by("periodo", "grupo", "periodo_parcial")
        .agg(
            pl.col("energia_mwh").sum(),
            pl.col("corte_positivo").fill_null(False).sum().alias("janelas_com_corte"),
            pl.col("energia_mwh").is_null().sum().alias("janelas_volume_nulo"),
            pl.struct("fonte", "id_ons").n_unique().alias("usinas"),
        )
        .sort(["periodo", "energia_mwh", "grupo"], descending=[False, True, False])
    )
