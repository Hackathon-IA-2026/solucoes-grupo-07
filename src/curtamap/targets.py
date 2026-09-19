"""Alvo GNR analítico v1: MWmed e MWh em patamares observados de 30 minutos.

Não calcula compensação financeira. Preserva originais; inválidos têm volume nulo.
A variante bruta mantém negativos finitos exclusivamente para sensibilidade.
"""

import polars as pl

CAUSES = ("REL", "CNF", "ENE", "PAR")
ORIGINS = ("LOC", "SIS")
NUMERIC = ("val_geracaolimitada", "val_geracaoreferencia", "val_geracao")
# Mesmo conjunto nos dois backends: trim() do DuckDB, sem argumento, não remove tab/quebra.
BLANKS = " \t\n\r"
BLANKS_SQL = "' ' || chr(9) || chr(10) || chr(13)"


def derive_targets(data: pl.DataFrame) -> pl.DataFrame:
    """Função pura: não preenche grade temporal nem remove ou altera linhas."""
    if data["fonte"].null_count() or not data["fonte"].is_in(["eolica", "fotovoltaica"]).all():
        raise ValueError("fonte deve ser eolica ou fotovoltaica")
    limited = pl.col("val_geracaolimitada").is_not_null()
    negative = pl.any_horizontal([(pl.col(c) < 0).fill_null(False) for c in NUMERIC])
    nonfinite = pl.any_horizontal(
        [(pl.col(c).is_not_null() & ~pl.col(c).is_finite()).fill_null(False) for c in NUMERIC]
    )
    missing = pl.col("val_geracaoreferencia").is_null() | pl.col("val_geracao").is_null()
    valid = ~missing & ~negative & ~nonfinite
    raw = (pl.col("val_geracaoreferencia") - pl.col("val_geracao")).clip(lower_bound=0)
    volume = pl.when(~limited).then(0.0).when(valid).then(raw).otherwise(None)
    brute = pl.when(~limited).then(0.0).when(~missing & ~nonfinite).then(raw * 0.5).otherwise(None)
    cause = pl.col("cod_razaorestricao").str.strip_chars(BLANKS).str.to_uppercase()
    origin = pl.col("cod_origemrestricao").str.strip_chars(BLANKS).str.to_uppercase()
    return data.with_columns(
        limited.alias("restricao_registrada"),
        volume.alias("volume_mwmed"),
        (volume * 0.5).alias("energia_mwh"),
        brute.alias("energia_bruta_mwh"),
        (volume > 0).alias("corte_positivo"),
        negative.alias("entrada_negativa"),
        nonfinite.alias("entrada_nao_finita"),
        (limited & missing).alias("entrada_ausente"),
        ((~limited) | valid).alias("volume_valido"),
        (limited & ~cause.is_in(CAUSES).fill_null(False)).alias("razao_desconhecida"),
        (limited & ~origin.is_in(ORIGINS).fill_null(False)).alias("origem_desconhecida"),
        # Texto vazio é representação de ausência na publicação ONS, não rótulo.
        ((~limited) & ((cause != "") | (origin != "")).fill_null(False)).alias("rotulo_sem_limite"),
        pl.when(~limited)
        .then(None)
        .when(cause.is_in(CAUSES))
        .then(cause)
        .otherwise(pl.lit("DESCONHECIDA"))
        .alias("causa"),
        pl.when(~limited)
        .then(None)
        .when(origin.is_in(ORIGINS))
        .then(origin)
        .otherwise(pl.lit("DESCONHECIDA"))
        .alias("origem"),
    )


def target_sql() -> str:
    """Projeção DuckDB equivalente, testada contra a implementação Polars."""
    limited = "(val_geracaolimitada IS NOT NULL)"
    negative = "(" + " OR ".join(f"coalesce({c}<0,false)" for c in NUMERIC) + ")"
    nonfinite = "(" + " OR ".join(f"coalesce(NOT isfinite({c}),false)" for c in NUMERIC) + ")"
    missing = "(val_geracaoreferencia IS NULL OR val_geracao IS NULL)"
    valid = f"(NOT {missing} AND NOT {negative} AND NOT {nonfinite})"
    raw = "greatest(val_geracaoreferencia-val_geracao,0)"
    volume = f"(CASE WHEN NOT {limited} THEN 0 WHEN {valid} THEN {raw} ELSE NULL END)"
    brute = (
        f"(CASE WHEN NOT {limited} THEN 0 WHEN NOT {missing} AND NOT {nonfinite} "
        f"THEN {raw}*0.5 ELSE NULL END)"
    )
    cause = f"upper(trim(cod_razaorestricao,{BLANKS_SQL}))"
    origin = f"upper(trim(cod_origemrestricao,{BLANKS_SQL}))"
    known_cause = f"coalesce({cause} IN {CAUSES},false)"
    known_origin = f"coalesce({origin} IN {ORIGINS},false)"
    expressions = {
        "restricao_registrada": limited,
        "volume_mwmed": volume,
        "energia_mwh": f"{volume}*0.5",
        "energia_bruta_mwh": brute,
        "corte_positivo": f"{volume}>0",
        "entrada_negativa": negative,
        "entrada_nao_finita": nonfinite,
        "entrada_ausente": f"{limited} AND {missing}",
        "volume_valido": f"NOT {limited} OR {valid}",
        "razao_desconhecida": f"{limited} AND NOT {known_cause}",
        "origem_desconhecida": f"{limited} AND NOT {known_origin}",
        "rotulo_sem_limite": f"NOT {limited} AND coalesce({cause}<>'' OR {origin}<>'',false)",
        "causa": f"CASE WHEN NOT {limited} THEN NULL WHEN {known_cause} THEN {cause} "
        "ELSE 'DESCONHECIDA' END",
        "origem": f"CASE WHEN NOT {limited} THEN NULL WHEN {known_origin} THEN {origin} "
        "ELSE 'DESCONHECIDA' END",
    }
    return ",\n".join(f"{expr} AS {name}" for name, expr in expressions.items())
