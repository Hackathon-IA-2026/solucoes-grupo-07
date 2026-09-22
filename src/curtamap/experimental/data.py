from __future__ import annotations

from datetime import datetime, timedelta
from math import ceil

import polars as pl

from curtamap.experimental.temporal import AvailabilityScenario, BusinessCalendar

EXPECTED_HALF_HOURS_28D = 28 * 48
MINIMUM_COVERAGE = ceil(EXPECTED_HALF_HOURS_28D * 0.8)
KNOWN_CAUSES = ("REL", "CNF", "ENE")


def add_release_times(
    frame: pl.DataFrame,
    scenario: AvailabilityScenario,
    calendar: BusinessCalendar,
) -> pl.DataFrame:
    """Anexa disponibilidade simulada sem usar mtime ou posição física do arquivo."""
    return frame.with_columns(
        pl.col("din_instante")
        .map_elements(
            lambda value: scenario.release_for(value.date(), calendar),
            return_dtype=pl.Datetime("us"),
        )
        .alias("disponivel_em")
    )


def available_asof(frame: pl.DataFrame, cutoff: datetime) -> pl.DataFrame:
    return frame.filter(
        (pl.col("disponivel_em") <= cutoff)
        & (pl.col("din_instante") + timedelta(minutes=30) <= cutoff)
    )


def history_eligibility(frame: pl.DataFrame, cutoff: datetime) -> pl.DataFrame:
    """Mede extensão e cobertura da grade; não confunde presença com alvo válido."""
    start = cutoff - timedelta(days=28)
    recent = frame.filter((pl.col("din_instante") >= start) & (pl.col("din_instante") < cutoff))
    if recent.is_empty():
        return pl.DataFrame(
            schema={
                "fonte": pl.String,
                "id_ons": pl.String,
                "observed_positions": pl.UInt32,
                "coverage": pl.Float64,
                "history_start": pl.Datetime,
                "eligible": pl.Boolean,
            }
        )
    return (
        recent.group_by("fonte", "id_ons")
        .agg(
            pl.col("din_instante").n_unique().alias("observed_positions"),
            pl.col("din_instante").min().alias("history_start"),
        )
        .with_columns((pl.col("observed_positions") / EXPECTED_HALF_HOURS_28D).alias("coverage"))
        .with_columns(
            (
                (pl.col("observed_positions") >= MINIMUM_COVERAGE)
                & (pl.col("history_start") <= start + timedelta(minutes=30))
            ).alias("eligible")
        )
        .sort("fonte", "id_ons")
    )


def task_masks(frame: pl.DataFrame) -> dict[str, pl.Series]:
    masks = frame.select(
        pl.col("corte_positivo").is_not_null().alias("occurrence_positive"),
        pl.col("restricao_registrada").is_not_null().alias("occurrence_restriction"),
        (pl.col("volume_valido") & pl.col("volume_mwmed").is_not_null()).alias("volume"),
        (
            pl.col("restricao_registrada") & pl.col("causa").is_in(KNOWN_CAUSES).fill_null(False)
        ).alias("cause"),
    )
    return {name: masks[name] for name in masks.columns}


def aggregate_asof(
    released: pl.DataFrame,
    cutoff: datetime,
    group_by: list[str],
) -> pl.DataFrame:
    history = available_asof(released, cutoff)
    return (
        history.group_by(group_by)
        .agg(
            pl.len().alias("observations"),
            pl.col("id_ons").n_unique().alias("entities"),
            pl.col("corte_positivo").mean().alias("positive_frequency"),
            pl.col("volume_mwmed").filter(pl.col("volume_valido")).mean().alias("mean_volume"),
        )
        .sort(group_by)
    )
