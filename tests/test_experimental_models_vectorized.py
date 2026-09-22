"""Igualdade entre codificação/limiar vetorizados e os trechos originais (oráculo)."""

from time import perf_counter

import numpy as np
import polars as pl
import pytest
import reference_models_stage2b as reference

from curtamap.experimental.models import FeaturePreprocessor, optimize_f2_threshold


def _frame(rows: int, seed: int) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    ids = np.array(["A", "B", "C", "NOVO", None], dtype=object)
    states = np.array(["BA", "RN", None], dtype=object)
    return pl.DataFrame(
        {
            "horizon": rng.integers(1, 49, rows),
            "history_age_hours": np.where(rng.random(rows) < 0.1, np.nan, rng.random(rows) * 90),
            "id_ons": ids[rng.integers(0, ids.size, rows)].tolist(),
            "id_estado": states[rng.integers(0, states.size, rows)].tolist(),
        },
        schema_overrides={"id_ons": pl.String, "id_estado": pl.String},
    )


def test_vectorized_categorical_encoding_matches_reference_matrix() -> None:
    train = _frame(500, seed=1).filter(pl.col("id_ons") != "NOVO")
    future = _frame(2_000, seed=2)  # inclui categoria nova e nulos
    pre = FeaturePreprocessor(
        numeric=("horizon", "history_age_hours"), categorical=("id_ons", "id_estado")
    ).fit(train)
    expected = reference.transform(pre, future)
    actual = pre.transform(future)
    assert actual.shape == expected.shape
    assert actual.format == "csr"
    assert (actual != expected).nnz == 0
    np.testing.assert_array_equal(actual.toarray(), expected.toarray())


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_vectorized_f2_threshold_matches_reference(seed: int) -> None:
    rng = np.random.default_rng(seed)
    target = (rng.random(3_000) < 0.2).astype(int)
    # Probabilidades com muitos empates e poucos valores distintos exercitam o desempate.
    probabilities = np.round(np.clip(target * 0.3 + rng.random(3_000) * 0.7, 0, 1), 2)
    assert optimize_f2_threshold(target, probabilities) == reference.optimize_f2_threshold(
        target, probabilities
    )


def test_f2_threshold_single_class_and_all_negative_scores_match_reference() -> None:
    probabilities = np.array([0.1, 0.4, 0.4, 0.9])
    for target in (np.array([0, 0, 0, 0]), np.array([1, 0, 0, 0]), np.array([0, 0, 0, 1])):
        assert optimize_f2_threshold(target, probabilities) == reference.optimize_f2_threshold(
            target, probabilities
        )


def test_f2_threshold_scales_to_calibration_segments() -> None:
    rng = np.random.default_rng(42)
    target = (rng.random(100_000) < 0.1).astype(int)
    probabilities = rng.random(100_000)
    started = perf_counter()
    optimize_f2_threshold(target, probabilities)
    assert perf_counter() - started < 2.0
