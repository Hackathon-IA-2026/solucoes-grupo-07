from datetime import date

import numpy as np
import polars as pl
import pytest

from curtamap.experimentos.rede_temporal.dados import (
    HOLDOUT_DAY,
    fold_cutoff,
    month_days,
    without_holdout,
)
from curtamap.experimentos.rede_temporal.metricas import (
    metric_table,
    occurrence_metrics,
    volume_metrics,
)
from curtamap.previsao.calendario import load_calendar


def test_occurrence_metrics_counts_and_scores() -> None:
    y = np.array([1, 0, 0, 1, 0])
    p = np.array([0.9, 0.6, 0.2, 0.4, 0.1])

    m = occurrence_metrics(y, p, threshold=0.5)

    assert (m["vp"], m["fp"], m["fn"], m["vn"]) == (1, 1, 1, 2)
    assert m["precisao"] == pytest.approx(0.5)
    assert m["recall"] == pytest.approx(0.5)
    assert m["f1"] == pytest.approx(0.5)
    assert m["acuracia"] == pytest.approx(0.6)
    assert m["brier"] == pytest.approx(np.mean((p - y) ** 2))
    assert 0 < m["ap"] <= 1


def _volume_frame() -> pl.DataFrame:
    # Usina A: dia 1 com corte (real 10+30 MWmed), dia 2 sem corte. Usina B: dia 1 sem corte.
    return pl.DataFrame(
        {
            "fonte": ["eolica"] * 5,
            "id_ons": ["A", "A", "A", "A", "B"],
            "dia": [date(2026, 2, 1)] * 2 + [date(2026, 2, 2)] * 2 + [date(2026, 2, 1)],
            "slot": [0, 1, 0, 1, 0],
            "y_volume": [10.0, 30.0, 0.0, 0.0, 0.0],
            "v": [20.0, 10.0, 4.0, 0.0, 2.0],
        }
    )


def test_volume_metrics_half_hour_daily_and_bias() -> None:
    m = volume_metrics(_volume_frame(), "v")

    assert m["mae_mwmed"] == pytest.approx((10 + 20 + 4 + 0 + 2) / 5)
    assert m["wape"] == pytest.approx(36 / 40)
    # Diário: A/d1 real 40, previsto 30; A/d2 real 0, previsto 4; B/d1 real 0, previsto 2.
    assert m["wape_diario"] == pytest.approx((10 + 4 + 2) / 40)
    assert m["vies"] == pytest.approx(36 / 40 - 1)
    assert m["energia_real_mwh"] == pytest.approx(20.0)
    assert m["energia_prevista_mwh"] == pytest.approx(18.0)
    assert m["wape_diario_dias_com_corte"] == pytest.approx(10 / 40)
    assert m["usina_dias_sem_corte"] == 2
    assert m["energia_prevista_dias_sem_corte_mwh"] == pytest.approx(3.0)


def test_volume_without_real_energy_has_undefined_wape() -> None:
    frame = _volume_frame().with_columns(pl.lit(0.0).alias("y_volume"))

    m = volume_metrics(frame, "v")

    assert np.isnan(m["wape"])
    assert np.isnan(m["wape_diario_dias_com_corte"])


def test_metric_table_uses_only_rows_every_candidate_covers() -> None:
    frame = _volume_frame().with_columns(
        pl.Series("y_corte", [1.0, 1.0, 0.0, 0.0, 0.0]),
        pl.Series("mes", [date(2026, 2, 1)] * 5),
        pl.Series("p_a", [0.9, 0.8, 0.1, 0.2, 0.3]),
        pl.Series("p_b", [0.7, None, 0.2, 0.1, 0.4]),
        pl.Series("v_a", [20.0, 10.0, 4.0, 0.0, 2.0]),
        pl.Series("v_b", [15.0, None, 1.0, 0.0, 0.0]),
    )

    table = metric_table(frame, ["a", "b"], thresholds={("eolica", "a"): 0.5})

    rows = table.filter(pl.col("periodo") == "2026-02-01")
    assert set(rows["candidato"]) == {"a", "b"}
    assert (rows["n"] == 4).all()
    assert (rows["linhas_sem_previsao"] == 1).all()


def test_fold_cutoff_respects_the_release_calendar() -> None:
    # Emissão de 31/12/2025 às 20h: o último dia liberado é anterior à véspera.
    cutoff = fold_cutoff(date(2026, 1, 1), load_calendar())

    assert cutoff < date(2025, 12, 31)


def test_month_days_and_holdout() -> None:
    assert len(month_days(date(2026, 2, 1))) == 28
    days = month_days(date(2026, 9, 1), last=date(2026, 9, 25))
    assert HOLDOUT_DAY not in without_holdout(days)
    assert without_holdout(days)[-1] == date(2026, 9, 24)
