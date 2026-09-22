from __future__ import annotations

import platform
import resource
from time import perf_counter
from typing import Any

import numpy as np
import polars as pl

from curtamap.experimental.artifacts import RunStore
from curtamap.experimental.models import candidate_grid, fit_candidate

NUMERIC_FEATURES = (
    "horizon",
    "history_age_hours",
    "history_coverage_28d",
    "positive_frequency_7d",
    "positive_frequency_28d",
    "mean_volume_28d",
    "tau_weekday",
    "tau_month",
)
CATEGORICAL_FEATURES = ("id_ons", "id_estado", "id_subsistema", "ceg_level")

TASKS = {
    "corte_positivo": ("occurrence", "true_positive"),
    "restricao_registrada": ("occurrence", "true_restriction"),
    "volume_condicional": ("volume", "true_volume_mwmed"),
    "causa": ("cause", "true_cause"),
}


def _task_frame(frame: pl.DataFrame, task_id: str) -> tuple[pl.DataFrame, np.ndarray]:
    if task_id == "volume_condicional":
        selected = frame.filter(
            pl.col("target_observed")
            & pl.col("true_volume_valid")
            & pl.col("true_positive")
            & (pl.col("true_volume_mwmed") > 0)
        )
    elif task_id == "causa":
        selected = frame.filter(
            pl.col("target_observed")
            & pl.col("true_restriction")
            & pl.col("true_cause").is_in(["REL", "CNF", "ENE"])
        )
    else:
        target = TASKS[task_id][1]
        selected = frame.filter(pl.col("target_observed") & pl.col(target).is_not_null())
    selected = selected.head(frame.height)
    return selected, selected[TASKS[task_id][1]].to_numpy()


def run_technical_pilot(
    frame: pl.DataFrame,
    store: RunStore,
    *,
    seed: int,
    max_examples: int = 500_000,
) -> dict[str, Any]:
    """Exercita contratos/recursos; não calcula métrica usada para escolher modelos."""
    report: dict[str, Any] = {
        "purpose": "contracts_and_resources_only",
        "selection_metrics_emitted": False,
        "max_examples_per_task_source": max_examples,
        "host": {"system": platform.system(), "machine": platform.machine()},
        "fits": [],
        "failures": [],
    }
    for task_id, (task, _) in TASKS.items():
        selected, target = _task_frame(frame, task_id)
        selected = selected.head(max_examples)
        target = target[: selected.height]
        for family in ("linear", "lightgbm"):
            started = perf_counter()
            identity = f"{task_id}-{family}"
            try:
                model = fit_candidate(
                    selected,
                    target,
                    task=task,
                    family=family,
                    params=candidate_grid(task, family)[0],
                    numeric=NUMERIC_FEATURES,
                    categorical=CATEGORICAL_FEATURES,
                    seed=seed,
                )
                store.write_model(f"models/pilot/{identity}.joblib", model)
                report["fits"].append(
                    {
                        "task": task_id,
                        "family": family,
                        "examples": selected.height,
                        "duration_seconds": perf_counter() - started,
                        "peak_rss_platform_units": resource.getrusage(
                            resource.RUSAGE_SELF
                        ).ru_maxrss,
                        "params": model.params,
                        "missing_classes": model.missing_classes,
                    }
                )
            except Exception as error:
                report["failures"].append(identity)
                store.record_failure(f"pilot/{identity}.json", error, resumable=True)
    store.write_json("reports/technical-pilot.json", report)
    return report
