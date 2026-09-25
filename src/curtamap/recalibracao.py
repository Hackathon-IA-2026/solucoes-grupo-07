"""Reajuste periódico de calibração com os rótulos já liberados pelo ONS.

O modelo fica congelado; só a camada de saída (sigmoide da probabilidade ou fator de viés
do volume) é reajustada a cada ``every_days``, usando apenas linhas cujo rótulo já estava
disponível no instante do reajuste. Regra pré-registrada em
``docs/reports/rapido/recalibracao-regra.md``.
"""

from collections.abc import Callable
from datetime import datetime, timedelta

import numpy as np
import polars as pl

from curtamap.experimental.models import fit_sigmoid_calibrator

Transform = Callable[[pl.DataFrame], np.ndarray]
Fit = Callable[[pl.DataFrame], Transform | None]


def rolling_refit(
    frame: pl.DataFrame,
    start: datetime,
    fit: Fit,
    *,
    every_days: int = 7,
    window_days: int = 28,
    min_days: int = 7,
) -> np.ndarray:
    """Devolve ``prediction`` com as linhas elegíveis reajustadas semana a semana.

    ``frame`` precisa de ``t0``, ``target_available_at``, ``eligible_history`` e
    ``prediction`` (saída congelada, já com fallback). A semana que começa em ``start`` e as
    linhas sem histórico elegível mantêm a previsão salva. Em cada ``R = start + k·every_days``
    ajusta-se ``fit`` na janela elegível com rótulo liberado até ``R``, ``t0 + 24 h ≤ R`` e
    ``t0 ≥ R − window_days``; se ela cobrir menos de ``min_days`` dias, fica o ajuste anterior.
    """
    indexed = frame.with_row_index("_row")
    out = frame["prediction"].to_numpy().astype(float, copy=True)
    eligible = indexed.filter(pl.col("eligible_history"))
    if eligible.is_empty():
        return out
    last_t0 = eligible["t0"].max()
    transform: Transform | None = None
    refresh = start + timedelta(days=every_days)
    while refresh <= last_t0:
        window = eligible.filter(
            (pl.col("target_available_at") <= refresh)
            & (pl.col("t0") + timedelta(hours=24) <= refresh)
            & (pl.col("t0") >= refresh - timedelta(days=window_days))
        )
        if window["t0"].dt.date().n_unique() >= min_days:
            fitted = fit(window.drop("_row"))
            transform = fitted if fitted is not None else transform
        week = eligible.filter(
            (pl.col("t0") >= refresh) & (pl.col("t0") < refresh + timedelta(days=every_days))
        )
        if transform is not None and not week.is_empty():
            out[week["_row"].to_numpy()] = transform(week.drop("_row"))
        refresh += timedelta(days=every_days)
    return out


def sigmoid_refit(*, seed: int) -> Fit:
    """Sigmoide de Platt sobre ``raw`` contra ``target``, como no treino."""

    def fit(window: pl.DataFrame) -> Transform | None:
        calibrator = fit_sigmoid_calibrator(
            window["raw"].to_numpy(), window["target"].to_numpy().astype(int), seed=seed
        )
        if calibrator is None:
            return None
        return lambda week: calibrator.predict(week["raw"].to_numpy())

    return fit


def bias_factor_refit(low: float = 0.5, high: float = 2.0) -> Fit:
    """Fator ``Σ target / Σ prediction`` da janela, limitado a ``[low, high]``."""

    def fit(window: pl.DataFrame) -> Transform | None:
        predicted = float(window["prediction"].sum())
        if predicted <= 0:
            return None
        factor = float(np.clip(float(window["target"].sum()) / predicted, low, high))
        return lambda week: week["prediction"].to_numpy() * factor

    return fit
