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

from curtamap.contexto import (
    BASELINE_FEATURES,
    BASELINE_IDS,
    BOOLEAN,
    CATEGORICAL,
    CAUSES,
    HISTORICO_PROBABILITY,
    NUMERIC,
    Encoder,
    baseline_wide,
    historico_offset,
    probability_with_offset,
)
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
TARGET = {
    "corte_positivo": "true_positive",
    "restricao_registrada": "true_restriction",
    "volume_condicional": "true_volume_mwmed",
    "causa": "true_cause",
    "volume_total": "true_volume_mwmed",
}
FALLBACK = {
    "corte_positivo": "b_historico_prob_positive",
    "restricao_registrada": "b_historico_prob_restriction",
    "volume_condicional": "b_historico_volume_positive_mean",
    "volume_total": "b_historico_volume_expected",
}
VOLUME_VALID = (
    pl.col("target_observed")
    & pl.col("true_volume_valid").fill_null(False)
    & pl.col("true_volume_mwmed").is_not_null()
)


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
        return LGBMClassifier(
            objective="multiclass", class_weight=params.get("class_weight"), **common
        )
    if task == "volume_total":
        return LGBMRegressor(
            objective="tweedie",
            tweedie_variance_power=params.get("tweedie_variance_power", 1.5),
            **common,
        )
    return LGBMRegressor(objective=params.get("objective", "gamma"), **common)


def _target(frame: pl.DataFrame, task: str) -> np.ndarray:
    values = frame[TARGET[task]]
    if task == "causa":
        return values.to_numpy()
    return values.cast(pl.Float64).to_numpy()


def _volume_offset(frame: pl.DataFrame) -> np.ndarray:
    """Log do volume esperado do `historico` (ligação log do Tweedie)."""
    expected = frame["b_historico_volume_expected"].fill_null(0.0).cast(pl.Float64).to_numpy()
    return np.log(np.maximum(expected, 1e-3))


def _offset(frame: pl.DataFrame, task: str, enabled: bool) -> np.ndarray | None:
    if enabled and task == "volume_total":
        return _volume_offset(frame)
    if not enabled or task not in HISTORICO_PROBABILITY:
        return None
    return historico_offset(frame, task)


