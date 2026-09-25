"""Pipeline de volume exploratório: P(corte) × volume condicional, contra os baselines.

Combina as previsões de duas runs de `treinar_contexto.py` (tarefas `corte_positivo` e
`volume_condicional`, mesma fonte e rodada) e avalia o MAE total, o WAPE e o viés sobre todos
os volumes válidos da rodada. Os baselines de volume vêm de `baselines.parquet`, nas mesmas
linhas. Somente leitura; grava `volume-<nome>.json` na run de volume.

Uso: uv run python scripts/rapido/avaliar_volume.py --corte RUN --volume RUN
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import polars as pl

ROOT = Path(__file__).resolve().parents[2]
EXP = ROOT / "experiments" / "stage2b" / "experimentos"
KEYS = ["fonte", "id_ons", "t0", "tau", "horizon"]
BASELINE_IDS = ("ultimo_valor", "mesmo_horario_dia_anterior", "mesmo_horario_recente", "historico")


def _metrics(y: np.ndarray, p: np.ndarray) -> dict:
    error = np.abs(y - p)
    return {
        "mae_full": float(error.mean()),
        "wape": float(error.sum() / y.sum()) if y.sum() > 0 else None,
        "bias": float((p - y).mean()),
        "mae_conditional": float(error[y > 0].mean()) if (y > 0).any() else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corte", required=True)
    parser.add_argument("--volume", required=True)
    args = parser.parse_args()
    corte_log = json.loads((EXP / args.corte / "resultado.json").read_text("utf-8"))
    volume_log = json.loads((EXP / args.volume / "resultado.json").read_text("utf-8"))
    source, round_id = corte_log["source"], corte_log["round"]
    if (volume_log["source"], volume_log["round"]) != (source, round_id):
        raise ValueError("runs de fonte/rodada diferentes")

    probability = pl.read_parquet(EXP / args.corte / "predictions.parquet").select(
        *KEYS, pl.col("prediction").alias("p_corte")
    )
    # A run de volume prevê em todas as linhas da rodada (não só nas positivas).
    conditional = pl.read_parquet(EXP / args.volume / "predictions.parquet").select(
        *KEYS, pl.col("prediction").alias("v_cond"), "true_volume_mwmed", "true_volume_valid"
    )
    frame = conditional.join(probability, on=KEYS, how="inner").filter(
        pl.col("true_volume_valid").fill_null(False) & pl.col("true_volume_mwmed").is_not_null()
    )
    base = ROOT / "experiments/stage2b/experimentos/stage2b-datasets/scenario=noturno_dia_util"
    baselines = (
        pl.scan_parquet(
            (base / f"source={source}/round=development/date=*/baselines.parquet").as_posix()
        )
        .filter((pl.col("t0") >= frame["t0"].min()) & (pl.col("t0") <= frame["t0"].max()))
        .select(*KEYS, "baseline_id", "volume_expected")
        .collect(engine="streaming")
        .pivot(on="baseline_id", index=KEYS, values="volume_expected")
    )
    frame = frame.join(baselines, on=KEYS, how="left")
    y = frame["true_volume_mwmed"].to_numpy()
    result = {
        "source": source,
        "round": round_id,
        "rows": frame.height,
        "pipeline": _metrics(y, (frame["p_corte"] * frame["v_cond"]).to_numpy()),
        "baselines": {b: _metrics(y, frame[b].fill_null(0.0).to_numpy()) for b in BASELINE_IDS},
    }
    name = f"volume-{args.corte}.json"
    (EXP / args.volume / name).write_text(json.dumps(result, indent=1), "utf-8")
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
