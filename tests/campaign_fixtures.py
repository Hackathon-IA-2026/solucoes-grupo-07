"""Dataset sintético da campanha: features e baselines no schema real, em partições diárias.

Verdade por (entidade, tau), sementes fixas, as duas classes nos trechos de ajuste e
calibração, causas REL/CNF/ENE (e PAR fora do contrato), volumes indeterminados,
``eligible_history`` misto, entidade nova após ``U`` e baselines com idade própria.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path

import numpy as np
import polars as pl

from curtamap.experimental.baselines import BASELINE_ORDER, CAUSE_ORDER, CAUSE_STRUCT
from curtamap.experimental.features import FEATURE_SCHEMA
from curtamap.experimental.temporal import BusinessCalendar, external_rounds

CALENDAR = BusinessCalendar(
    frozenset(
        {
            date(2024, 11, 15),
            date(2024, 12, 25),
            date(2025, 1, 1),
            date(2025, 3, 3),
            date(2025, 3, 4),
            date(2025, 4, 18),
            date(2025, 4, 21),
        }
    ),
    "fixture-campanha",
)
V1 = next(item for item in external_rounds() if item.round_id == "V1")
START, END = datetime(2024, 9, 1), datetime(2025, 5, 1)
HORIZONS = (1, 2, 13, 25, 48)
ENTITIES = (
    ("A", "BA", "NE", "conjunto", START),
    ("B", "RN", "NE", "individual", START),
    ("C", "CE", "NE", "conjunto", START),
    # Surge depois de U (05/11/2024 para V1 neste calendário): entidade nova.
    ("D", "BA", "NE", "individual", datetime(2024, 11, 20)),
)
SEED = 42


def _truth(rng: np.random.Generator, *, delay: timedelta) -> pl.DataFrame:
    """Verdade por (entidade, tau): a mesma janela tem o mesmo alvo em qualquer emissão."""
    slots = pl.datetime_range(
        START, END + timedelta(days=1), "30m", closed="left", eager=True, time_unit="us"
    )
    frames = []
    for id_ons, *_ in ENTITIES:
        size = slots.len()
        draws = rng.random(size)
        positive = np.zeros(size, dtype=bool)
        for index in range(size):
            previous = positive[index - 1] if index else False
            positive[index] = draws[index] < (0.7 if previous else 0.2)
        observed = rng.random(size) > 0.04
        valid = rng.random(size) > 0.06
        volume = np.where(positive, np.round(rng.gamma(2.0, 8.0, size) + 0.01, 3), 0.0)
        restriction = np.where(positive, rng.random(size) < 0.9, rng.random(size) < 0.08)
        cause = rng.choice(["REL", "CNF", "ENE", "PAR"], size=size, p=[0.3, 0.35, 0.3, 0.05])
        release = [
            datetime.combine(slot.date() + timedelta(days=1), time(19, 30)) + delay
            for slot in slots.to_list()
        ]
        frames.append(
            pl.DataFrame(
                {
                    "id_ons": [id_ons] * size,
                    "tau": slots,
                    "target_observed": observed,
                    "true_restriction": restriction,
                    "true_positive": positive,
                    "true_volume_mwmed": volume,
                    "true_volume_valid": valid,
                    "true_cause": cause,
                    "target_available_at": release,
                }
            ).with_columns(
                pl.when(pl.col("target_observed")).then(pl.col(name)).alias(name)
                for name in (
                    "true_restriction",
                    "true_positive",
                    "true_volume_mwmed",
                    "true_volume_valid",
                    "true_cause",
                    "target_available_at",
                )
            )
        )
    truth = pl.concat(frames)
    return truth.with_columns(
        pl.when(pl.col("true_volume_valid"))
        .then(pl.col("true_volume_mwmed"))
        .alias("true_volume_mwmed"),
        pl.when(pl.col("true_restriction")).then(pl.col("true_cause")).alias("true_cause"),
    )


def synthetic_dataset(
    *, seed: int, delay: timedelta, grid: str = "6h"
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Features e baselines sintéticos direto no schema real (não passa pela geração)."""
    rng = np.random.default_rng(seed)
    truth = _truth(rng, delay=delay)
    emissions = pl.datetime_range(START, END, grid, closed="left", eager=True, time_unit="us")
    entities = pl.DataFrame(
        {
            "id_ons": [item[0] for item in ENTITIES],
            "id_estado": [item[1] for item in ENTITIES],
            "id_subsistema": [item[2] for item in ENTITIES],
            "ceg_level": [item[3] for item in ENTITIES],
            "_first": [item[4] for item in ENTITIES],
        }
    ).with_columns(pl.col("_first").cast(pl.Datetime("us")))
    frame = (
        pl.DataFrame({"t0": emissions})
        .join(entities, how="cross")
        .join(pl.DataFrame({"horizon": list(HORIZONS)}), how="cross")
        .filter(pl.col("t0") >= pl.col("_first"))
        .with_columns(
            pl.lit("eolica").alias("fonte"),
            (pl.col("t0") + pl.duration(minutes=(pl.col("horizon") - 1) * 30)).alias("tau"),
        )
        .sort("fonte", "id_ons", "t0", "horizon")
        .join(truth, on=["id_ons", "tau"], how="left", maintain_order="left")
    )
    size = frame.height
    signal = frame["true_positive"].fill_null(False).cast(pl.Float64).to_numpy()
    eligible = rng.random(size) < 0.85
    # C fica fora do painel fixo (inelegível na emissão de 01/01/2025 00h).
    eligible &= ~(
        (frame["id_ons"] == "C").to_numpy() & (frame["t0"] == datetime(2025, 1, 1)).to_numpy()
    )
    eligible &= ~(
        (frame["id_ons"] == "D").to_numpy() & (frame["t0"] < datetime(2024, 12, 1)).to_numpy()
    )
    age = rng.uniform(0.5, 150.0, size)
    mean_volume = rng.gamma(2.0, 6.0, size)
    random_columns: dict[str, object] = {}
    for name, dtype in FEATURE_SCHEMA.items():
        if name in frame.columns:
            continue
        if dtype == pl.Float64():
            random_columns[name] = rng.normal(size=size)
        elif dtype == pl.Boolean():
            random_columns[name] = rng.random(size) < 0.3
        elif dtype == pl.Int64():
            random_columns[name] = rng.integers(0, 50, size)
        elif dtype == pl.String():
            random_columns[name] = rng.choice(["REL", "CNF", "ENE"], size=size)
    frame = frame.with_columns(
        pl.Series(name, values) for name, values in random_columns.items()
    ).with_columns(
        pl.Series("eligible_history", eligible),
        pl.Series("history_age_hours", np.where(rng.random(size) < 0.02, np.nan, age)),
        pl.Series("history_coverage_28d", rng.uniform(0.0, 1.0, size)),
        pl.Series("positive_frequency_7d", 0.5 * signal + 0.5 * rng.random(size)),
        pl.Series("positive_frequency_28d", 0.3 * signal + 0.7 * rng.random(size)),
        pl.Series("mean_volume_28d", np.where(rng.random(size) < 0.05, np.nan, mean_volume)),
        (pl.col("tau").dt.weekday() - 1).alias("tau_weekday"),
        pl.col("tau").dt.month().cast(pl.Int64).alias("tau_month"),
    )
    frame = frame.with_columns(
        pl.col("history_age_hours", "mean_volume_28d").fill_nan(None)
    ).select([pl.col(name).cast(dtype) for name, dtype in FEATURE_SCHEMA.items()])

    requests = frame.select("fonte", "id_ons", "id_estado", "t0", "tau", "horizon")
    baselines = (
        requests.with_row_index("_request")
        .join(pl.DataFrame({"_baseline": list(range(4))}), how="cross")
        .sort("_request", "_baseline")
    )
    rows = baselines.height
    probability = rng.random(rows)
    positive_mean = np.where(rng.random(rows) < 0.1, np.nan, rng.gamma(2.0, 7.0, rows))
    shares = rng.dirichlet(np.ones(3), rows)
    baselines = (
        baselines.with_columns(
            pl.col("_baseline")
            .replace_strict(list(range(4)), list(BASELINE_ORDER))
            .alias("baseline_id"),
            pl.Series("native_available", rng.random(rows) < 0.8),
            pl.Series(
                "fallback_level",
                rng.choice(["nativo", "entidade_mesmo_horario", "sem_evidencia"], size=rows),
            ),
            (pl.col("t0") - pl.duration(minutes=pl.Series(rng.integers(30, 9_000, rows)))).alias(
                "source_time"
            ),
            # Idade própria do comparador: colide com a das features na junção do oráculo.
            pl.Series("history_age_hours", rng.uniform(0.0, 200.0, rows)),
            pl.Series("prob_positive", probability),
            pl.Series("prob_restriction", rng.random(rows)),
            pl.Series("volume_positive_mean", positive_mean).fill_nan(None),
            pl.Series("volume_expected", probability * np.nan_to_num(positive_mean)),
            pl.Series("cause_prediction", rng.choice(list(CAUSE_ORDER), size=rows)),
            pl.struct(pl.Series(cause, shares[:, index]) for index, cause in enumerate(CAUSE_ORDER))
            .cast(CAUSE_STRUCT)
            .alias("cause_probabilities"),
        )
        .drop("_request", "_baseline")
        .with_columns(pl.col("source_time").cast(pl.Datetime("us")))
    )
    return frame, baselines


def write_partitions(root: Path, scenario: str, features: pl.DataFrame, baselines: pl.DataFrame):
    """Leiaute real: uma partição diária com features e baselines, lidas por glob."""
    base = root / f"scenario={scenario}" / "source=eolica" / "round=development"
    for name, frame in (("features", features), ("baselines", baselines)):
        for day, part in _by_day(frame):
            destination = base / f"date={day.isoformat()}" / f"{name}.parquet"
            destination.parent.mkdir(parents=True, exist_ok=True)
            part.write_parquet(destination)
    return str(base / "date=*" / "features.parquet"), str(base / "date=*" / "baselines.parquet")


def _by_day(frame: pl.DataFrame):
    keyed = frame.with_columns(pl.col("t0").dt.date().alias("_day"))
    for (day,), part in keyed.partition_by("_day", as_dict=True, maintain_order=True).items():
        yield day, part.drop("_day")


def manifest(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "code_commit": "a" * 40,
        "data_hashes": {},
        "schema": {},
        "calendar": {"version": CALENDAR.version},
        "resolved_config": {"seed": SEED},
        "parameters": {},
        "seeds": [SEED],
        "host": {"system": "test"},
        "started_at": "2026-09-22T00:00:00Z",
        "status": "running",
    }
