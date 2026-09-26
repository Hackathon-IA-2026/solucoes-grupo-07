import math
from datetime import date, timedelta

import numpy as np
import polars as pl
import pytest

from curtamap.experimentos.rede_temporal.hgb import (
    EXT_OCCURRENCE,
    EXT_VOLUME,
    NEW_FEATURES,
    VARIANTS,
    build_rows,
    recency_weights,
)
from curtamap.previsao.features import OCCURRENCE, VOLUME

L = date(2026, 3, 10)


def _base(volumes: dict[date, float], slot: int = 0) -> pl.DataFrame:
    rows = [
        {
            "fonte": "eolica",
            "id_ons": "A",
            "id_estado": "RN",
            "dia": day,
            "slot": slot,
            "corte": float(volume > 0),
            "volume": volume,
            "referencia": 100.0,
            "restricao": float(volume > 0),
            "causa": "ENE" if volume > 0 else None,
            "_REL": 0.0 if volume > 0 else None,
            "_CNF": 0.0 if volume > 0 else None,
            "_ENE": 1.0 if volume > 0 else None,
            "_sis": 1.0 if volume > 0 else None,
        }
        for day, volume in volumes.items()
    ]
    return pl.DataFrame(rows).with_columns(
        pl.col("dia").cast(pl.Date),
        pl.col("slot").cast(pl.Int8),
        pl.col(["corte", "volume", "referencia", "restricao", "_REL", "_CNF", "_ENE", "_sis"]).cast(
            pl.Float32
        ),
    )


def _mapping(target: date = L + timedelta(days=2)) -> pl.DataFrame:
    return pl.DataFrame(
        {"dia": [target], "ultimo_dia": [L], "idade": [2], "dia_semana": [3], "feriado": [0]},
        schema={
            "dia": pl.Date,
            "ultimo_dia": pl.Date,
            "idade": pl.Int8,
            "dia_semana": pl.Int8,
            "feriado": pl.Int8,
        },
    )


# 28 dias até L: volume 0 nos 21 primeiros e 10 MWmed nos 7 últimos.
VOLUMES = {L - timedelta(days=k): (10.0 if k < 7 else 0.0) for k in range(28)}


def _slot0(rows: pl.DataFrame) -> dict:
    return rows.filter(pl.col("slot") == 0).row(0, named=True)


def test_change_features_compare_recent_and_long_windows() -> None:
    row = _slot0(build_rows(_base(VOLUMES), _mapping()))

    assert row["vol_hist_7d"] == pytest.approx(10.0)
    assert row["vol_hist_28d"] == pytest.approx(2.5)
    assert row["d_vol_7_28"] == pytest.approx(7.5)
    assert row["lr_vol_7_28"] == pytest.approx(math.log1p(10) - math.log1p(2.5))
    assert row["d_hist_7_28"] == pytest.approx(1.0 - 0.25)
    assert row["vol_std_28d"] == pytest.approx(np.std([10.0] * 7 + [0.0] * 21, ddof=1), rel=1e-5)
    assert row["n_dias_slot_28d"] == 28


def test_zero_history_gives_zero_log_ratio_not_nan() -> None:
    zeros = {day: 0.0 for day in VOLUMES}

    row = _slot0(build_rows(_base(zeros), _mapping()))

    assert row["lr_vol_7_28"] == 0.0
    assert row["cv_vol_28d"] == 0.0


def test_missing_days_reduce_coverage_instead_of_counting_as_zero() -> None:
    sparse = {day: v for day, v in VOLUMES.items() if day > L - timedelta(days=7)}

    row = _slot0(build_rows(_base(sparse), _mapping()))

    assert row["n_dias_slot_28d"] == 7
    assert row["vol_hist_28d"] == pytest.approx(10.0)


def test_data_after_the_last_released_day_never_changes_features() -> None:
    later = {**VOLUMES, L + timedelta(days=1): 999.0, L + timedelta(days=2): 999.0}

    before = build_rows(_base(VOLUMES), _mapping()).select(NEW_FEATURES)
    after = build_rows(_base(later), _mapping()).select(NEW_FEATURES)

    assert before.equals(after)


def test_extended_feature_lists_extend_the_originals() -> None:
    assert EXT_OCCURRENCE[: len(OCCURRENCE)] == OCCURRENCE
    assert EXT_VOLUME[: len(VOLUME)] == VOLUME
    assert set(NEW_FEATURES).isdisjoint(VOLUME)


def test_recency_weights_halve_every_half_life() -> None:
    days = pl.Series([L, L - timedelta(days=60), L - timedelta(days=120)])

    assert recency_weights(days, L, half_life=60) == pytest.approx([1.0, 0.5, 0.25])
    assert recency_weights(days, L, half_life=None) is None


def test_control_variant_reproduces_the_product_recipe() -> None:
    from curtamap.previsao.modelo import PARAMS, TRAIN_DAYS

    control = VARIANTS["B0_original"]
    assert control.occurrence == OCCURRENCE
    assert control.volume == VOLUME
    assert control.params == PARAMS
    assert control.train_days == TRAIN_DAYS
    assert control.half_life is None
