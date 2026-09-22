from __future__ import annotations

import math
from datetime import datetime, timedelta

import polars as pl

from curtamap.experimental.data import history_eligibility

KNOWN_CAUSES = ("REL", "CNF", "ENE")
SAME_HOUR_DAYS = (1, 2, 3, 7)
HISTORY_OFFSETS = {
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "48h": timedelta(hours=48),
    "7d": timedelta(days=7),
}

# Schema estável: colunas inteiramente nulas continuam tipadas, sem ``Null`` inferido.
FEATURE_SCHEMA: dict[str, pl.DataType] = {
    "fonte": pl.String(),
    "id_ons": pl.String(),
    "id_estado": pl.String(),
    "id_subsistema": pl.String(),
    "ceg_level": pl.String(),
    "t0": pl.Datetime("us"),
    "tau": pl.Datetime("us"),
    "horizon": pl.Int64(),
    "t0_hour_sin": pl.Float64(),
    "t0_hour_cos": pl.Float64(),
    "tau_hour_sin": pl.Float64(),
    "tau_hour_cos": pl.Float64(),
    "tau_weekday": pl.Int64(),
    "tau_month": pl.Int64(),
    "tau_day_of_year": pl.Int64(),
    "t0_weekday": pl.Int64(),
    "t0_month": pl.Int64(),
    "t0_day_of_year": pl.Int64(),
    "last_positive": pl.Boolean(),
    "last_restriction": pl.Boolean(),
    "last_volume_mwmed": pl.Float64(),
    "last_cause": pl.String(),
    "observed_episode_length": pl.Int64(),
    "history_coverage_28d": pl.Float64(),
    "eligible_history": pl.Boolean(),
    "history_age_hours": pl.Float64(),
    "hours_since_positive": pl.Float64(),
    "hours_since_restriction": pl.Float64(),
    "positive_frequency_24h": pl.Float64(),
    "positive_frequency_7d": pl.Float64(),
    "positive_frequency_28d": pl.Float64(),
    "mean_volume_28d": pl.Float64(),
    "std_volume_28d": pl.Float64(),
    "max_volume_28d": pl.Float64(),
    "restriction_frequency_28d": pl.Float64(),
    "state_positive_frequency_28d": pl.Float64(),
    "subsystem_positive_frequency_28d": pl.Float64(),
    "target_observed": pl.Boolean(),
    "true_restriction": pl.Boolean(),
    "true_positive": pl.Boolean(),
    "true_volume_mwmed": pl.Float64(),
    "true_volume_valid": pl.Boolean(),
    "true_cause": pl.String(),
    "target_available_at": pl.Datetime("us"),
    **{f"cause_{cause.lower()}_share_28d": pl.Float64() for cause in KNOWN_CAUSES},
    **{
        f"{stat}_volume_{label}": pl.Float64()
        for label in ("24h", "7d")
        for stat in ("mean", "std", "max")
    },
    **{
        f"same_hour_{days}d_{kind}": pl.Boolean() if kind == "positive" else pl.Float64()
        for days in SAME_HOUR_DAYS
        for kind in ("positive", "volume")
    },
    **{
        f"history_{label}_{kind}": pl.Boolean() if kind == "positive" else pl.Float64()
        for label in HISTORY_OFFSETS
        for kind in ("positive", "volume")
    },
}


def _hours(expression: pl.Expr) -> pl.Expr:
    return expression.dt.total_microseconds().cast(pl.Float64) / 3_600_000_000


def _valid_volume() -> pl.Expr:
    return pl.col("volume_valido").fill_null(False) & pl.col("volume_mwmed").is_not_null()


def _slot_angle(expression: pl.Expr) -> pl.Expr:
    slot = expression.dt.hour().cast(pl.Int64) * 2 + expression.dt.minute().cast(pl.Int64) // 30
    return 2 * math.pi * slot.cast(pl.Float64) / 48


def _volume_window(days: int, t0: datetime, label: str) -> list[pl.Expr]:
    in_window = pl.col("din_instante") >= t0 - timedelta(days=days)
    volumes = pl.col("volume_mwmed").filter(in_window & _valid_volume())
    return [
        volumes.mean().alias(f"mean_volume_{label}"),
        pl.when(volumes.len() >= 2).then(volumes.std(ddof=0)).alias(f"std_volume_{label}"),
        volumes.max().alias(f"max_volume_{label}"),
    ]


