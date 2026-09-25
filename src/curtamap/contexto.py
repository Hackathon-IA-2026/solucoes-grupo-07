"""Modelo com contexto: features do §8, saídas dos baselines e correção sobre o `historico`.

Nasce do treino rápido exploratório de 25/09/2026 (`scripts/rapido/treinar_contexto.py`),
depois da Etapa 2C. Fica no pacote para que os modelos serializados possam ser carregados
pelo dashboard e por outros scripts; não é resultado aprovado pelo §11 do protocolo.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import polars as pl

KEYS = ["fonte", "id_ons", "t0", "tau", "horizon"]
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
# Mês e dia do ano confundem tendência com sazonalidade quando há menos de dois anos de
# histórico (solar começa em 04/2024): removidos na variante 003 em diante.
SEASONAL = ("t0_month", "t0_day_of_year", "tau_month", "tau_day_of_year")
HISTORICO_PROBABILITY = {
    "corte_positivo": "b_historico_prob_positive",
    "restricao_registrada": "b_historico_prob_restriction",
}


def baseline_wide(baselines: pl.LazyFrame) -> pl.LazyFrame:
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

    def __init__(self, drop: tuple[str, ...] = ()) -> None:
        self.categories: dict[str, dict[str, int]] = {}
        self.dense = [c for c in (*NUMERIC, *BOOLEAN, *BASELINE_FEATURES) if c not in drop]

    def fit(self, frame: pl.DataFrame) -> Encoder:
        for name in CATEGORICAL:
            values = sorted(str(v) for v in frame[name].drop_nulls().unique().to_list())
            self.categories[name] = {v: i for i, v in enumerate(values)}
        return self

    @property
    def columns(self) -> list[str]:
        return [*self.dense, *CATEGORICAL]

    def matrix(self, frame: pl.DataFrame) -> np.ndarray:
        numeric = frame.select(
            *[pl.col(c).cast(pl.Float32) for c in self.dense],
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
        start = len(self.dense)
        return list(range(start, start + len(CATEGORICAL)))


def historico_offset(frame: pl.DataFrame, task: str) -> np.ndarray:
    """Logit limitado da probabilidade do `historico`; ausência vira 0,5 (logit zero)."""
    p = frame[HISTORICO_PROBABILITY[task]].fill_null(0.5).cast(pl.Float64).to_numpy()
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def probability_with_offset(
    model: Any, matrix: np.ndarray, offset: np.ndarray | None
) -> np.ndarray:
    """Probabilidade do classificador binário, somando o offset ao escore bruto quando houver."""
    if offset is None:
        return model.predict_proba(matrix)[:, 1]
    return 1 / (1 + np.exp(-(model.predict(matrix, raw_score=True) + offset)))
