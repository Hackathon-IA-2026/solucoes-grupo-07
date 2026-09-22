from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import polars as pl
from lightgbm import LGBMClassifier, LGBMRegressor
from scipy import sparse
from sklearn.linear_model import GammaRegressor, LogisticRegression

CAUSES = ("REL", "CNF", "ENE")


def candidate_grid(task: str, family: str) -> tuple[dict[str, Any], ...]:
    if family == "linear" and task in {"occurrence", "cause"}:
        return ({"C": 0.1}, {"C": 1.0})
    if family == "linear" and task == "volume":
        return ({"alpha": 0.0001}, {"alpha": 0.01})
    if family == "lightgbm" and task in {"occurrence", "volume", "cause"}:
        return (
            {"num_leaves": 15, "max_depth": 4},
            {"num_leaves": 31, "max_depth": 5},
        )
    raise ValueError(f"tarefa/família não suportada: {task}/{family}")


@dataclass
class FeaturePreprocessor:
    numeric: tuple[str, ...]
    categorical: tuple[str, ...]
    numeric_medians_: dict[str, float] = field(default_factory=dict, init=False)
    numeric_means_: dict[str, float] = field(default_factory=dict, init=False)
    numeric_scales_: dict[str, float] = field(default_factory=dict, init=False)
    categories_: dict[str, tuple[str, ...]] = field(default_factory=dict, init=False)
    fitted_: bool = field(default=False, init=False)

    def fit(self, frame: pl.DataFrame) -> FeaturePreprocessor:
        for name in self.numeric:
            values = frame[name].cast(pl.Float64).to_numpy()
            median = float(np.nanmedian(values)) if not np.isnan(values).all() else 0.0
            filled = np.where(np.isnan(values), median, values)
            scale = float(np.std(filled))
            self.numeric_medians_[name] = median
            self.numeric_means_[name] = float(np.mean(filled))
            self.numeric_scales_[name] = scale if scale > 0 else 1.0
        for name in self.categorical:
            observed = sorted(str(value) for value in frame[name].drop_nulls().unique().to_list())
            self.categories_[name] = tuple(observed + ["<MISSING>", "<UNKNOWN>"])
        self.fitted_ = True
        return self

    @property
    def output_features(self) -> int:
        if not self.fitted_:
            raise RuntimeError("pré-processador ainda não ajustado")
        return len(self.numeric) + sum(len(values) for values in self.categories_.values())

    def transform(self, frame: pl.DataFrame) -> sparse.csr_matrix:
        if not self.fitted_:
            raise RuntimeError("pré-processador ainda não ajustado")
        numeric_parts: list[np.ndarray] = []
        for name in self.numeric:
            values = frame[name].cast(pl.Float64).to_numpy()
            values = np.where(np.isnan(values), self.numeric_medians_[name], values)
            numeric_parts.append(
                ((values - self.numeric_means_[name]) / self.numeric_scales_[name]).reshape(-1, 1)
            )
        numeric = (
            sparse.csr_matrix(np.hstack(numeric_parts))
            if numeric_parts
            else sparse.csr_matrix((frame.height, 0))
        )
        categorical_parts: list[sparse.csr_matrix] = []
        for name in self.categorical:
            categories = self.categories_[name]
            mapping = {value: position for position, value in enumerate(categories)}
            missing = mapping["<MISSING>"]
            unknown = mapping["<UNKNOWN>"]
            columns = []
            for value in frame[name].to_list():
                if value is None:
                    columns.append(missing)
                else:
                    columns.append(mapping.get(str(value), unknown))
            categorical_parts.append(
                sparse.csr_matrix(
                    (np.ones(frame.height), (np.arange(frame.height), columns)),
                    shape=(frame.height, len(categories)),
                )
            )
        return sparse.hstack([numeric, *categorical_parts], format="csr")

    def fit_transform(self, frame: pl.DataFrame) -> sparse.csr_matrix:
        return self.fit(frame).transform(frame)


