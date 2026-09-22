from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

import polars as pl

from curtamap.experimental.artifacts import RunStore
from curtamap.experimental.metrics import cause_metrics, occurrence_metrics, volume_metrics
from curtamap.experimental.models import expected_volume
from curtamap.experimental.runner import CATEGORICAL_FEATURES, NUMERIC_FEATURES, _task_frame
from curtamap.experimental.temporal import AvailabilityScenario, BusinessCalendar, ExternalRound
from curtamap.experimental.training import DatasetSplit, internal_boundaries, train_family


def _range(
    frame: pl.DataFrame,
    start,
    end,
    *,
    label_cutoff=None,
) -> pl.DataFrame:
    selected = frame.filter(
        (pl.col("t0") >= start)
        & (pl.col("t0") + timedelta(hours=24) <= end)
        & pl.col("eligible_history")
    )
    if label_cutoff is not None:
        selected = selected.filter(pl.col("target_available_at") <= label_cutoff)
    return selected


def _split(frame: pl.DataFrame, task_id: str) -> DatasetSplit:
    selected, target = _task_frame(frame, task_id)
    if selected.is_empty():
        raise ValueError(f"segmento sem exemplos para {task_id}")
    return DatasetSplit(selected, target)


def _slice_frames(frame: pl.DataFrame) -> list[tuple[str, pl.DataFrame]]:
    slices = [("global", frame)]
    for start, end, name in ((1, 12, "0_6h"), (13, 24, "6_12h"), (25, 48, "12_24h")):
        slices.append(
            (f"faixa_horizonte:{name}", frame.filter(pl.col("horizon").is_between(start, end)))
        )
    for horizon in range(1, 49):
        slices.append((f"horizonte:{horizon}", frame.filter(pl.col("horizon") == horizon)))
    if "eligible_history" in frame.columns:
        slices.append(("historico_insuficiente", frame.filter(~pl.col("eligible_history"))))
    if "entity_new" in frame.columns:
        slices.append(("entidade_nova", frame.filter(pl.col("entity_new"))))
    if "panel_fixed" in frame.columns:
        slices.append(("painel_fixo", frame.filter(pl.col("panel_fixed"))))
        slices.append(("painel_aberto", frame))
    if "tau_weekend_or_holiday" in frame.columns:
        slices.append(("fim_semana_feriado", frame.filter(pl.col("tau_weekend_or_holiday"))))
    for lower, upper, label in ((0, 48, "ate_48h"), (48, 96, "48_96h"), (96, None, "acima_96h")):
        condition = (
            pl.col("history_age_hours") <= upper
            if lower == 0
            else pl.col("history_age_hours") > lower
        )
        if upper is not None and lower:
            condition &= pl.col("history_age_hours") <= upper
        slices.append((f"idade:{label}", frame.filter(condition)))
    return [(name, subset) for name, subset in slices if not subset.is_empty()]


def _metrics_for_prediction(
    frame: pl.DataFrame, task_id: str, threshold: float | None
) -> list[dict]:
    reports = []
    for slice_id, subset in _slice_frames(frame):
        if task_id in {"corte_positivo", "restricao_registrada"}:
            target = "true_positive" if task_id == "corte_positivo" else "true_restriction"
            valid = subset.filter(pl.col(target).is_not_null())
            metrics = occurrence_metrics(
                valid[target].cast(pl.Int8).to_numpy(),
                valid["prediction"].to_numpy(),
                threshold=threshold or 0.5,
            )
        elif task_id == "causa":
            valid = subset.filter(pl.col("true_cause").is_in(["REL", "CNF", "ENE"]))
            metrics = cause_metrics(valid["true_cause"].to_numpy(), valid["prediction"].to_numpy())
        else:
            metrics = volume_metrics(
                subset["true_volume_mwmed"].to_numpy(), subset["prediction"].to_numpy()
            )
        reports.append({"slice": slice_id, "metrics": metrics})
    return reports