def _lookup(frame: pl.DataFrame, found: pl.DataFrame, at: pl.Expr, prefix: str) -> pl.DataFrame:
    """Busca exata por timestamp no histórico liberado; ausência permanece nula."""
    return (
        frame.with_columns(at.alias("_lookup_at"))
        .join(
            found.rename({"_positive": f"{prefix}_positive", "_volume": f"{prefix}_volume"}),
            on=["fonte", "id_ons", "_lookup_at"],
            how="left",
        )
        .drop("_lookup_at")
    )


SOURCE_COLUMNS = (
    "fonte",
    "id_ons",
    "id_estado",
    "id_subsistema",
    "ceg",
    "din_instante",
    "disponivel_em",
    "restricao_registrada",
    "corte_positivo",
    "volume_mwmed",
    "volume_valido",
    "causa",
)


def _project(source: pl.DataFrame) -> pl.DataFrame:
    """Mantém só as colunas usadas; alvos do DuckDB chegam em ns e a grade cabe em us."""
    projected = source.select(SOURCE_COLUMNS)
    if projected.schema["din_instante"] == pl.Datetime("us") and projected.schema[
        "disponivel_em"
    ] == pl.Datetime("us"):
        return projected
    return projected.with_columns(pl.col("din_instante", "disponivel_em").cast(pl.Datetime("us")))


