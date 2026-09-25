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
# Estado recente do subsistema no instante t0 (variante `sys`): agregados entre usinas da
# mesma fonte e subsistema, só de colunas disponíveis em t0. A informação mais nova tem ~39 h
# (as de 24 h são 87% nulas), por isso o regime recente usa a frequência de 7 dias.
SYSTEMIC = ("sys_last_positive_share", "sys_positive_frequency_7d_mean")
SYSTEMIC_KEYS = ["fonte", "id_subsistema", "t0"]
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


def systemic_state(features: pl.LazyFrame) -> pl.LazyFrame:
    """Uma linha por fonte+subsistema+t0; cada usina pesa uma vez, qualquer que seja o tau."""
    per_plant = features.group_by("fonte", "id_ons", "id_subsistema", "t0").agg(
        pl.col("last_positive").cast(pl.Float64).first(),
        pl.col("positive_frequency_7d").first(),
    )
    return per_plant.group_by(SYSTEMIC_KEYS).agg(
        pl.col("last_positive").mean().alias(SYSTEMIC[0]),
        pl.col("positive_frequency_7d").mean().alias(SYSTEMIC[1]),
    )


class Encoder:
    """Códigos inteiros aprendidos no treino; desconhecido e ausente viram NaN (nativo)."""

    def __init__(self, drop: tuple[str, ...] = (), extra: tuple[str, ...] = ()) -> None:
        self.categories: dict[str, dict[str, int]] = {}
        self.dense = [c for c in (*NUMERIC, *BOOLEAN, *BASELINE_FEATURES, *extra) if c not in drop]
        self.categorical = [c for c in CATEGORICAL if c not in drop]

    @property
    def _categorical(self) -> list[str]:
        # Encoders salvos antes de 25/09 (tarde) não têm a lista e usam todas as categóricas.
        return self.__dict__.get("categorical", list(CATEGORICAL))

    def fit(self, frame: pl.DataFrame) -> Encoder:
        for name in self._categorical:
            values = sorted(str(v) for v in frame[name].drop_nulls().unique().to_list())
            self.categories[name] = {v: i for i, v in enumerate(values)}
        return self

    @property
    def columns(self) -> list[str]:
        return [*self.dense, *self._categorical]

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
                for c in self._categorical
            ],
        )
        return numeric.to_numpy().astype(np.float32, copy=False)

    @property
    def categorical_indices(self) -> list[int]:
        start = len(self.dense)
        return list(range(start, start + len(self._categorical)))


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


def baseline_cause(frame: pl.DataFrame, baseline_id: str) -> np.ndarray:
    """Argmax das probabilidades de causa do baseline, com desempate fixo CNF, ENE, REL."""
    order = ("CNF", "ENE", "REL")
    matrix = np.column_stack(
        [frame[f"b_{baseline_id}_cause_{c}"].fill_null(0.0).to_numpy() for c in order]
    )
    return np.asarray(order)[matrix.argmax(axis=1)]


def predict_corte(bundle: dict[str, Any], frame: pl.DataFrame) -> np.ndarray:
    """Probabilidade calibrada da receita 003; linhas sem histórico elegível usam o `historico`.

    ``bundle`` é o ``model.joblib`` do treino rápido e ``frame`` já traz features, baselines
    largos (`baseline_wide`) e ``tau_weekend_or_holiday``.
    """
    raw = probability_with_offset(bundle["model"], bundle["encoder"].matrix(frame), None)
    calibrator = bundle.get("calibrator")
    probabilities = calibrator.predict(raw) if calibrator is not None else raw
    fallback = frame[HISTORICO_PROBABILITY["corte_positivo"]].to_numpy()
    return np.where(frame["eligible_history"].to_numpy(), probabilities, fallback)


def predict_causa(bundle: dict[str, Any], frame: pl.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Causa prevista pela receita 005 e suas probabilidades (ordem de ``model.classes_``)."""
    model = bundle["model"]
    proba = model.predict_proba(bundle["encoder"].matrix(frame))
    labels = np.asarray(model.classes_)[proba.argmax(axis=1)]
    eligible = frame["eligible_history"].to_numpy()
    return np.where(eligible, labels, baseline_cause(frame, "historico")), proba


# Receita confirmada no teste reservado (25/09/2026, commit de congelamento 8271bf1):
# modelo no corte solar e na causa eólica; baseline nas demais células.
VOLUME_BASELINE = {"fotovoltaica": "historico", "eolica": "mesmo_horario_dia_anterior"}
CAUSE_BASELINE = {"fotovoltaica": "ultimo_valor", "eolica": "historico"}
REPLAY_PASSTHROUGH = (
    *KEYS,
    "id_estado",
    "id_subsistema",
    "eligible_history",
    "target_observed",
    "true_positive",
    "true_volume_mwmed",
    "true_volume_valid",
    "true_cause",
)


def replay_frame(
    frame: pl.DataFrame,
    source: str,
    *,
    corte: dict[str, Any] | None,
    causa: dict[str, Any] | None,
) -> pl.DataFrame:
    """Saída do produto por usina e janela, aplicando a receita congelada de cada célula.

    ``corte`` só é usado na solar (modelo 003) e ``causa`` só na eólica (modelo 005); nas demais
    células entram os baselines. As colunas ``*_fonte`` dizem de onde veio cada número.
    """
    eligible = frame["eligible_history"].to_numpy()
    rows = frame.height
    if source == "fotovoltaica" and corte is not None:
        prob = predict_corte(corte, frame)
        prob_source = np.where(eligible, "modelo_003", "historico")
        threshold = corte.get("threshold")
        alert = [bool(p >= threshold) if e else None for p, e in zip(prob, eligible, strict=True)]
    else:
        prob = frame[HISTORICO_PROBABILITY["corte_positivo"]].to_numpy()
        prob_source = np.full(rows, "historico")
        alert = [None] * rows
    volume_id = VOLUME_BASELINE[source]
    columns = [
        pl.Series("prob_corte", prob, dtype=pl.Float64),
        pl.Series("prob_corte_fonte", prob_source, dtype=pl.String),
        pl.Series("alerta_corte", alert, dtype=pl.Boolean),
        frame[f"b_{volume_id}_volume_expected"].alias("volume_esperado_mwmed"),
        pl.Series("volume_fonte", np.full(rows, volume_id), dtype=pl.String),
    ]
    if source == "eolica" and causa is not None:
        labels, proba = predict_causa(causa, frame)
        columns += [
            pl.Series("causa_prevista", labels, dtype=pl.String),
            pl.Series(
                "causa_fonte", np.where(eligible, "modelo_005", "historico"), dtype=pl.String
            ),
            *[
                pl.Series(f"p_{c}", proba[:, i], dtype=pl.Float64)
                for i, c in enumerate(causa["model"].classes_)
            ],
        ]
    else:
        cause_id = CAUSE_BASELINE[source]
        columns += [
            pl.Series("causa_prevista", baseline_cause(frame, cause_id), dtype=pl.String),
            pl.Series("causa_fonte", np.full(rows, cause_id), dtype=pl.String),
        ]
    present = [c for c in REPLAY_PASSTHROUGH if c in frame.columns]
    return frame.select(present).with_columns(columns)
