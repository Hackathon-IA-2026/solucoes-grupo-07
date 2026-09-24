from __future__ import annotations

from typing import Any

import numpy as np
import polars as pl
from sklearn.metrics import average_precision_score, confusion_matrix, f1_score, recall_score

CAUSES = ("REL", "CNF", "ENE")


def _value(value: float) -> dict[str, float]:
    return {"value": float(value)}


def _missing(reason: str) -> dict[str, None | str]:
    return {"value": None, "reason": reason}


def occurrence_metrics(
    target: np.ndarray, probabilities: np.ndarray, *, threshold: float
) -> dict[str, Any]:
    target = np.asarray(target, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    if target.size != probabilities.size or not np.isfinite(probabilities).all():
        raise ValueError("alvos e probabilidades devem ter mesmo tamanho e valores finitos")
    predicted = probabilities >= threshold
    tn, fp, fn, tp = confusion_matrix(target, predicted, labels=[0, 1]).ravel()
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f2_denominator = 5 * tp + 4 * fn + fp
    bins = np.minimum((probabilities * 10).astype(int), 9)
    calibration = []
    for index in range(10):
        selected = bins == index
        calibration.append(
            {
                "lower": index / 10,
                "upper": (index + 1) / 10,
                "support": int(selected.sum()),
                "mean_probability": float(probabilities[selected].mean())
                if selected.any()
                else None,
                "observed_frequency": float(target[selected].mean()) if selected.any() else None,
            }
        )
    both_classes = np.unique(target).size == 2
    return {
        "average_precision": _value(average_precision_score(target, probabilities))
        if both_classes
        else _missing("classe_unica"),
        "recall": _value(recall) if recall is not None else _missing("sem_positivos"),
        "precision": _value(precision) if precision is not None else _missing("sem_alertas"),
        "f2": _value(5 * tp / f2_denominator) if f2_denominator else _value(0.0),
        "brier": _value(np.mean((probabilities - target) ** 2)),
        "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "calibration_bins": calibration,
        "support": int(target.size),
        "prevalence": float(target.mean()) if target.size else None,
        "threshold": float(threshold),
    }


def volume_metrics(target: np.ndarray, prediction: np.ndarray) -> dict[str, Any]:
    target = np.asarray(target, dtype=float)
    prediction = np.asarray(prediction, dtype=float)
    if target.size != prediction.size:
        raise ValueError("alvos e previsões devem ter o mesmo tamanho")
    valid = np.isfinite(target) & np.isfinite(prediction)
    y, estimate = target[valid], prediction[valid]
    if np.any(estimate < 0):
        raise ValueError("previsões de volume não podem ser negativas")
    if not y.size:
        return {
            "support": 0,
            "coverage": 0.0,
            "mae_full": _missing("sem_alvos_validos"),
            "mae_conditional": _missing("sem_alvos_validos"),
            "wape": _missing("sem_alvos_validos"),
            "bias": _missing("sem_alvos_validos"),
        }
    absolute = np.abs(y - estimate)
    positive = y > 0
    denominator = float(y.sum())
    return {
        "support": int(y.size),
        "coverage": float(valid.mean()),
        "mae_full": _value(absolute.mean()),
        "mae_conditional": _value(absolute[positive].mean())
        if positive.any()
        else _missing("sem_cortes_positivos"),
        "wape": _value(absolute.sum() / denominator)
        if denominator > 0
        else _missing("denominador_zero"),
        "bias": _value(np.mean(estimate - y)),
    }


def cause_metrics(target: np.ndarray, prediction: np.ndarray) -> dict[str, Any]:
    target = np.asarray(target)
    prediction = np.asarray(prediction)
    matrix = confusion_matrix(target, prediction, labels=CAUSES)
    per_class: dict[str, dict[str, Any]] = {}
    supports = []
    for cause in CAUSES:
        support = int(np.sum(target == cause))
        supports.append(support)
        per_class[cause] = {
            "support": support,
            "recall": float(
                recall_score(target, prediction, labels=[cause], average="macro", zero_division=0)
            )
            if support
            else None,
            "f1": float(
                f1_score(target, prediction, labels=[cause], average="macro", zero_division=0)
            )
            if support
            else None,
        }
    missing = [cause for cause, support in zip(CAUSES, supports, strict=True) if not support]
    return {
        "macro_f1": _missing("classe_sem_suporte:" + ",".join(missing))
        if missing
        else _value(f1_score(target, prediction, labels=CAUSES, average="macro", zero_division=0)),
        "per_class": per_class,
        "confusion": {"labels": list(CAUSES), "matrix": matrix.tolist()},
        "support": int(target.size),
    }


def canonical_daily_energy(predictions: pl.DataFrame) -> pl.DataFrame:
    return (
        predictions.filter(
            (pl.col("t0").dt.hour() == 0)
            & (pl.col("t0").dt.minute() == 0)
            & pl.col("true_volume_mwmed").is_not_null()
        )
        .group_by("fonte", "id_ons", "t0")
        .agg(
            pl.col("horizon").n_unique().alias("horizons"),
            (pl.col("predicted_volume_mwmed").sum() * 0.5).alias("predicted_energy_mwh"),
            (pl.col("true_volume_mwmed").sum() * 0.5).alias("true_energy_mwh"),
        )
        .filter(pl.col("horizons") == 48)
        .drop("horizons")
        .sort("fonte", "id_ons", "t0")
    )


def block_bootstrap_difference(
    weekly: pl.DataFrame, *, repetitions: int = 1_000, seed: int = 42
) -> dict[str, Any]:
    groups = {
        round_id: values["difference"].to_numpy()
        for round_id, values in weekly.partition_by("round", as_dict=True).items()
    }
    if not groups:
        return {"estimate": None, "lower_95": None, "upper_95": None, "blocks": 0}
    estimate = float(np.mean([values.mean() for values in groups.values()]))
    generator = np.random.default_rng(seed)
    samples = np.empty(repetitions)
    for index in range(repetitions):
        round_means = []
        for values in groups.values():
            selected = generator.choice(values, size=values.size, replace=True)
            round_means.append(selected.mean())
        samples[index] = np.mean(round_means)
    lower, upper = np.quantile(samples, [0.025, 0.975])
    return {
        "estimate": estimate,
        "lower_95": float(lower),
        "upper_95": float(upper),
        "blocks": int(sum(values.size for values in groups.values())),
        "repetitions": repetitions,
        "seed": seed,
    }
