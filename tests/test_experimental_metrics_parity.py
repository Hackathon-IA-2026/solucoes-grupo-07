"""Paridade independente com as métricas anteriores à otimização de 24/09."""

import numpy as np
import polars as pl
import pytest
import reference_metrics_stage2b as oracle

from curtamap.experimental import campaign, metrics


@pytest.mark.parametrize("size", [0, 1, 17, 10003])
@pytest.mark.parametrize("labels", [("REL",), ("REL", "CNF", "ENE"), ("REL", "PAR", "CNF")])
def test_cause_matches_frozen_oracle(size, labels):
    rng = np.random.default_rng(42)
    target = rng.choice(labels, size=size)
    prediction = rng.choice(["REL", "CNF", "ENE", "PAR"], size=size)
    if not size:
        with pytest.raises(ValueError):
            oracle.cause_metrics(target, prediction)
        with pytest.raises(ValueError):
            metrics.cause_metrics(target, prediction)
        return
    assert metrics.cause_metrics(target, prediction) == oracle.cause_metrics(target, prediction)


@pytest.mark.parametrize("size", [0, 1, 17, 10003])
def test_occurrence_matches_frozen_oracle(size):
    rng = np.random.default_rng(42)
    target = rng.integers(0, 2, size=size)
    probabilities = rng.choice([0.0, 0.1, 0.5, 0.9, 1.0], size=size)
    if not size:
        with pytest.raises(ValueError):
            oracle.occurrence_metrics(target, probabilities, threshold=0.5)
        with pytest.raises(ValueError):
            metrics.occurrence_metrics(target, probabilities, threshold=0.5)
        return
    actual = metrics.occurrence_metrics(target, probabilities, threshold=0.5)
    expected = oracle.occurrence_metrics(target, probabilities, threshold=0.5)
    assert actual == expected


def test_cause_does_not_repeat_sklearn_scans(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("métricas de causa devem reutilizar uma única contagem")

    monkeypatch.setattr(metrics, "confusion_matrix", forbidden)
    metrics.cause_metrics(np.array(["REL", "CNF", "ENE"]), np.array(["REL"] * 3))


def test_slices_copy_only_metric_columns(monkeypatch):
    def slices(frame):
        assert frame.columns == ["horizon", "true_volume_mwmed", "prediction"]
        yield "global", frame

    monkeypatch.setattr(campaign, "_slice_frames", slices)
    campaign._metrics_for_prediction(
        pl.DataFrame(
            {
                "horizon": [1],
                "true_volume_mwmed": [2.0],
                "prediction": [1.0],
                "unused_feature": [999],
            }
        ),
        "volume_pipeline",
        None,
    )
