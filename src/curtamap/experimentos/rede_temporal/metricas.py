"""Métricas por fonte × mês e agregadas, nas mesmas linhas para todos os candidatos.

Unidades: volume em MWmed por meia-hora; energia = MWmed × 0,5 (MWh). Agregações:

- **por meia-hora:** MAE e WAPE sobre todas as linhas avaliadas;
- **diário:** soma por `fonte + id_ons + dia` antes do WAPE, como `previsao.avaliacao`;
- **dias com e sem corte:** a partição usa a energia real do dia da usina. WAPE só existe nos
  dias com corte; nos dias sem corte, reporta-se a energia prevista (falso volume);
- **agregado:** linhas de todos os meses juntas (não é média dos meses). A média mensal, usada
  na decisão, é calculada à parte no relatório.

WAPE não é "100 − acerto": acima de 1 significa erro total maior que a energia real.
"""

from collections.abc import Sequence

import numpy as np
import polars as pl
from sklearn.metrics import average_precision_score

from curtamap.experimentos.rede_temporal.limiar import alert_counts

DAY_KEY = ["fonte", "id_ons", "dia"]


def _wape(actual: np.ndarray, predicted: np.ndarray) -> float:
    total = float(np.abs(actual).sum())
    return float(np.abs(actual - predicted).sum() / total) if total else float("nan")


def occurrence_metrics(y: np.ndarray, p: np.ndarray, threshold: float) -> dict:
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    c = alert_counts(y, p, threshold)
    alerts, positives = c["vp"] + c["fp"], c["vp"] + c["fn"]
    precision = c["vp"] / alerts if alerts else float("nan")
    recall = c["vp"] / positives if positives else float("nan")
    denominator = 2 * c["vp"] + c["fp"] + c["fn"]
    return {
        "prevalencia": float(y.mean()),
        "ap": float(average_precision_score(y, p)) if 0 < y.sum() < len(y) else float("nan"),
        "brier": float(np.mean((np.clip(p, 0, 1) - y) ** 2)),
        "limiar": float(threshold),
        **c,
        "precisao": precision,
        "recall": recall,
        "f1": 2 * c["vp"] / denominator if denominator else float("nan"),
        "acuracia": (c["vp"] + c["vn"]) / len(y),
    }


def volume_metrics(frame: pl.DataFrame, column: str) -> dict:
    # Float64 antes de agregar: somas em Float32 variam com a ordem entre threads.
    frame = frame.with_columns(pl.col("y_volume", column).cast(pl.Float64))
    y = frame["y_volume"].to_numpy()
    v = frame[column].to_numpy().astype(float)
    daily = frame.group_by(DAY_KEY).agg(pl.col("y_volume").sum(), pl.col(column).sum())
    y_day, v_day = daily["y_volume"].to_numpy(), daily[column].to_numpy()
    cut = y_day > 0
    return {
        "mae_mwmed": float(np.abs(y - v).mean()),
        "wape": _wape(y, v),
        "wape_diario": _wape(y_day, v_day),
        "vies": float(v.sum() / y.sum() - 1) if y.sum() else float("nan"),
        "energia_real_mwh": float(y.sum() * 0.5),
        "energia_prevista_mwh": float(v.sum() * 0.5),
        "usina_dias_com_corte": int(cut.sum()),
        "wape_diario_dias_com_corte": _wape(y_day[cut], v_day[cut]),
        "usina_dias_sem_corte": int((~cut).sum()),
        "energia_prevista_dias_sem_corte_mwh": float(v_day[~cut].sum() * 0.5),
    }


def _rows(frame: pl.DataFrame, candidates: Sequence[str], thresholds: dict, period: str) -> list:
    columns = [f"{k}_{c}" for c in candidates for k in ("p", "v") if f"{k}_{c}" in frame.columns]
    covered = frame.filter(pl.all_horizontal(pl.col(c).is_not_null() for c in columns))
    source = frame["fonte"][0]
    out = []
    for candidate in candidates:
        row = {
            "fonte": source,
            "periodo": period,
            "candidato": candidate,
            "n": covered.height,
            "linhas_sem_previsao": frame.height - covered.height,
        }
        if f"p_{candidate}" in covered.columns:
            row |= occurrence_metrics(
                covered["y_corte"].to_numpy(),
                covered[f"p_{candidate}"].to_numpy(),
                thresholds.get((source, candidate), 0.5),
            )
        if f"v_{candidate}" in covered.columns:
            row |= volume_metrics(covered, f"v_{candidate}")
        out.append(row)
    return out


def metric_table(
    predictions: pl.DataFrame, candidates: Sequence[str], thresholds: dict
) -> pl.DataFrame:
    """Uma linha por fonte × período × candidato; `thresholds[(fonte, candidato)]`."""
    rows = []
    for _, by_source in sorted(predictions.partition_by("fonte", as_dict=True).items()):
        for (month,), frame in sorted(by_source.partition_by("mes", as_dict=True).items()):
            rows += _rows(frame, candidates, thresholds, month.isoformat())
        rows += _rows(by_source, candidates, thresholds, "agregado")
    return pl.DataFrame(rows, infer_schema_length=None)
