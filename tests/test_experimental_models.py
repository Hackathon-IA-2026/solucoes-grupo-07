import numpy as np
import polars as pl
import pytest

from curtamap.experimental.models import (
    FeaturePreprocessor,
    candidate_grid,
    expected_volume,
    fit_candidate,
    fit_sigmoid_calibrator,
    optimize_f2_threshold,
)


def features() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "horizon": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
            "history_age": [24.0, 25.0, None, 27.0, 48.0, 49.0, 50.0, 51.0, 72.0, 73.0, 74.0, 75.0],
            "id_ons": ["A"] * 6 + ["B"] * 6,
            "id_estado": ["RJ"] * 4 + ["BA"] * 4 + ["RN"] * 4,
        }
    )


def test_preprocessor_is_fit_only_on_training_data_and_handles_new_entities() -> None:
    train = features().head(8)
    future = pl.DataFrame(
        {
            "horizon": [48],
            "history_age": [10_000.0],
            "id_ons": ["NOVA"],
            "id_estado": ["XX"],
        }
    )
    pre = FeaturePreprocessor(
        numeric=("horizon", "history_age"), categorical=("id_ons", "id_estado")
    ).fit(train)

    assert pre.numeric_medians_["history_age"] == 48.0
    assert "NOVA" not in pre.categories_["id_ons"]
    transformed = pre.transform(future)
    assert transformed.shape == (1, pre.output_features)
    assert np.isfinite(transformed.data).all()


@pytest.mark.parametrize("task", ["occurrence", "volume", "cause"])
@pytest.mark.parametrize("family", ["linear", "lightgbm"])
def test_candidate_grid_is_small_and_predefined(task: str, family: str) -> None:
    grid = candidate_grid(task, family)
    assert len(grid) == 2
    assert grid != candidate_grid(task, "lightgbm" if family == "linear" else "linear")


@pytest.mark.parametrize("family", ["linear", "lightgbm"])
def test_occurrence_models_are_reproducible_and_probabilistic(family: str) -> None:
    x = features()
    y = np.array([0, 1] * 6)
    kwargs = dict(
        task="occurrence",
        family=family,
        params=candidate_grid("occurrence", family)[0],
        numeric=("horizon", "history_age"),
        categorical=("id_ons", "id_estado"),
        seed=42,
    )
    first = fit_candidate(x, y, **kwargs)
    second = fit_candidate(x, y, **kwargs)
    np.testing.assert_allclose(first.predict_proba(x), second.predict_proba(x))
    assert np.all((first.predict_proba(x) >= 0) & (first.predict_proba(x) <= 1))


@pytest.mark.parametrize("family", ["linear", "lightgbm"])
def test_volume_models_return_finite_nonnegative_conditional_mean(family: str) -> None:
    x = features()
    y = np.arange(1.0, 13.0)
    model = fit_candidate(
        x,
        y,
        task="volume",
        family=family,
        params=candidate_grid("volume", family)[0],
        numeric=("horizon", "history_age"),
        categorical=("id_ons", "id_estado"),
        seed=42,
    )
    prediction = model.predict(x)
    assert np.isfinite(prediction).all()
    assert (prediction >= 0).all()


@pytest.mark.parametrize("family", ["linear", "lightgbm"])
def test_cause_model_preserves_only_observed_rel_cnf_ene_classes(family: str) -> None:
    x = features()
    y = np.array(["REL", "CNF", "ENE"] * 4)
    model = fit_candidate(
        x,
        y,
        task="cause",
        family=family,
        params=candidate_grid("cause", family)[0],
        numeric=("horizon", "history_age"),
        categorical=("id_ons", "id_estado"),
        seed=42,
    )
    assert set(model.classes_) == {"REL", "CNF", "ENE"}
    assert "PAR" not in model.classes_


def test_absent_cause_class_is_recorded_without_synthetic_examples() -> None:
    model = fit_candidate(
        features(),
        np.array(["REL", "CNF"] * 6),
        task="cause",
        family="linear",
        params=candidate_grid("cause", "linear")[0],
        numeric=("horizon", "history_age"),
        categorical=("id_ons", "id_estado"),
        seed=42,
    )
    assert model.missing_classes == ("ENE",)


def test_sigmoid_calibration_requires_both_classes_and_threshold_tie_prefers_higher() -> None:
    assert fit_sigmoid_calibrator(np.array([0.1, 0.2]), np.array([1, 1]), seed=42) is None
    calibrator = fit_sigmoid_calibrator(
        np.array([0.1, 0.2, 0.8, 0.9]), np.array([0, 0, 1, 1]), seed=42
    )
    assert calibrator is not None
    probabilities = calibrator.predict(np.array([0.1, 0.9]))
    assert probabilities[0] < probabilities[1]
    assert optimize_f2_threshold(np.array([0, 1]), np.array([0.5, 0.5])) == 0.5


def test_expected_volume_does_not_depend_on_alert_threshold() -> None:
    result = expected_volume(np.array([0.2, 0.8]), np.array([100.0, 50.0]))
    np.testing.assert_allclose(result, [20.0, 40.0])
