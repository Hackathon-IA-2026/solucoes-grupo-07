from datetime import date, datetime

import numpy as np
import polars as pl

from curtamap.experimental.temporal import AvailabilityScenario, BusinessCalendar, external_rounds
from curtamap.experimental.training import (
    DatasetSplit,
    choose_configuration,
    internal_boundaries,
    train_family,
)


def frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "horizon": list(range(1, 49)),
            "history_age": [24.0 + i for i in range(48)],
            "id_ons": ["A"] * 24 + ["B"] * 24,
            "id_estado": ["RJ"] * 16 + ["BA"] * 16 + ["RN"] * 16,
        }
    )


def test_internal_boundaries_follow_last_released_day_and_28_day_segments() -> None:
    calendar = BusinessCalendar(frozenset({date(2024, 12, 25), date(2025, 1, 1)}), "test")
    boundary = internal_boundaries(external_rounds()[0], AvailabilityScenario.main(), calendar)
    assert boundary.validation_start == datetime(2025, 1, 1)
    assert boundary.cutoff == datetime(2024, 12, 31)
    assert boundary.tuning_start == datetime(2024, 11, 5)
    assert boundary.calibration_start == datetime(2024, 12, 3)


def test_configuration_choice_uses_primary_metric_and_prefers_first_on_tie() -> None:
    assert choose_configuration([0.6, 0.6], higher_is_better=True) == 0
    assert choose_configuration([10.0, 8.0], higher_is_better=False) == 1


def test_occurrence_training_selects_only_with_internal_data_and_freezes_validation_recipe() -> (
    None
):
    x = frame()
    y = np.array([0, 1] * 24)
    split = DatasetSplit(x, y)
    trained = train_family(
        task="occurrence",
        family="linear",
        initial=split,
        tuning=split,
        refit=split,
        calibration=split,
        numeric=("horizon", "history_age"),
        categorical=("id_ons", "id_estado"),
        seed=42,
    )
    assert len(trained.internal_scores) == 2
    assert trained.selected_index in (0, 1)
    assert 0 <= trained.threshold <= 1
    assert trained.model.seed == 42
    assert trained.task == "occurrence"


def test_volume_and_cause_use_their_predefined_internal_metrics() -> None:
    x = frame()
    volume = DatasetSplit(x, np.arange(1.0, 49.0))
    cause = DatasetSplit(x, np.array(["REL", "CNF", "ENE"] * 16))
    trained_volume = train_family(
        task="volume",
        family="linear",
        initial=volume,
        tuning=volume,
        refit=volume,
        calibration=None,
        numeric=("horizon", "history_age"),
        categorical=("id_ons", "id_estado"),
        seed=42,
    )
    trained_cause = train_family(
        task="cause",
        family="linear",
        initial=cause,
        tuning=cause,
        refit=cause,
        calibration=None,
        numeric=("horizon", "history_age"),
        categorical=("id_ons", "id_estado"),
        seed=42,
    )
    assert trained_volume.selection_metric == "mae_conditional"
    assert trained_cause.selection_metric == "macro_f1"
    assert trained_volume.calibrator is None
    assert trained_cause.threshold is None