def run_campaign_round(
    features: pl.DataFrame,
    baselines: pl.DataFrame,
    store: RunStore,
    *,
    source: str,
    round_: ExternalRound,
    calendar: BusinessCalendar,
    seed: int,
) -> dict[str, Any]:
    if round_.reserved:
        raise ValueError("teste reservado não pode ser executado pela campanha V1–V4")
    boundary = internal_boundaries(round_, AvailabilityScenario.main(), calendar)
    features = features.with_columns(
        (
            ~pl.col("id_ons").is_in(
                features.filter(pl.col("t0") < boundary.tuning_start)["id_ons"].unique()
            )
        ).alias("entity_new"),
        (
            (pl.col("tau").dt.weekday() >= 6)
            | pl.col("tau").dt.date().is_in(list(calendar.non_business_days))
        ).alias("tau_weekend_or_holiday"),
    )
    fixed_ids = features.filter(
        (pl.col("t0") == datetime(2025, 1, 1)) & pl.col("eligible_history")
    )["id_ons"].unique()
    features = features.with_columns(pl.col("id_ons").is_in(fixed_ids).alias("panel_fixed"))
    initial = _range(
        features,
        features["t0"].min(),
        boundary.tuning_start,
        label_cutoff=boundary.tuning_start,
    )
    tuning = _range(
        features,
        boundary.tuning_start,
        boundary.calibration_start,
        label_cutoff=boundary.calibration_start,
    )
    refit = _range(
        features,
        features["t0"].min(),
        boundary.calibration_start,
        label_cutoff=boundary.calibration_start,
    )
    calibration = _range(
        features,
        boundary.calibration_start,
        boundary.cutoff,
        label_cutoff=round_.start,
    )
    validation = features.filter(
        (pl.col("t0") >= round_.start) & (pl.col("t0") + timedelta(hours=24) <= round_.end)
    )
    keys = ["fonte", "id_ons", "t0", "tau", "horizon"]
    reports: dict[str, Any] = {
        "source": source,
        "round": round_.round_id,
        "boundaries": asdict(boundary),
        "models": {},
        "failures": [],
    }
    predictions: dict[tuple[str, str], pl.DataFrame] = {}
    for task_id in ("corte_positivo", "restricao_registrada", "volume_condicional", "causa"):
        for family in ("linear", "lightgbm"):
            identity = f"{source}-{round_.round_id}-{task_id}-{family}"
            try:
                trained = train_family(
                    task={
                        "corte_positivo": "occurrence",
                        "restricao_registrada": "occurrence",
                        "volume_condicional": "volume",
                        "causa": "cause",
                    }[task_id],
                    family=family,
                    initial=_split(initial, task_id),
                    tuning=_split(tuning, task_id),
                    refit=_split(refit, task_id),
                    calibration=_split(calibration, task_id)
                    if task_id in {"corte_positivo", "restricao_registrada"}
                    else None,
                    numeric=NUMERIC_FEATURES,
                    categorical=CATEGORICAL_FEATURES,
                    seed=seed,
                )
                if task_id in {"corte_positivo", "restricao_registrada"}:
                    raw = trained.model.predict_proba(validation)
                    prediction = trained.calibrator.predict(raw) if trained.calibrator else raw
                elif task_id == "causa":
                    prediction = trained.model.predict(validation)
                else:
                    prediction = trained.model.predict(validation)
                predicted = validation.with_columns(pl.Series("prediction", prediction))
                predictions[(task_id, family)] = predicted
                store.write_model(f"models/{identity}.joblib", trained)
                store.write_parquet(
                    f"predictions/{identity}.parquet",
                    predicted.select(
                        keys
                        + [
                            "prediction",
                            "true_positive",
                            "true_restriction",
                            "true_volume_mwmed",
                            "true_volume_valid",
                            "true_cause",
                            "eligible_history",
                            "history_age_hours",
                            "entity_new",
                            "panel_fixed",
                            "tau_weekend_or_holiday",
                        ]
                    ),
                )
                task_metrics = _metrics_for_prediction(predicted, task_id, trained.threshold)
                store.write_json(f"metrics/{identity}.json", task_metrics)
                reports["models"][identity] = {
                    "selected_params": trained.selected_params,
                    "internal_scores": trained.internal_scores,
                    "fit_seconds": trained.fit_seconds,
                    "calibration_status": trained.calibration_status,
                    "threshold": trained.threshold,
                }
            except Exception as error:
                reports["failures"].append(identity)
                store.record_failure(f"campaign/{identity}.json", error, resumable=True)

    for occurrence_family in ("linear", "lightgbm"):
        occurrence = predictions.get(("corte_positivo", occurrence_family))
        if occurrence is None:
            continue
        for volume_family in ("linear", "lightgbm"):
            volume = predictions.get(("volume_condicional", volume_family))
            if volume is None:
                continue
            pipeline = (
                occurrence.select(keys + [pl.col("prediction").alias("probability")])
                .join(
                    volume.select(keys + [pl.col("prediction").alias("conditional_volume")]),
                    on=keys,
                )
                .join(
                    validation.select(
                        keys
                        + [
                            "true_volume_mwmed",
                            "eligible_history",
                            "history_age_hours",
                            "entity_new",
                            "panel_fixed",
                            "tau_weekend_or_holiday",
                        ]
                    ),
                    on=keys,
                )
            )
            pipeline = pipeline.with_columns(
                pl.Series(
                    "prediction",
                    expected_volume(
                        pipeline["probability"].to_numpy(),
                        pipeline["conditional_volume"].to_numpy(),
                    ),
                )
            )
            identity = f"{source}-{round_.round_id}-volume-{occurrence_family}-{volume_family}"
            store.write_parquet(f"predictions/{identity}.parquet", pipeline)
            store.write_json(
                f"metrics/{identity}.json",
                _metrics_for_prediction(pipeline, "volume_pipeline", None),
            )

    reports["baseline_rows"] = baselines.height
    store.write_json(f"reports/{source}-{round_.round_id}.json", reports)
    return reports
