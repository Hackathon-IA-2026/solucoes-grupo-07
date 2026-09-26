"""Dobras e métricas compartilhadas pelos experimentos da v2 (fora do produto).

Lê o cache de `cache_features_v2.py`. Cada dobra mensal M treina com dias-alvo em
(L_M − janela, L_M], sendo L_M o último dia liberado na emissão da véspera de 1º de M, e
testa nos dias de M: o mesmo recorte de `curtamap.previsao.avaliacao.backtest_month`.
"""

from datetime import date, timedelta

import numpy as np
import polars as pl

from curtamap.config import settings
from curtamap.previsao.calendario import load_calendar
from curtamap.previsao.features import release_map

CACHE = settings.data_dir / "interim" / "previsao" / "v2"
MONTHS = [date(2026, m, 1) for m in range(1, 9)]
NOT_FEATURES = {"fonte", "id_ons", "id_estado", "dia", "ultimo_dia"}
# A ordem das linhas muda a amostra que o HGB usa para os limites dos bins: ordenar como em
# `modelo.fit` reproduz a v1 exatamente (fevereiro: WAPE diário 1,727 fora de ordem, 1,655).
ORDER = ["fonte", "id_ons", "dia", "slot"]


def load(source: str) -> pl.DataFrame:
    frame = pl.read_parquet(CACHE / f"features_{source}.parquet").sort(ORDER)
    numeric = [c for c in frame.columns if c not in NOT_FEATURES and not c.startswith("y_")]
    return frame.with_columns(pl.col(numeric).cast(pl.Float32))


def pool(frame: pl.DataFrame) -> list[str]:
    """Todas as colunas candidatas a feature, na ordem do cache."""
    return [c for c in frame.columns if c not in NOT_FEATURES and not c.startswith("y_")]


def folds(frame: pl.DataFrame, window_days: int = 365):
    """(mês, último dia de rótulo, treino, teste) para as 8 dobras de jan–ago/2026."""
    calendar = load_calendar()
    for month in MONTHS:
        following = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
        last_label = release_map([month], calendar)["ultimo_dia"].item()
        train = frame.filter(
            pl.col("dia") <= last_label,
            pl.col("dia") > last_label - timedelta(days=window_days),
        )
        test = frame.filter(pl.col("dia") >= month, pl.col("dia") < following)
        yield month, last_label, train, test


def matrix(frame: pl.DataFrame, columns: list[str]) -> np.ndarray:
    return frame.select(columns).to_numpy()


def wape(actual: np.ndarray, predicted: np.ndarray) -> float:
    total = float(np.abs(actual).sum())
    return float(np.abs(actual - predicted).sum() / total) if total else float("nan")


def volume_metrics(test: pl.DataFrame, predicted: np.ndarray) -> dict:
    """WAPE diário por usina × dia (principal), WAPE e RMSE da meia-hora e viés."""
    frame = test.select("id_ons", "dia", "y_volume").with_columns(
        pl.Series("_p", predicted, dtype=pl.Float64)
    )
    daily = frame.group_by("id_ons", "dia").agg(pl.col("y_volume").sum(), pl.col("_p").sum())
    y = frame["y_volume"].to_numpy()
    return {
        "wape_diario": wape(daily["y_volume"].to_numpy(), daily["_p"].to_numpy()),
        "wape": wape(y, predicted),
        "rmse": float(np.sqrt(np.mean((y - predicted) ** 2))),
        "vies": float(predicted.sum() / y.sum() - 1) if y.sum() else float("nan"),
    }