def _baseline_cause(frame: pl.DataFrame, baseline_id: str) -> np.ndarray:
    """Argmax das probabilidades de causa do baseline, com desempate fixo CNF, ENE, REL."""
    order = ("CNF", "ENE", "REL")
    matrix = np.column_stack(
        [frame[f"b_{baseline_id}_cause_{c}"].fill_null(0.0).to_numpy() for c in order]
    )
    return np.asarray(order)[matrix.argmax(axis=1)]


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
    parser.add_argument(
        "--offset", action="store_true", help="parte do logit do historico (init_score)"
    )
    parser.add_argument("--no-categorical", action="store_true")
    parser.add_argument("--train-months", type=int, default=None)
    parser.add_argument("--drop", default="", help="features removidas, separadas por vírgula")
    args = parser.parse_args()
    drop = tuple(name for name in args.drop.split(",") if name)

    def categorical(encoder: Encoder) -> list[int] | str:
        # Contorno do erro interno `best_split_info.left_count > 0` do LightGBM em regressão
        # com categóricas nativas: os códigos entram como numéricos.
        return [] if args.no_categorical else encoder.categorical_indices

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
        "offset_historico": args.offset,
        "dropped_features": drop,
        "native_categorical": not args.no_categorical,
        "train_months": args.train_months,
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
            VOLUME_VALID if args.task == "volume_total" else _task_filter(args.task)
        )
        side = raw_baselines.filter(window(start, end))
        if sampled:
            lazy, side = lazy.filter(sample), side.filter(sample)
        return _collect(lazy.join(baseline_wide(side), on=KEYS, how="left"))

    phase("carregar_initial")

    def train_start(end: datetime) -> datetime:
        # Janela recente: N×30 dias antes do fim do segmento (initial ou refit), com o
        # mesmo comprimento nos dois; sem a opção, todo o histórico desde o primeiro t0.
        if args.train_months is None:
            return first_t0
        return max(first_t0, end - timedelta(days=30 * args.train_months))

    initial = segment(
        train_start(boundary.tuning_start), boundary.tuning_start, boundary.tuning_start, True
    )
    tuning = segment(
        boundary.tuning_start, boundary.calibration_start, boundary.calibration_start, False
    )
    encoder = Encoder(drop).fit(initial)
    log["rows"] = {"initial": initial.height, "tuning": tuning.height}
    phase("ajuste_initial")
    x_initial, y_initial = encoder.matrix(initial), _target(initial, args.task)
    x_tuning, y_tuning = encoder.matrix(tuning), _target(tuning, args.task)
    offset_initial = _offset(initial, args.task, args.offset)
    offset_tuning = _offset(tuning, args.task, args.offset)
    del initial
    stopping_metric = {
        "corte_positivo": "average_precision",
        "restricao_registrada": "average_precision",
        "causa": "multi_logloss",
        "volume_total": "tweedie",
    }.get(args.task, params.get("stopping_metric", "gamma_deviance"))
    model = _estimator(args.task, params, params["max_trees"], args.seed)
    model.fit(
        x_initial,
        y_initial,
        init_score=offset_initial,
        eval_set=[(x_tuning, y_tuning)],
        eval_init_score=None if offset_tuning is None else [offset_tuning],
        eval_metric=stopping_metric,
        categorical_feature=categorical(encoder),
        callbacks=[early_stopping(50, verbose=False)],
    )
    best = int(model.best_iteration_ or params["max_trees"])
    log["best_iteration"] = best
    log["tuning_score"] = {k: float(v[-1]) for k, v in model.evals_result_["valid_0"].items()}
    del x_initial, y_initial, x_tuning, y_tuning, tuning, model

    phase("carregar_refit")
    refit = segment(
        train_start(boundary.calibration_start),
        boundary.calibration_start,
        boundary.calibration_start,
        True,
    )
    log["rows"]["refit"] = refit.height
    encoder = Encoder(drop).fit(refit)
    phase("ajuste_refit")
    model = _estimator(args.task, params, best, args.seed)
    model.fit(
        encoder.matrix(refit),
        _target(refit, args.task),
        init_score=_offset(refit, args.task, args.offset),
        categorical_feature=categorical(encoder),
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
        raw = probability_with_offset(
            model, encoder.matrix(calibration), _offset(calibration, args.task, args.offset)
        )
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
    if args.task == "volume_total":
        validation = validation.filter(VOLUME_VALID)
    parts = []
    day = round_.start
    step = timedelta(days=args.chunk_days)
    while day < round_.end:
        in_chunk = (pl.col("t0") >= day) & (pl.col("t0") < day + step)
        side = raw_baselines.filter(_validation_filter(round_) & in_chunk)
        chunk = _collect(validation.filter(in_chunk).join(baseline_wide(side), on=KEYS, how="left"))
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
            baseline_labels = {b: _baseline_cause(chunk, b) for b in ("ultimo_valor", "historico")}
            frame = chunk.select(*keep).with_columns(
                pl.Series("prediction", np.where(eligible, labels, baseline_labels["historico"])),
                *[pl.Series(f"b_{b}_pred", v) for b, v in baseline_labels.items()],
                *[pl.Series(f"p_{c}", proba[:, i]) for i, c in enumerate(model.classes_)],
            )
        elif args.task == "volume_total":
            offset = _offset(chunk, args.task, args.offset)
            raw_log = model.predict(matrix, raw_score=True)
            prediction = np.exp(raw_log + offset) if offset is not None else np.exp(raw_log)
            fallback = chunk[FALLBACK[args.task]].fill_null(0.0).to_numpy()
            frame = chunk.select(
                *keep, *[f"b_{b}_volume_expected" for b in BASELINE_IDS]
            ).with_columns(pl.Series("prediction", np.where(eligible, prediction, fallback)))
        elif args.task == "volume_condicional":
            prediction = np.maximum(model.predict(matrix), 0.0)
            fallback = chunk[FALLBACK[args.task]].fill_null(0.0).to_numpy()
            frame = chunk.select(*keep, "b_historico_prob_positive").with_columns(
                pl.Series("prediction", np.where(eligible, prediction, fallback))
            )
        else:
            raw = probability_with_offset(model, matrix, _offset(chunk, args.task, args.offset))
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
        for name, column in (
            ("model", "prediction"),
            ("baseline_ultimo_valor", "b_ultimo_valor_pred"),
            ("baseline_historico", "b_historico_pred"),
        ):
            predicted = predictions[column].to_numpy()
            metrics[f"{name}_macro_f1"] = float(
                f1_score(y, predicted, labels=CAUSES, average="macro", zero_division=0)
            )
            metrics[f"{name}_recall"] = {
                c: float(((predicted == c) & (y == c)).sum() / max((y == c).sum(), 1))
                for c in CAUSES
            }
    elif args.task == "volume_total":
        y = predictions["true_volume_mwmed"].to_numpy()

        def volume(p: np.ndarray) -> dict[str, float]:
            error = np.abs(y - p)
            return {
                "mae": float(error.mean()),
                "wape": float(error.sum() / y.sum()),
                "bias": float((p - y).mean()),
            }

        metrics["model"] = volume(predictions["prediction"].to_numpy())
        for b in BASELINE_IDS:
            metrics[f"baseline_{b}"] = volume(
                predictions[f"b_{b}_volume_expected"].fill_null(0.0).to_numpy()
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
