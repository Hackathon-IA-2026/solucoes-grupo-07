from __future__ import annotations

from datetime import datetime, timedelta

import polars as pl

CAUSE_ORDER = ("CNF", "ENE", "REL")
MINIMUM_GROUP_SUPPORT = 7
BASELINE_ORDER = (
    "ultimo_valor",
    "mesmo_horario_dia_anterior",
    "mesmo_horario_recente",
    "historico",
)
# Hierarquia do fallback estatístico (protocolo §7.1), do grupo mais específico ao geral.
FALLBACK_LEVELS = (
    ("entidade_mesmo_horario", ("fonte", "id_ons", "_slot")),
    ("entidade_todos_horarios", ("fonte", "id_ons")),
    ("fonte_uf_mesmo_horario", ("fonte", "id_estado", "_slot")),
    ("fonte_mesmo_horario", ("fonte", "_slot")),
    ("fonte_todos_horarios", ("fonte",)),
)
HISTORY_COLUMNS = (
    "fonte",
    "id_ons",
    "id_estado",
    "din_instante",
    "disponivel_em",
    "restricao_registrada",
    "corte_positivo",
    "volume_mwmed",
    "volume_valido",
    "causa",
)
CAUSE_STRUCT = pl.Struct({cause: pl.Float64 for cause in CAUSE_ORDER})
VALUE_COLUMNS = (
    "prob_positive",
    "prob_restriction",
    "volume_positive_mean",
    "volume_expected",
    "cause_prediction",
    "cause_probabilities",
)


def _slot(expression: pl.Expr) -> pl.Expr:
    return expression.dt.hour().cast(pl.Int32) * 60 + expression.dt.minute().cast(pl.Int32)


def _hours(expression: pl.Expr) -> pl.Expr:
    return expression.dt.total_microseconds().cast(pl.Float64) / 3_600_000_000


def _group_statistics(available: pl.DataFrame, keys: tuple[str, ...], level: int) -> pl.DataFrame:
    """Contagens suficientes para reproduzir ``_statistics`` em cada grupo da hierarquia."""
    suffix = f"_{level}"
    volume_valid = pl.col("volume_valido").fill_null(False) & pl.col("volume_mwmed").is_not_null()
    positive_volume = volume_valid & (pl.col("volume_mwmed") > 0)
    known = pl.col("restricao_registrada").fill_null(False) & pl.col("causa").is_in(CAUSE_ORDER)
    return available.group_by(list(keys)).agg(
        pl.len().alias(f"rows{suffix}"),
        pl.col("corte_positivo").is_not_null().sum().alias(f"positive_valid{suffix}"),
        pl.col("corte_positivo").fill_null(False).sum().alias(f"positive_sum{suffix}"),
        volume_valid.sum().alias(f"volume_valid{suffix}"),
        positive_volume.sum().alias(f"positive_count{suffix}"),
        pl.col("volume_mwmed").filter(positive_volume).sum().alias(f"positive_volume{suffix}"),
        pl.col("restricao_registrada").fill_null(False).sum().alias(f"restriction_sum{suffix}"),
        *[
            (known & (pl.col("causa") == cause)).sum().alias(f"cause_{cause}{suffix}")
            for cause in CAUSE_ORDER
        ],
        pl.col("din_instante").max().alias(f"last_time{suffix}"),
    )


def _choose(level_expressions: list[tuple[pl.Expr, pl.Expr]], default: pl.Expr) -> pl.Expr:
    chained = pl.when(level_expressions[0][0]).then(level_expressions[0][1])
    for condition, value in level_expressions[1:]:
        chained = chained.when(condition).then(value)
    return chained.otherwise(default)