@dataclass
class CandidateModel:
    task: str
    family: str
    params: dict[str, Any]
    seed: int
    preprocessor: FeaturePreprocessor
    estimator: Any
    classes_: tuple[str, ...] = ()
    missing_classes: tuple[str, ...] = ()

    def predict_proba(self, frame: pl.DataFrame) -> np.ndarray:
        if self.task != "occurrence":
            raise TypeError("predict_proba binária é exclusiva de ocorrência")
        matrix = self.preprocessor.transform(frame)
        return np.asarray(self.estimator.predict_proba(matrix)[:, 1], dtype=float)

    def predict(self, frame: pl.DataFrame) -> np.ndarray:
        matrix = self.preprocessor.transform(frame)
        if self.task == "cause":
            return np.asarray(self.estimator.predict(matrix))
        prediction = np.asarray(self.estimator.predict(matrix), dtype=float)
        return np.maximum(prediction, 0.0) if self.task == "volume" else prediction

    def predict_cause_proba(self, frame: pl.DataFrame) -> np.ndarray:
        if self.task != "cause":
            raise TypeError("probabilidades multiclasse são exclusivas de causa")
        return np.asarray(self.estimator.predict_proba(self.preprocessor.transform(frame)))


def _estimator(task: str, family: str, params: dict[str, Any], seed: int) -> Any:
    if family == "linear" and task in {"occurrence", "cause"}:
        return LogisticRegression(
            C=params["C"],
            tol=1e-4,
            max_iter=1_000,
            random_state=seed,
        )
    if family == "linear" and task == "volume":
        return GammaRegressor(alpha=params["alpha"], tol=1e-4, max_iter=1_000)
    common = dict(
        **params,
        learning_rate=0.05,
        min_child_samples=100,
        reg_lambda=1.0,
        max_bin=63,
        n_estimators=500,
        subsample=1.0,
        colsample_bytree=1.0,
        random_state=seed,
        n_jobs=1,
        verbosity=-1,
    )
    if family == "lightgbm" and task == "occurrence":
        return LGBMClassifier(objective="binary", **common)
    if family == "lightgbm" and task == "volume":
        return LGBMRegressor(objective="gamma", **common)
    if family == "lightgbm" and task == "cause":
        return LGBMClassifier(objective="multiclass", **common)
    raise ValueError(f"tarefa/família não suportada: {task}/{family}")


def fit_candidate(
    frame: pl.DataFrame,
    target: np.ndarray,
    *,
    task: str,
    family: str,
    params: dict[str, Any],
    numeric: tuple[str, ...],
    categorical: tuple[str, ...],
    seed: int,
) -> CandidateModel:
    if task == "volume" and (not np.isfinite(target).all() or np.any(target <= 0)):
        raise ValueError("Gamma requer volumes condicionais positivos e finitos")
    preprocessor = FeaturePreprocessor(numeric=numeric, categorical=categorical)
    matrix = preprocessor.fit_transform(frame)
    estimator = _estimator(task, family, params, seed)
    estimator.fit(matrix, target)
    classes = tuple(str(value) for value in getattr(estimator, "classes_", ()))
    missing = tuple(cause for cause in CAUSES if task == "cause" and cause not in classes)
    return CandidateModel(
        task=task,
        family=family,
        params=params,
        seed=seed,
        preprocessor=preprocessor,
        estimator=estimator,
        classes_=classes,
        missing_classes=missing,
    )


@dataclass
class SigmoidCalibrator:
    estimator: LogisticRegression

    def predict(self, scores: np.ndarray) -> np.ndarray:
        return self.estimator.predict_proba(np.asarray(scores).reshape(-1, 1))[:, 1]


def fit_sigmoid_calibrator(
    scores: np.ndarray, target: np.ndarray, *, seed: int
) -> SigmoidCalibrator | None:
    if np.unique(target).size < 2:
        return None
    estimator = LogisticRegression(random_state=seed, max_iter=1_000)
    estimator.fit(np.asarray(scores).reshape(-1, 1), target)
    return SigmoidCalibrator(estimator)


def optimize_f2_threshold(target: np.ndarray, probabilities: np.ndarray) -> float:
    if np.unique(target).size < 2:
        return 0.5
    best_score, best_threshold = -1.0, 0.5
    for threshold in sorted(set(np.asarray(probabilities).tolist())):
        predicted = probabilities >= threshold
        true_positive = int(np.sum((target == 1) & predicted))
        false_positive = int(np.sum((target == 0) & predicted))
        false_negative = int(np.sum((target == 1) & ~predicted))
        denominator = 5 * true_positive + 4 * false_negative + false_positive
        score = 5 * true_positive / denominator if denominator else 0.0
        if score > best_score or (score == best_score and threshold > best_threshold):
            best_score, best_threshold = score, float(threshold)
    return best_threshold


def expected_volume(probability: np.ndarray, conditional_volume: np.ndarray) -> np.ndarray:
    result = np.asarray(probability, dtype=float) * np.asarray(conditional_volume, dtype=float)
    if not np.isfinite(result).all() or np.any(result < 0):
        raise ValueError("volume esperado deve ser finito e não negativo")
    return result
