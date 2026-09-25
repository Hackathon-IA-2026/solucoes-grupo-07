"""Simula a recalibração periódica sobre as previsões salvas das runs rápidas.

Exploratório, fora do protocolo completo; regra pré-registrada em
``docs/reports/rapido/recalibracao-regra.md``. Nada é retreinado e nenhum arquivo de run é
alterado: os resultados vão para ``experimentos/rapido-recal/<run>.json``. Também calcula a
incerteza semanal da causa (macro-F1 contra o ``historico``).

Uso: ``uv run python scripts/rapido/recalibrar.py [run_id ...]``.
"""

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import polars as pl
from sklearn.metrics import average_precision_score, f1_score

import __main__
from curtamap.contexto import CAUSES, Encoder
from curtamap.experimental.campaign import KEYS
from curtamap.experimental.temporal import external_rounds
from curtamap.recalibracao import bias_factor_refit, rolling_refit, sigmoid_refit

# Joblibs antigos foram salvos com o Encoder definido em __main__.
__main__.Encoder = Encoder

ROOT = Path(__file__).resolve().parents[2]
EXP = ROOT / "experiments" / "stage2b" / "experimentos"
DATASETS = EXP / "stage2b-datasets" / "scenario=noturno_dia_util"
OUT = EXP / "rapido-recal"
DEFAULT_RUNS = [
    *(
        f"rapido-{s}-v{i}-{t}"
        for s in ("fv", "eol")
        for t in ("corte-003", "voltot-004")
        for i in range(1, 5)
    ),
    *(f"rapido-eol-v{i}-causa-005" for i in range(1, 5)),
]
COMPARATOR = {"fotovoltaica": "historico", "eolica": "mesmo_horario_dia_anterior"}


def _weekly_ci(frame: pl.DataFrame, start, score) -> dict:
    diffs = []
    for week in frame.with_columns(
        ((pl.col("t0") - pl.lit(start)).dt.total_days() // 7).alias("week")
    ).partition_by("week"):
        value = score(week)
        if value is not None:
            diffs.append(value)
    diffs = np.asarray(diffs)
    rng = np.random.default_rng(42)
    boots = [rng.choice(diffs, diffs.size).mean() for _ in range(1000)]
    return {
        "weeks": int(diffs.size),
        "mean": float(diffs.mean()),
        "ci95": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
        "wins": int((diffs > 0).sum()),
    }


def _with_availability(predictions: pl.DataFrame, source: str) -> pl.DataFrame:
    lo, hi = predictions["t0"].min(), predictions["t0"].max()
    base = DATASETS / f"source={source}" / "round=development"
    available = (
        pl.scan_parquet((base / "date=*" / "features.parquet").as_posix())
        .filter(pl.col("t0").is_between(lo, hi))
        .select(*KEYS, "target_available_at")
        .collect()
    )
    joined = predictions.join(available, on=KEYS, how="left")
    missing = joined["target_available_at"].null_count()
    if missing or joined.height != predictions.height:
        raise SystemExit(f"junção de disponibilidade falhou: {missing} nulos")
    return joined


def corte(run: str, info: dict, frame: pl.DataFrame, start) -> dict:
    calibrator = joblib.load(EXP / run / "model.joblib")["calibrator"]
    eligible = frame["eligible_history"].to_numpy()
    frozen = calibrator.predict(frame["raw"].to_numpy()[eligible])
    check = float(np.max(np.abs(frozen - frame["prediction"].to_numpy()[eligible])))
    if check > 1e-9:
        raise SystemExit(f"{run}: autoconferência falhou (diferença {check})")
    frame = frame.with_columns(pl.col("true_positive").cast(pl.Float64).alias("target"))
    recal = rolling_refit(frame, start, sigmoid_refit(seed=info["seed"]))
    frame = frame.with_columns(pl.Series("recal", recal))
    y = frame["target"].to_numpy()
    result = {"self_check_max_abs_diff": check, "prevalence": float(y.mean())}
    for name, column in (
        ("frozen", "prediction"),
        ("recal", "recal"),
        ("historico", "b_historico_prob_positive"),
    ):
        p = frame[column].to_numpy()
        result[name] = {
            "ap": float(average_precision_score(y, p)),
            "brier": float(np.mean((p - y) ** 2)),
            "mean_prediction": float(p.mean()),
        }
    reference = info["metrics"]
    if abs(result["frozen"]["ap"] - reference["model_ap"]) > 1e-9:
        raise SystemExit(f"{run}: AP congelado não reproduz o resultado.json")

    def weekly(week: pl.DataFrame):
        target = week["target"].to_numpy()
        if not 0 < target.sum() < target.size:
            return None
        return average_precision_score(target, week["recal"].to_numpy()) - (
            average_precision_score(target, week["b_historico_prob_positive"].to_numpy())
        )

    result["weekly_ap_diff_recal_vs_historico"] = _weekly_ci(frame, start, weekly)
    return result


def volume(run: str, info: dict, frame: pl.DataFrame, start) -> dict:
    frame = frame.with_columns(pl.col("true_volume_mwmed").alias("target"))
    recal = rolling_refit(frame, start, bias_factor_refit())
    y = frame["target"].to_numpy()
    comparator = f"b_{COMPARATOR[info['source']]}_volume_expected"

    def metrics(p: np.ndarray) -> dict:
        error = np.abs(y - p)
        return {
            "mae": float(error.mean()),
            "wape": float(error.sum() / y.sum()),
            "bias": float((p - y).mean()),
        }

    result = {
        "frozen": metrics(frame["prediction"].to_numpy()),
        "recal": metrics(recal),
        "comparator_id": COMPARATOR[info["source"]],
        "comparator": metrics(frame[comparator].fill_null(0.0).to_numpy()),
    }
    if abs(result["frozen"]["mae"] - info["metrics"]["model"]["mae"]) > 1e-9:
        raise SystemExit(f"{run}: MAE congelado não reproduz o resultado.json")
    return result


def causa(run: str, info: dict, frame: pl.DataFrame, start) -> dict:
    def macro(week: pl.DataFrame, column: str) -> float:
        return f1_score(
            week["true_cause"].to_numpy(),
            week[column].to_numpy(),
            labels=CAUSES,
            average="macro",
            zero_division=0,
        )

    return {
        "weekly_macro_f1_diff_vs_historico": _weekly_ci(
            frame, start, lambda w: macro(w, "prediction") - macro(w, "b_historico_pred")
        ),
        "weekly_macro_f1_diff_vs_ultimo_valor": _weekly_ci(
            frame, start, lambda w: macro(w, "prediction") - macro(w, "b_ultimo_valor_pred")
        ),
    }


def main(runs: list[str]) -> int:
    OUT.mkdir(exist_ok=True)
    for run in runs:
        info = json.loads((EXP / run / "resultado.json").read_text("utf-8"))
        start = next(r for r in external_rounds() if r.round_id == info["round"]).start
        predictions = pl.read_parquet(EXP / run / "predictions.parquet")
        if info["task"] == "causa":
            result = causa(run, info, predictions, start)
        else:
            frame = _with_availability(predictions, info["source"])
            del predictions
            handler = corte if info["task"] == "corte_positivo" else volume
            result = handler(run, info, frame, start)
            del frame
        result.update(run_id=run, source=info["source"], round=info["round"], task=info["task"])
        (OUT / f"{run}.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), "utf-8")
        print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or DEFAULT_RUNS))