def _historical_fallback(requests: pl.DataFrame, available: pl.DataFrame) -> pl.DataFrame:
    """Reproduz ``_fallback``: primeiro grupo com sete observações válidas por tarefa."""
    frame = requests
    for level, (_name, keys) in enumerate(FALLBACK_LEVELS):
        frame = frame.join(
            _group_statistics(available, keys, level),
            on=list(keys),
            how="left",
            nulls_equal=True,
        )
    usable = [
        (pl.col(f"positive_valid_{level}") >= MINIMUM_GROUP_SUPPORT)
        & (pl.col(f"volume_valid_{level}") >= MINIMUM_GROUP_SUPPORT)
        for level in range(len(FALLBACK_LEVELS))
    ]
    usable = [condition.fill_null(False) for condition in usable]

    def pick(column: str, default: pl.Expr) -> pl.Expr:
        return _choose(
            [(usable[level], pl.col(f"{column}_{level}")) for level in range(len(FALLBACK_LEVELS))],
            default,
        )

    frame = frame.with_columns(
        pick("positive_valid", pl.lit(None, pl.UInt32)).alias("_positive_valid"),
        pick("positive_sum", pl.lit(None, pl.UInt32)).alias("_positive_sum"),
        pick("positive_count", pl.lit(None, pl.UInt32)).alias("_positive_count"),
        pick("positive_volume", pl.lit(None, pl.Float64)).alias("_positive_volume"),
        pick("restriction_sum", pl.lit(None, pl.UInt32)).alias("_restriction_sum"),
        pick("rows", pl.lit(None, pl.UInt32)).alias("_rows"),
        *[
            pick(f"cause_{cause}", pl.lit(None, pl.UInt32)).alias(f"_cause_{cause}")
            for cause in CAUSE_ORDER
        ],
        pick("last_time", pl.col(f"last_time_{len(FALLBACK_LEVELS) - 1}")).alias("fallback_time"),
        _choose(
            [(usable[level], pl.lit(name)) for level, (name, _keys) in enumerate(FALLBACK_LEVELS)],
            pl.lit("sem_evidencia"),
        ).alias("fallback_level"),
    )
    informed = pl.col("fallback_level") != "sem_evidencia"
    probability = pl.col("_positive_sum").cast(pl.Float64) / pl.col("_positive_valid")
    positive_mean = (
        pl.when(pl.col("_positive_count") >= MINIMUM_GROUP_SUPPORT)
        .then(pl.col("_positive_volume") / pl.col("_positive_count"))
        .otherwise(None)
    )
    support = sum(pl.col(f"_cause_{cause}") for cause in CAUSE_ORDER)
    has_majority = informed & (support >= MINIMUM_GROUP_SUPPORT)
    # Desempate fixo CNF, ENE, REL: vence a primeira causa com a maior contagem.
    best = pl.max_horizontal(*[pl.col(f"_cause_{cause}") for cause in CAUSE_ORDER])
    majority = _choose(
        [(pl.col(f"_cause_{cause}") == best, pl.lit(cause)) for cause in CAUSE_ORDER],
        pl.lit("CNF"),
    )
    uniform = pl.struct([pl.lit(1 / 3).alias(cause) for cause in CAUSE_ORDER])
    frame = frame.with_columns(
        pl.when(informed).then(probability).otherwise(0.5).alias("fb_prob_positive"),
        pl.when(informed)
        .then(pl.col("_restriction_sum").cast(pl.Float64) / pl.col("_rows"))
        .otherwise(0.5)
        .alias("fb_prob_restriction"),
        pl.when(informed).then(positive_mean).alias("fb_volume_positive_mean"),
        pl.when(informed & positive_mean.is_not_null())
        .then(probability * positive_mean)
        .otherwise(0.0)
        .alias("fb_volume_expected"),
        pl.when(has_majority).then(majority).otherwise(pl.lit("CNF")).alias("fb_cause_prediction"),
        pl.when(has_majority)
        .then(
            pl.struct(
                [
                    (pl.col(f"_cause_{cause}").cast(pl.Float64) / support).alias(cause)
                    for cause in CAUSE_ORDER
                ]
            )
        )
        .otherwise(uniform)
        .alias("fb_cause_probabilities"),
    )
    return frame


def _direct_values(frame: pl.DataFrame, prefix: str) -> pl.DataFrame:
    """Reproduz ``_direct_values`` sobre a linha direta encontrada (colunas ``prefix*``)."""
    cause = pl.col("_entity_last_cause").fill_null("CNF")
    return frame.with_columns(
        pl.col(f"{prefix}_positive")
        .cast(pl.Float64)
        .fill_null(0.5)
        .alias(f"{prefix}_prob_positive"),
        pl.col(f"{prefix}_restriction").cast(pl.Float64).alias(f"{prefix}_prob_restriction"),
        # O original compara ``volume > 0`` em Python; volume indeterminado (nulo) vira nulo
        # aqui em vez de TypeError.
        pl.when(pl.col(f"{prefix}_volume") > 0)
        .then(pl.col(f"{prefix}_volume"))
        .alias(f"{prefix}_volume_positive_mean"),
        pl.when(pl.col(f"{prefix}_volume_valid").fill_null(False))
        .then(pl.col(f"{prefix}_volume"))
        .otherwise(0.0)
        .alias(f"{prefix}_volume_expected"),
        cause.alias(f"{prefix}_cause_prediction"),
        pl.struct([(cause == name).cast(pl.Float64).alias(name) for name in CAUSE_ORDER]).alias(
            f"{prefix}_cause_probabilities"
        ),
    )


def _direct_row(available: pl.DataFrame, prefix: str) -> pl.DataFrame:
    return available.select(
        "fonte",
        "id_ons",
        "din_instante",
        pl.col("din_instante").alias(f"{prefix}_time"),
        pl.col("corte_positivo").alias(f"{prefix}_positive"),
        pl.col("restricao_registrada").alias(f"{prefix}_restriction"),
        pl.col("volume_mwmed").alias(f"{prefix}_volume"),
        pl.col("volume_valido").alias(f"{prefix}_volume_valid"),
    )


