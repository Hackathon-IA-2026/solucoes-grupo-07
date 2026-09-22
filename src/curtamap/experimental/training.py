from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from time import perf_counter

import numpy as np
import polars as pl
from sklearn.metrics import average_precision_score, f1_score, mean_absolute_error

from curtamap.experimental.models import (
    CandidateModel,
    SigmoidCalibrator,
    candidate_grid,
    fit_candidate,
    fit_sigmoid_calibrator,
    optimize_f2_threshold,
)
from curtamap.experimental.temporal import (
    AvailabilityScenario,
    BusinessCalendar,
    ExternalRound,
)


@dataclass(frozen=True)
class InternalBoundaries:
    validation_start: datetime
    cutoff: datetime
    tuning_start: datetime
    calibration_start: datetime


def internal_boundaries(
    round_: ExternalRound,
    scenario: AvailabilityScenario,
    calendar: BusinessCalendar,
) -> InternalBoundaries:
    last_day = scenario.last_fully_released_day(round_.start, calendar)
    cutoff = datetime.combine(last_day + timedelta(days=1), datetime.min.time())
    return InternalBoundaries(
        validation_start=round_.start,
        cutoff=cutoff,
        tuning_start=cutoff - timedelta(days=56),
        calibration_start=cutoff - timedelta(days=28),
    )


@dataclass(frozen=True)
class DatasetSplit:
    features: pl.DataFrame
    target: np.ndarray

    def __post_init__(self) -> None:
        if self.features.height != len(self.target):
            raise ValueError("features e alvo devem ter o mesmo número de linhas")


@dataclass
class TrainedFamily:
    task: str
    family: str
    selection_metric: str
    selected_index: int
    selected_params: dict
    internal_scores: tuple[float, ...]
    model: CandidateModel
    calibrator: SigmoidCalibrator | None
    threshold: float | None
    fit_seconds: float
    calibration_status: str


def choose_configuration(scores: list[float], *, higher_is_better: bool) -> int:
    if not scores or not np.isfinite(scores).all():
        raise ValueError("scores internos devem ser finitos")
    optimum = max(scores) if higher_is_better else min(scores)
    return scores.index(optimum)


def _score(task: str, model: CandidateModel, split: DatasetSplit) -> float:
    if task == "occurrence":
        if np.unique(split.target).size < 2:
            raise ValueError("ajuste interno de ocorrência precisa das duas classes")
        return float(average_precision_score(split.target, model.predict_proba(split.features)))
    prediction = model.predict(split.features)
    if task == "volume":
        return float(mean_absolute_error(split.target, prediction))
    if task == "cause":
        return float(
            f1_score(
                split.target,
                prediction,
                labels=("REL", "CNF", "ENE"),
                average="macro",
                zero_division=0,
            )
        )
    raise ValueError(f"tarefa desconhecida: {task}")


def train_family(
    *,
    task: str,
    family: str,
    initial: DatasetSplit,
    tuning: DatasetSplit,
    refit: DatasetSplit,
    calibration: DatasetSplit | None,
    numeric: tuple[str, ...],
    categorical: tuple[str, ...],
    seed: int,
) -> TrainedFamily:
    started = perf_counter()
    grid = candidate_grid(task, family)
    internal_models = [
        fit_candidate(
            initial.features,
            initial.target,
            task=task,
            family=family,
            params=params,
            numeric=numeric,
            categorical=categorical,
            seed=seed,
            validation=(tuning.features, tuning.target),
        )
        for params in grid
    ]
    scores = [_score(task, model, tuning) for model in internal_models]
    higher = task != "volume"
    selected = choose_configuration(scores, higher_is_better=higher)
    selected_params = dict(grid[selected])
    best_iteration = getattr(internal_models[selected].estimator, "best_iteration_", 0)
    if family == "lightgbm" and best_iteration:
        selected_params["n_estimators"] = int(best_iteration)
    model = fit_candidate(
        refit.features,
        refit.target,
        task=task,
        family=family,
        params=selected_params,
        numeric=numeric,
        categorical=categorical,
        seed=seed,
    )
    calibrator = None
    threshold = None
    calibration_status = "nao_aplicavel"
    if task == "occurrence":
        if calibration is None:
            raise ValueError("ocorrência requer trecho independente de calibração")
        raw = model.predict_proba(calibration.features)
        calibrator = fit_sigmoid_calibrator(raw, calibration.target, seed=seed)
        probabilities = calibrator.predict(raw) if calibrator else raw
        threshold = optimize_f2_threshold(calibration.target, probabilities)
        calibration_status = "sigmoide" if calibrator else "fallback_bruto_classe_unica"
    metric = {"occurrence": "average_precision", "volume": "mae_conditional", "cause": "macro_f1"}[
        task
    ]
    return TrainedFamily(
        task=task,
        family=family,
        selection_metric=metric,
        selected_index=selected,
        selected_params=selected_params,
        internal_scores=tuple(scores),
        model=model,
        calibrator=calibrator,
        threshold=threshold,
        fit_seconds=perf_counter() - started,
        calibration_status=calibration_status,
    )
