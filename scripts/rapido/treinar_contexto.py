"""Treino rápido exploratório (fora do protocolo completo): LightGBM com contexto.

Motivação (Etapa 2C, 24/09/2026): os modelos da 2B receberam só 12 features e perderam
para o baseline `historico`. Este script treina um LightGBM por fonte/tarefa/rodada com as
features do §8 já presentes nos datasets **mais as saídas dos quatro baselines** (auditadas
sem vazamento na 2C), para que o modelo parta da regra histórica e aprenda a corrigi-la.

Mantém do protocolo: segmentos temporais (initial/tuning/refit/calibração), disponibilidade
dos rótulos, amostragem `t0_sistematico_diario_v1`, calibração sigmoide e limiar F2 no trecho
de calibração, fallback `historico` para entidades sem histórico elegível e validação
completa da rodada. Não mantém: busca nas duas configurações, família linear e as quatro
rodadas obrigatórias. É um desvio exploratório registrado; não aprova nada pelo §11.

Uso:
  uv run python scripts/rapido/treinar_contexto.py --source fotovoltaica --round V4 \
      --task corte_positivo --slots 8 --run-id rapido-fv-v4-corte-001
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import polars as pl
from lightgbm import LGBMClassifier, LGBMRegressor, early_stopping
from sklearn.metrics import average_precision_score, f1_score

from curtamap.experimental.calendar import load_calendar_manifest
from curtamap.experimental.campaign import (
    KEYS,
    _range,
    _task_filter,
    _validation_filter,
    _weekend_or_holiday,
)
from curtamap.experimental.models import fit_sigmoid_calibrator, optimize_f2_threshold
from curtamap.experimental.resources import peak_rss_bytes
from curtamap.experimental.sampling import emission_mask
from curtamap.experimental.temporal import external_rounds

ROOT = Path(__file__).resolve().parents[2]
EXP = ROOT / "experiments" / "stage2b" / "experimentos"
DATASETS = EXP / "stage2b-datasets" / "scenario=noturno_dia_util"
MAIN_RUNS = {
    ("eolica", "V1"): "main-eolica-v1-002",
    ("eolica", "V2"): "main-eolica-v2-004",
    ("eolica", "V3"): "main-eolica-v3-001",
    ("eolica", "V4"): "main-eolica-v4-001",
    **{("fotovoltaica", f"V{i}"): f"main-fotovoltaica-v{i}-001" for i in range(1, 5)},
}
CAUSES = ("REL", "CNF", "ENE")
BASELINE_IDS = ("ultimo_valor", "mesmo_horario_dia_anterior", "mesmo_horario_recente", "historico")
BASELINE_VALUES = ("prob_positive", "prob_restriction", "volume_positive_mean", "volume_expected")

# Features do §8 já presentes em features.parquet (lista do prompt 2D, §3.1).
NUMERIC = (
    "horizon",
    "t0_hour_sin",
    "t0_hour_cos",
    "tau_hour_sin",
    "tau_hour_cos",
    "t0_weekday",
    "t0_month",
    "t0_day_of_year",
    "tau_weekday",
    "tau_month",
    "tau_day_of_year",
    "last_volume_mwmed",
    "observed_episode_length",
    "history_coverage_28d",
    "history_age_hours",
    "hours_since_positive",
    "hours_since_restriction",
    "positive_frequency_24h",
    "positive_frequency_7d",
    "positive_frequency_28d",
    *[f"{s}_volume_{w}" for w in ("24h", "7d", "28d") for s in ("mean", "std", "max")],
    "restriction_frequency_28d",
    "state_positive_frequency_28d",
    "subsystem_positive_frequency_28d",
    *[f"cause_{c.lower()}_share_28d" for c in CAUSES],
    *[f"same_hour_{d}d_volume" for d in (1, 2, 3, 7)],
    *[f"history_{w}_volume" for w in ("30m", "1h", "24h", "48h", "7d")],
)
BOOLEAN = (
    "last_positive",
    "last_restriction",
    "tau_weekend_or_holiday",
    *[f"same_hour_{d}d_positive" for d in (1, 2, 3, 7)],
    *[f"history_{w}_positive" for w in ("30m", "1h", "24h", "48h", "7d")],
)
CATEGORICAL = ("id_ons", "id_estado", "id_subsistema", "ceg_level", "last_cause")
BASELINE_FEATURES = (
    *[f"b_{b}_{v}" for b in BASELINE_IDS for v in BASELINE_VALUES],
    *[f"b_{b}_native" for b in BASELINE_IDS],
    *[f"b_{b}_cause_{c}" for b in ("ultimo_valor", "historico") for c in CAUSES],
)
TARGET = {
    "corte_positivo": "true_positive",
    "restricao_registrada": "true_restriction",
    "volume_condicional": "true_volume_mwmed",
    "causa": "true_cause",
}
FALLBACK = {
    "corte_positivo": "b_historico_prob_positive",
    "restricao_registrada": "b_historico_prob_restriction",
    "volume_condicional": "b_historico_volume_positive_mean",
}


@dataclass(frozen=True)
class Boundary:
    tuning_start: datetime
    calibration_start: datetime
    cutoff: datetime


def _boundary(source: str, round_id: str) -> Boundary:
    run = MAIN_RUNS[(source, round_id)]
    report = json.loads(next((EXP / run / "reports").glob("*.json")).read_text("utf-8"))
    raw = report["boundaries"]
    return Boundary(
        *(datetime.fromisoformat(raw[k]) for k in ("tuning_start", "calibration_start", "cutoff"))
    )


def _baseline_wide(baselines: pl.LazyFrame) -> pl.LazyFrame:
    """Uma coluna por baseline×valor, unidas pela chave da requisição."""
    wide = None
    for baseline_id in BASELINE_IDS:
        part = baselines.filter(pl.col("baseline_id") == baseline_id).select(
            *KEYS,
            *[pl.col(v).alias(f"b_{baseline_id}_{v}") for v in BASELINE_VALUES],
            pl.col("native_available").cast(pl.Float32).alias(f"b_{baseline_id}_native"),
            *(
                [
                    pl.col("cause_probabilities")
                    .struct.field(c)
                    .alias(f"b_{baseline_id}_cause_{c}")
                    for c in CAUSES
                ]
                if baseline_id in ("ultimo_valor", "historico")
                else []
            ),
        )
        wide = part if wide is None else wide.join(part, on=KEYS, how="inner")
    return wide


class Encoder:
    """Códigos inteiros aprendidos no treino; desconhecido e ausente viram NaN (nativo)."""

    def __init__(self) -> None:
        self.categories: dict[str, dict[str, int]] = {}

    def fit(self, frame: pl.DataFrame) -> Encoder:
        for name in CATEGORICAL:
            values = sorted(str(v) for v in frame[name].drop_nulls().unique().to_list())
            self.categories[name] = {v: i for i, v in enumerate(values)}
        return self

    @property
    def columns(self) -> list[str]:
        return [*NUMERIC, *BOOLEAN, *BASELINE_FEATURES, *CATEGORICAL]

    def matrix(self, frame: pl.DataFrame) -> np.ndarray:
        numeric = frame.select(
            *[pl.col(c).cast(pl.Float32) for c in (*NUMERIC, *BOOLEAN, *BASELINE_FEATURES)],
            *[
                pl.col(c)
                .cast(pl.String)
                .replace_strict(
                    list(self.categories[c]),
                    list(self.categories[c].values()),
                    default=None,
                    return_dtype=pl.Float32,
                )
                for c in CATEGORICAL
            ],
        )
        return numeric.to_numpy().astype(np.float32, copy=False)

    @property
    def categorical_indices(self) -> list[int]:
        start = len(NUMERIC) + len(BOOLEAN) + len(BASELINE_FEATURES)
        return list(range(start, start + len(CATEGORICAL)))


def _estimator(task: str, params: dict[str, Any], n_estimators: int, seed: int) -> Any:
    common = dict(
        learning_rate=params["learning_rate"],
        num_leaves=params["num_leaves"],
        max_depth=params["max_depth"],
        min_child_samples=params["min_child_samples"],
        reg_lambda=params["reg_lambda"],
        colsample_bytree=params["colsample_bytree"],
        subsample=params["subsample"],
        subsample_freq=1 if params["subsample"] < 1 else 0,
        max_bin=params["max_bin"],
        cat_smooth=params["cat_smooth"],
        n_estimators=n_estimators,
        random_state=seed,
        n_jobs=6,
        deterministic=True,
        force_row_wise=True,
        verbosity=-1,
    )
    if task in ("corte_positivo", "restricao_registrada"):
        return LGBMClassifier(objective="binary", **common)
    if task == "causa":
        return LGBMClassifier(objective="multiclass", **common)
    return LGBMRegressor(objective=params.get("objective", "gamma"), **common)


def _target(frame: pl.DataFrame, task: str) -> np.ndarray:
    values = frame[TARGET[task]]
    if task == "causa":
        return values.to_numpy()
    return values.cast(pl.Float64).to_numpy()


def _collect(lazy: pl.LazyFrame) -> pl.DataFrame:
    return lazy.collect(engine="streaming")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, choices=("eolica", "fotovoltaica"))
    parser.add_argument("--round", required=True, choices=("V1", "V2", "V3", "V4"))
    parser.add_argument("--task", required=True, choices=tuple(TARGET))
    parser.add_argument("--slots", type=int, default=8)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--params", default="{}", help="JSON que sobrescreve PARAMS")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--chunk-days", type=int, default=14)
    args = parser.parse_args()

    params = {
        "learning_rate": 0.05,
        "num_leaves": 63,
        "max_depth": 8,
        "min_child_samples": 200,
        "reg_lambda": 1.0,
        "colsample_bytree": 0.8,
        "subsample": 1.0,
        "max_bin": 63,
        "cat_smooth": 10.0,
        "max_trees": 1500,
        **json.loads(args.params),
    }
    out = EXP / args.run_id
    out.mkdir(parents=False, exist_ok=False)
    started = time.perf_counter()
    log: dict[str, Any] = {
        "run_id": args.run_id,
        "kind": "rapido_exploratorio_fora_do_protocolo",
        "source": args.source,
        "round": args.round,
        "task": args.task,
        "slots_per_day_training": args.slots,
        "seed": args.seed,
        "params": params,
        "features": {
            "numeric": NUMERIC,
            "boolean": BOOLEAN,
            "baseline": BASELINE_FEATURES,
            "categorical": CATEGORICAL,
        },
        "started_at": datetime.now().isoformat(timespec="seconds"),
    }

    def phase(name: str) -> None:
        log.setdefault("phases", {})[name] = round(time.perf_counter() - started, 1)
        print(f"[{time.perf_counter() - started:8.1f}s] {name}", flush=True)

    calendar = load_calendar_manifest(ROOT / "configs/experimental/calendar-2023-2026.json")
    round_ = next(r for r in external_rounds() if r.round_id == args.round)
    boundary = _boundary(args.source, args.round)
    log["boundaries"] = {k: str(v) for k, v in vars(boundary).items()}
    base = DATASETS / f"source={args.source}" / "round=development"
    features = pl.scan_parquet((base / "date=*" / "features.parquet").as_posix()).with_columns(
        _weekend_or_holiday(calendar.calendar)
    )
    raw_baselines = pl.scan_parquet((base / "date=*" / "baselines.parquet").as_posix())
    first_t0 = _collect(features.select(pl.col("t0").min())).item()
    sample = emission_mask(args.slots, args.seed)

    def window(start, end) -> pl.Expr:
        return (pl.col("t0") >= start) & (pl.col("t0") + timedelta(hours=24) <= end)

    def segment(start, end, label_cutoff, sampled: bool) -> pl.DataFrame:
        lazy = _range(features, start, end, label_cutoff=label_cutoff).filter(
            _task_filter(args.task)
        )
        side = raw_baselines.filter(window(start, end))
        if sampled:
            lazy, side = lazy.filter(sample), side.filter(sample)
        return _collect(lazy.join(_baseline_wide(side), on=KEYS, how="left"))

    phase("carregar_initial")
    initial = segment(first_t0, boundary.tuning_start, boundary.tuning_start, True)
    tuning = segment(
        boundary.tuning_start, boundary.calibration_start, boundary.calibration_start, False
    )
    encoder = Encoder().fit(initial)
    log["rows"] = {"initial": initial.height, "tuning": tuning.height}
    phase("ajuste_initial")
    x_initial, y_initial = encoder.matrix(initial), _target(initial, args.task)
    x_tuning, y_tuning = encoder.matrix(tuning), _target(tuning, args.task)
    del initial
    stopping_metric = {
        "corte_positivo": "average_precision",
        "restricao_registrada": "average_precision",
        "causa": "multi_logloss",
    }.get(args.task, params.get("stopping_metric", "l1"))
    model = _estimator(args.task, params, params["max_trees"], args.seed)
    model.fit(
        x_initial,
        y_initial,
        eval_set=[(x_tuning, y_tuning)],
        eval_metric=stopping_metric,
        categorical_feature=encoder.categorical_indices,
        callbacks=[early_stopping(50, verbose=False)],
    )
    best = int(model.best_iteration_ or params["max_trees"])
    log["best_iteration"] = best
    log["tuning_score"] = {k: float(v[-1]) for k, v in model.evals_result_["valid_0"].items()}
    del x_initial, y_initial, x_tuning, y_tuning, tuning, model

    phase("carregar_refit")
    refit = segment(first_t0, boundary.calibration_start, boundary.calibration_start, True)
    log["rows"]["refit"] = refit.height
    encoder = Encoder().fit(refit)
    phase("ajuste_refit")
    model = _estimator(args.task, params, best, args.seed)
    model.fit(
        encoder.matrix(refit),
        _target(refit, args.task),
        categorical_feature=encoder.categorical_indices,
    )
    del refit
    importance = sorted(
        zip(encoder.columns, model.booster_.feature_importance("gain").tolist(), strict=True),
        key=lambda item: -item[1],
    )
    log["importance_gain_top30"] = importance[:30]

    calibrator = threshold = None
    if args.task in ("corte_positivo", "restricao_registrada"):
        phase("calibracao")
        calibration = segment(boundary.calibration_start, boundary.cutoff, round_.start, False)
        raw = model.predict_proba(encoder.matrix(calibration))[:, 1]
        target = _target(calibration, args.task).astype(int)
        calibrator = fit_sigmoid_calibrator(raw, target, seed=args.seed)
        probabilities = calibrator.predict(raw) if calibrator else raw
        threshold = optimize_f2_threshold(target, probabilities)
        log["rows"]["calibration"] = calibration.height
        log["threshold"] = threshold
        del calibration
    joblib.dump(
        {"model": model, "encoder": encoder, "calibrator": calibrator, "threshold": threshold},
        out / "model.joblib",
    )

    phase("validacao")
    validation = features.filter(_validation_filter(round_))
    if args.task in ("corte_positivo", "restricao_registrada", "causa"):
        validation = validation.filter(pl.col(TARGET[args.task]).is_not_null())
    if args.task == "causa":
        validation = validation.filter(pl.col("true_cause").is_in(CAUSES))
    parts = []
    day = round_.start
    step = timedelta(days=args.chunk_days)
    while day < round_.end:
        in_chunk = (pl.col("t0") >= day) & (pl.col("t0") < day + step)
        side = raw_baselines.filter(_validation_filter(round_) & in_chunk)
        chunk = _collect(
            validation.filter(in_chunk).join(_baseline_wide(side), on=KEYS, how="left")
        )
        day += step
        if chunk.is_empty():
            continue
        matrix = encoder.matrix(chunk)
        eligible = chunk["eligible_history"].to_numpy()
        keep = list(
            dict.fromkeys(
                [
                    *KEYS,
                    TARGET[args.task],
                    "eligible_history",
                    "true_volume_mwmed",
                    "true_volume_valid",
                ]
            )
        )
        if args.task == "causa":
            proba = model.predict_proba(matrix)
            labels = np.asarray(model.classes_)[proba.argmax(axis=1)]
            frame = chunk.select(*keep).with_columns(
                pl.Series("prediction", labels),
                *[pl.Series(f"p_{c}", proba[:, i]) for i, c in enumerate(model.classes_)],
            )
        elif args.task == "volume_condicional":
            prediction = np.maximum(model.predict(matrix), 0.0)
            fallback = chunk[FALLBACK[args.task]].fill_null(0.0).to_numpy()
            frame = chunk.select(*keep, "b_historico_prob_positive").with_columns(
                pl.Series("prediction", np.where(eligible, prediction, fallback))
            )
        else:
            raw = model.predict_proba(matrix)[:, 1]
            probabilities = calibrator.predict(raw) if calibrator else raw
            fallback = chunk[FALLBACK[args.task]].to_numpy()
            frame = chunk.select(*keep, FALLBACK[args.task]).with_columns(
                pl.Series("prediction", np.where(eligible, probabilities, fallback)),
                pl.Series("raw", raw),
            )
        parts.append(frame)
        print(f"   parte {day.date()} {chunk.height} linhas", flush=True)
        del chunk, matrix
    predictions = pl.concat(parts)
    predictions.write_parquet(out / "predictions.parquet")

    phase("metricas")
    metrics: dict[str, Any] = {"rows": predictions.height}
    if args.task in ("corte_positivo", "restricao_registrada"):
        y = predictions[TARGET[args.task]].cast(pl.Int8).to_numpy()
        model_p = predictions["prediction"].to_numpy()
        base_p = predictions[FALLBACK[args.task]].to_numpy()
        metrics.update(
            {
                "prevalence": float(y.mean()),
                "model_ap": float(average_precision_score(y, model_p)),
                "baseline_historico_ap": float(average_precision_score(y, base_p)),
                "model_brier": float(np.mean((model_p - y) ** 2)),
                "baseline_historico_brier": float(np.mean((base_p - y) ** 2)),
            }
        )
        weeks = predictions.with_columns(
            ((pl.col("t0") - pl.lit(round_.start)).dt.total_days() // 7).alias("week")
        ).partition_by("week")
        diffs_list = []
        for week in weeks:
            target_week = week[TARGET[args.task]].cast(pl.Int8).to_numpy()
            if 0 < target_week.sum() < target_week.size:
                diffs_list.append(
                    average_precision_score(target_week, week["prediction"].to_numpy())
                    - average_precision_score(target_week, week[FALLBACK[args.task]].to_numpy())
                )
        diffs = np.asarray(diffs_list)
        rng = np.random.default_rng(42)
        boots = [rng.choice(diffs, diffs.size).mean() for _ in range(1000)]
        metrics["weekly_ap_diff"] = {
            "weeks": int(diffs.size),
            "mean": float(diffs.mean()),
            "ci95": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
            "wins": int((diffs > 0).sum()),
        }
    elif args.task == "causa":
        y = predictions["true_cause"].to_numpy()
        metrics["model_macro_f1"] = float(
            f1_score(y, predictions["prediction"].to_numpy(), labels=CAUSES, average="macro")
        )
    else:
        positive = predictions.filter(pl.col("true_volume_mwmed") > 0)
        metrics["conditional_mae_positive_rows"] = float(
            (positive["prediction"] - positive["true_volume_mwmed"]).abs().mean()
        )
    log["metrics"] = metrics
    log["peak_rss_gib"] = peak_rss_bytes() / 2**30 if peak_rss_bytes() else None
    phase("fim")
    (out / "resultado.json").write_text(
        json.dumps(log, indent=1, ensure_ascii=False, default=str), "utf-8"
    )
    print(json.dumps(metrics, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