def _baselines_for_t0(history: pl.DataFrame, requests: pl.DataFrame, t0: datetime) -> pl.DataFrame:
    available = history.filter(
        (pl.col("disponivel_em") <= t0)
        & (pl.col("din_instante") + timedelta(minutes=30) <= t0)
        & (pl.col("din_instante") >= t0 - timedelta(days=28))
    ).with_columns(_slot(pl.col("din_instante")).alias("_slot"))
    frame = _historical_fallback(
        requests.with_columns(_slot(pl.col("tau")).alias("_slot")), available
    )
    ordered = available.sort("din_instante")
    known = pl.col("restricao_registrada").fill_null(False) & pl.col("causa").is_in(CAUSE_ORDER)
    last_cause = (
        ordered.filter(known)
        .group_by("fonte", "id_ons")
        .agg(pl.col("causa").last().alias("_entity_last_cause"))
    )
    last_row = (
        _direct_row(ordered, "d0")
        .group_by("fonte", "id_ons")
        .agg(pl.all().last())
        .drop("din_instante")
    )
    yesterday = _direct_row(available, "d1").rename({"din_instante": "_yesterday"})
    recent = (
        frame.select("_request", "fonte", "id_ons", "_slot", "tau")
        .join(
            _direct_row(available.select(pl.exclude("_slot")), "d2").with_columns(
                _slot(pl.col("din_instante")).alias("_slot")
            ),
            on=["fonte", "id_ons", "_slot"],
            how="inner",
        )
        .filter(pl.col("din_instante") < pl.col("tau"))
        .sort("din_instante")
        .group_by("_request")
        .agg(pl.exclude("fonte", "id_ons", "_slot", "tau", "din_instante").last())
    )
    frame = (
        frame.join(last_cause, on=["fonte", "id_ons"], how="left")
        .join(last_row, on=["fonte", "id_ons"], how="left")
        .with_columns((pl.col("tau") - timedelta(days=1)).alias("_yesterday"))
        .join(yesterday, on=["fonte", "id_ons", "_yesterday"], how="left")
        .join(recent, on="_request", how="left")
    )
    for prefix in ("d0", "d1", "d2"):
        frame = _direct_values(frame, prefix)

    request_columns = [name for name in requests.columns if name not in {"_request"}]
    outputs = []
    for position, baseline_id in enumerate(BASELINE_ORDER):
        if baseline_id == "historico":
            native = pl.col("fallback_level") != "sem_evidencia"
            level = pl.col("fallback_level")
            source_time = pl.col("fallback_time")
            values = [pl.col(f"fb_{name}").alias(name) for name in VALUE_COLUMNS]
        else:
            prefix = f"d{position}"
            found = pl.col(f"{prefix}_time").is_not_null()
            native = found
            level = pl.when(found).then(pl.lit("nativo")).otherwise(pl.col("fallback_level"))
            source_time = (
                pl.when(found).then(pl.col(f"{prefix}_time")).otherwise(pl.col("fallback_time"))
            )
            values = [
                pl.when(found)
                .then(pl.col(f"{prefix}_{name}"))
                .otherwise(pl.col(f"fb_{name}"))
                .alias(name)
                for name in VALUE_COLUMNS
            ]
        outputs.append(
            frame.select(
                "_request",
                pl.lit(position).alias("_baseline"),
                *request_columns,
                pl.lit(baseline_id).alias("baseline_id"),
                native.alias("native_available"),
                level.alias("fallback_level"),
                source_time.alias("source_time"),
                _hours(pl.lit(t0).cast(pl.Datetime("us")) - source_time).alias("history_age_hours"),
                *values,
            )
        )
    return pl.concat(outputs)


def generate_baselines(history: pl.DataFrame, requests: pl.DataFrame) -> pl.DataFrame:
    """Gera os quatro comparadores sem acessar observações não liberadas em ``t0``."""
    # Só as colunas usadas; alvos do DuckDB chegam em ns e a grade de 30 min cabe em us.
    history = history.select(HISTORY_COLUMNS)
    if not (
        history.schema["din_instante"] == pl.Datetime("us")
        and history.schema["disponivel_em"] == pl.Datetime("us")
    ):
        history = history.with_columns(
            pl.col("din_instante", "disponivel_em").cast(pl.Datetime("us"))
        )
    indexed = requests.with_row_index("_request").with_columns(
        pl.col("t0", "tau").cast(pl.Datetime("us"))
    )
    parts = []
    for t0 in indexed["t0"].unique(maintain_order=True).to_list():
        batch = indexed.filter(pl.col("t0") == t0)
        source = history.filter(pl.col("fonte").is_in(batch["fonte"].unique().to_list()))
        parts.append(_baselines_for_t0(source, batch, t0))
    result = pl.concat(parts).sort("_request", "_baseline").drop("_request", "_baseline")
    return result.with_columns(
        pl.col("fallback_level").cast(pl.String),
        pl.col("cause_probabilities").cast(CAUSE_STRUCT),
    )