def build_feature_batch(source: pl.DataFrame, t0: datetime) -> pl.DataFrame:
    """Constrói um lote de emissão de forma colunar, sem materializar o snapshot inteiro.

    ``source`` contém história e verdade posterior. Somente linhas com ``disponivel_em <= t0``
    alimentam features/cadastro; a verdade futura é consultada exclusivamente para os alvos.
    """
    if not source["fonte"].n_unique() == 1:
        raise ValueError("cada lote deve conter uma única fonte")
    source = _project(source)
    available = source.filter(
        (pl.col("disponivel_em") <= t0) & (pl.col("din_instante") + timedelta(minutes=30) <= t0)
    ).sort("id_ons", "din_instante")
    if available.is_empty():
        return pl.DataFrame()

    ordered = available.with_columns(
        (pl.len().over("fonte", "id_ons") - 1 - pl.int_range(pl.len()).over("fonte", "id_ons"))
        .cast(pl.Int64)
        .alias("_from_end"),
        pl.col("din_instante").last().over("fonte", "id_ons").alias("_last_time"),
    ).with_columns(
        # Episódio: linhas finais consecutivas (grade exata de 30 min) com corte positivo.
        (
            pl.col("corte_positivo").fill_null(False)
            & (
                pl.col("din_instante")
                == pl.col("_last_time") - pl.duration(minutes=pl.col("_from_end") * 30)
            )
        ).alias("_in_episode")
    )
    window_28d = pl.col("din_instante") >= t0 - timedelta(days=28)
    known_cause = window_28d & pl.col("causa").is_in(KNOWN_CAUSES)
    entities = ordered.group_by("fonte", "id_ons", maintain_order=True).agg(
        pl.col("id_estado").last(),
        pl.col("id_subsistema").last(),
        pl.col("ceg").last(),
        pl.col("din_instante").last().alias("last_time"),
        pl.col("corte_positivo").last().alias("last_positive"),
        pl.col("restricao_registrada").last().alias("last_restriction"),
        pl.when(pl.col("volume_valido").last().fill_null(False))
        .then(pl.col("volume_mwmed").last())
        .alias("last_volume_mwmed"),
        pl.col("causa").last().alias("last_cause"),
        pl.col("_from_end")
        .filter(~pl.col("_in_episode"))
        .min()
        .fill_null(pl.len())
        .cast(pl.Int64)
        .alias("observed_episode_length"),
        pl.col("din_instante")
        .filter(pl.col("corte_positivo").fill_null(False))
        .last()
        .alias("last_positive_time"),
        pl.col("din_instante")
        .filter(pl.col("restricao_registrada").fill_null(False))
        .last()
        .alias("last_restriction_time"),
        *[
            pl.col("corte_positivo")
            .filter(pl.col("din_instante") >= t0 - timedelta(days=days))
            .cast(pl.Float64)
            .mean()
            .alias(f"positive_frequency_{label}")
            for days, label in ((1, "24h"), (7, "7d"), (28, "28d"))
        ],
        *_volume_window(28, t0, "28d"),
        pl.col("restricao_registrada")
        .filter(window_28d)
        .cast(pl.Float64)
        .mean()
        .alias("restriction_frequency_28d"),
        *[
            pl.when(pl.col("causa").filter(known_cause).len() > 0)
            .then(
                (pl.col("causa").filter(known_cause) == cause).sum().cast(pl.Float64)
                / pl.col("causa").filter(known_cause).len()
            )
            .alias(f"cause_{cause.lower()}_share_28d")
            for cause in KNOWN_CAUSES
        ],
        *_volume_window(1, t0, "24h"),
        *_volume_window(7, t0, "7d"),
    )

    eligibility = history_eligibility(available, t0).select(
        "fonte",
        "id_ons",
        pl.col("coverage").alias("history_coverage_28d"),
        pl.col("eligible").alias("eligible_history"),
    )
    recent = available.filter(window_28d)
    regional = {
        field: recent.group_by(field).agg(
            pl.col("corte_positivo").cast(pl.Float64).mean().alias(alias)
        )
        for field, alias in (
            ("id_estado", "state_positive_frequency_28d"),
            ("id_subsistema", "subsystem_positive_frequency_28d"),
        )
    }
    entities = (
        entities.join(eligibility, on=["fonte", "id_ons"], how="left")
        .join(regional["id_estado"], on="id_estado", how="left", nulls_equal=True)
        .join(regional["id_subsistema"], on="id_subsistema", how="left", nulls_equal=True)
        .with_columns(
            pl.col("history_coverage_28d").fill_null(0.0),
            pl.col("eligible_history").fill_null(False),
        )
    )

    horizons = pl.DataFrame(
        {
            "horizon": list(range(1, 49)),
            "tau": [t0 + timedelta(minutes=30 * step) for step in range(48)],
        },
        schema={"horizon": pl.Int64, "tau": pl.Datetime("us")},
    )
    frame = entities.join(horizons, how="cross").with_columns(
        pl.lit(t0).cast(pl.Datetime("us")).alias("t0")
    )
    targets = (
        source.filter(
            (pl.col("din_instante") >= t0) & (pl.col("din_instante") < t0 + timedelta(hours=24))
        )
        .select(
            "fonte",
            "id_ons",
            pl.col("din_instante").alias("tau"),
            pl.lit(True).alias("target_observed"),
            pl.col("restricao_registrada").alias("true_restriction"),
            pl.col("corte_positivo").alias("true_positive"),
            pl.col("volume_mwmed").alias("true_volume_mwmed"),
            pl.col("volume_valido").alias("true_volume_valid"),
            pl.col("causa").alias("true_cause"),
            pl.col("disponivel_em").alias("target_available_at"),
        )
        .unique(["fonte", "id_ons", "tau"], keep="last", maintain_order=True)
    )
    frame = frame.join(targets, on=["fonte", "id_ons", "tau"], how="left").with_columns(
        pl.col("target_observed").fill_null(False)
    )
    found = available.select(
        "fonte",
        "id_ons",
        pl.col("din_instante").alias("_lookup_at"),
        pl.col("corte_positivo").alias("_positive"),
        pl.when(pl.col("volume_valido").fill_null(False))
        .then(pl.col("volume_mwmed"))
        .alias("_volume"),
    )
    for days in SAME_HOUR_DAYS:
        frame = _lookup(frame, found, pl.col("tau") - timedelta(days=days), f"same_hour_{days}d")
    for label, offset in HISTORY_OFFSETS.items():
        frame = _lookup(frame, found, pl.col("last_time") - offset, f"history_{label}")

    frame = frame.with_columns(
        pl.when(pl.col("ceg") == "-")
        .then(pl.lit("conjunto"))
        .otherwise(pl.lit("individual"))
        .alias("ceg_level"),
        _slot_angle(pl.col("t0")).sin().alias("t0_hour_sin"),
        _slot_angle(pl.col("t0")).cos().alias("t0_hour_cos"),
        _slot_angle(pl.col("tau")).sin().alias("tau_hour_sin"),
        _slot_angle(pl.col("tau")).cos().alias("tau_hour_cos"),
        (pl.col("tau").dt.weekday() - 1).alias("tau_weekday"),
        pl.col("tau").dt.month().alias("tau_month"),
        pl.col("tau").dt.ordinal_day().alias("tau_day_of_year"),
        (pl.col("t0").dt.weekday() - 1).alias("t0_weekday"),
        pl.col("t0").dt.month().alias("t0_month"),
        pl.col("t0").dt.ordinal_day().alias("t0_day_of_year"),
        _hours(pl.col("t0") - pl.col("last_time")).alias("history_age_hours"),
        _hours(pl.col("t0") - pl.col("last_positive_time")).alias("hours_since_positive"),
        _hours(pl.col("t0") - pl.col("last_restriction_time")).alias("hours_since_restriction"),
    )
    return frame.select([pl.col(name).cast(dtype) for name, dtype in FEATURE_SCHEMA.items()]).sort(
        "fonte", "id_ons", "t0", "horizon"
    )
