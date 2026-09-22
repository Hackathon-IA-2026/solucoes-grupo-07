from datetime import datetime, timedelta

import numpy as np
import polars as pl
import pytest

from curtamap.experimental.metrics import (
    block_bootstrap_difference,
    canonical_daily_energy,
    cause_metrics,
    occurrence_metrics,
    volume_metrics,
)


def test_occurrence_metrics_include_ap_f2_brier_confusion_calibration_and_support() -> None:
    result = occurrence_metrics(
        np.array([0, 0, 1, 1]), np.array([0.1, 0.4, 0.6, 0.9]), threshold=0.5
    )
    assert result["average_precision"]["value"] == 1.0
    assert result["recall"]["value"] == 1.0
    assert result["precision"]["value"] == 1.0
    assert result["f2"]["value"] == 1.0
    assert result["brier"]["value"] == pytest.approx(0.085)
    assert result["confusion"] == {"tn": 2, "fp": 0, "fn": 0, "tp": 2}
    assert result["support"] == 4
    assert result["prevalence"] == 0.5
    assert len(result["calibration_bins"]) == 10


def test_occurrence_slice_with_one_class_is_not_presented_as_comparable_ap() -> None:
    result = occurrence_metrics(np.array([0, 0]), np.array([0.1, 0.2]), threshold=0.5)
    assert result["average_precision"] == {"value": None, "reason": "classe_unica"}
    assert result["recall"] == {"value": None, "reason": "sem_positivos"}
    assert result["brier"]["value"] == pytest.approx(0.025)


def test_volume_metrics_distinguish_full_conditional_bias_wape_and_coverage() -> None:
    result = volume_metrics(np.array([0.0, 10.0, 20.0, np.nan]), np.array([1.0, 8.0, 24.0, 999.0]))
    assert result["support"] == 3
    assert result["coverage"] == 0.75
    assert result["mae_full"]["value"] == pytest.approx(7 / 3)
    assert result["mae_conditional"]["value"] == 3.0
    assert result["wape"]["value"] == pytest.approx(7 / 30)
    assert result["bias"]["value"] == 1.0


def test_volume_wape_is_not_applicable_when_true_sum_is_zero() -> None:
    result = volume_metrics(np.array([0.0, 0.0]), np.array([0.0, 1.0]))
    assert result["wape"] == {"value": None, "reason": "denominador_zero"}


def test_cause_metrics_use_three_class_macro_and_mark_missing_truth_class() -> None:
    result = cause_metrics(np.array(["REL", "REL", "CNF"]), np.array(["REL", "CNF", "CNF"]))
    assert result["macro_f1"] == {"value": None, "reason": "classe_sem_suporte:ENE"}
    assert result["per_class"]["REL"]["recall"] == 0.5
    assert result["per_class"]["CNF"]["recall"] == 1.0
    assert result["per_class"]["ENE"]["support"] == 0
    assert set(result["confusion"]) == {"labels", "matrix"}


def test_daily_energy_uses_only_midnight_emission_with_all_48_horizons() -> None:
    start = datetime(2025, 1, 1)
    complete = pl.DataFrame(
        {
            "fonte": ["eolica"] * 48,
            "id_ons": ["A"] * 48,
            "t0": [start] * 48,
            "horizon": list(range(1, 49)),
            "predicted_volume_mwmed": [2.0] * 48,
            "true_volume_mwmed": [1.0] * 48,
        }
    )
    overlapping = complete.with_columns((pl.col("t0") + timedelta(minutes=30)).alias("t0"))
    incomplete = complete.head(47).with_columns((pl.col("t0") + timedelta(days=1)).alias("t0"))
    result = canonical_daily_energy(pl.concat([complete, overlapping, incomplete]))
    assert result.height == 1
    assert result.row(0, named=True)["predicted_energy_mwh"] == 48.0
    assert result.row(0, named=True)["true_energy_mwh"] == 24.0


def test_temporal_block_bootstrap_is_reproducible_and_keeps_weekly_units() -> None:
    differences = pl.DataFrame(
        {
            "round": ["V1"] * 4 + ["V2"] * 4,
            "week": [1, 2, 3, 4] * 2,
            "difference": [-1.0, -2.0, -3.0, -4.0, 1.0, 2.0, 3.0, 4.0],
        }
    )
    first = block_bootstrap_difference(differences, repetitions=100, seed=42)
    second = block_bootstrap_difference(differences, repetitions=100, seed=42)
    assert first == second
    assert first["blocks"] == 8
    assert first["repetitions"] == 100
    assert first["estimate"] == 0.0
