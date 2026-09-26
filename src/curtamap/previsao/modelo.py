"""Modelo diário: HistGradientBoosting por fonte sobre as features de `features.py`.

Componentes, todos treinados só com dias-alvo cujo rótulo já estava liberado:

- ocorrência (`p_corte`): classificador binário do corte positivo;
- volume esperado: regressão Poisson direta de E[volume], sem o produto P × condicional que
  explodiu na Etapa 2 anterior;
- volume condicional: Poisson só nas meias-horas com corte;
- p10/p90: regressão quantílica do volume;
- causa condicional ("se houver ordem, qual causa?"): multiclasse REL/CNF/ENE com peso
  balanceado, só em linhas com ordem e causa conhecida.

O que é servido por célula está em `SERVING`, decidido pelo backtest: componentes que não
venceram os baselines são substituídos por eles (`apply_serving`), com proveniência por linha
em `tipo_saida_volume` e `tipo_saida_causa`. `p_restricao` e a origem são baselines
declarados (frequência da usina no slot em 28 dias), não modelos. `p_restricao` nunca fica
abaixo de `p_corte`, porque todo corte exige ordem.
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import joblib
import numpy as np
import polars as pl
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

from curtamap.contracts import (
    FORECAST_SCHEMA,
    HORIZONS,
    PREDICTABLE_CAUSES,
    RESERVED_TEST_START,
    SOURCES,
    STEP,
    validate_forecast,
)
from curtamap.previsao.calendario import Calendar, load_calendar
from curtamap.previsao.features import (
    CAUSE,
    OCCURRENCE,
    VOLUME,
    attach_targets,
    base_from_history,
    build_features,
)

MODEL_VERSION = "diario_hgb_v1"
AVAILABILITY_SCENARIO = "diario_20h_dia_util_feriados"
TRAIN_DAYS = 365
SEED = 0
PARAMS = {
    "max_iter": 300,
    "learning_rate": 0.05,
    "max_leaf_nodes": 31,
    "min_samples_leaf": 200,
    "early_stopping": False,
    "random_state": SEED,
}
CAUSE_PARAMS = {**PARAMS, "max_iter": 200, "min_samples_leaf": 100}
QUANTILES = (0.1, 0.9)
DEFAULT_THRESHOLD = 0.5
# Composição servida por célula, decidida pelo backtest jan–ago/2026 com a regra registrada
# antes dos resultados (docs/reports/nova-abordagem). "modelo" usa o HGB; os demais são
# baselines: "historico" = volume médio da usina no slot em 28 d; "usina_28d" = participação
# de cada causa nas ordens da usina no slot em 28 d, com recurso ao estado em 7 d.
SERVING = {
    "eolica": {"volume": "historico", "causa": "usina_28d"},
    "fotovoltaica": {"volume": "modelo", "causa": "usina_28d"},
}
# Coluna da classe na ordem de PREDICTABLE_CAUSES.
_CAUSE_COLUMNS = [f"p_causa_{c.lower()}" for c in PREDICTABLE_CAUSES]


def _matrix(frame: pl.DataFrame, columns: list[str]) -> np.ndarray:
    return frame.select(pl.col(columns).cast(pl.Float32)).to_numpy()


@dataclass
class SourceModel:
    occurrence: HistGradientBoostingClassifier
    volume: HistGradientBoostingRegressor
    conditional: HistGradientBoostingRegressor
    quantiles: dict[float, HistGradientBoostingRegressor]
    cause: HistGradientBoostingClassifier | None
    threshold: float = DEFAULT_THRESHOLD


def fit_source(rows: pl.DataFrame) -> SourceModel:
    """Treina os componentes de uma fonte com linhas de `attach_targets`."""
    labelled = rows.filter(pl.col("y_corte").is_not_null())
    occurrence = HistGradientBoostingClassifier(**PARAMS).fit(
        _matrix(labelled, OCCURRENCE), labelled["y_corte"].to_numpy()
    )
    x_volume, y_volume = _matrix(labelled, VOLUME), labelled["y_volume"].to_numpy()
    volume = HistGradientBoostingRegressor(loss="poisson", **PARAMS).fit(x_volume, y_volume)
    positive = labelled.filter(pl.col("y_volume") > 0)
    conditional = HistGradientBoostingRegressor(loss="poisson", **PARAMS).fit(
        _matrix(positive, VOLUME), positive["y_volume"].to_numpy()
    )
    quantiles = {
        q: HistGradientBoostingRegressor(loss="quantile", quantile=q, **PARAMS).fit(
            x_volume, y_volume
        )
        for q in QUANTILES
    }
    with_cause = labelled.filter(pl.col("y_causa").is_not_null())
    cause = None
    if with_cause["y_causa"].n_unique() == len(PREDICTABLE_CAUSES):
        cause = HistGradientBoostingClassifier(class_weight="balanced", **CAUSE_PARAMS).fit(
            _matrix(with_cause, CAUSE), with_cause["y_causa"].to_numpy()
        )
    return SourceModel(occurrence, volume, conditional, quantiles, cause)


def predict_source(model: SourceModel, rows: pl.DataFrame) -> pl.DataFrame:
    """Colunas de previsão para as linhas de `build_features` de uma fonte."""
    if rows.is_empty():
        return rows
    x_volume = _matrix(rows, VOLUME)
    low = np.clip(model.quantiles[QUANTILES[0]].predict(x_volume), 0, None)
    high = np.clip(model.quantiles[QUANTILES[1]].predict(x_volume), 0, None)
    expected = model.volume.predict(x_volume)
    columns = {
        "p_corte": model.occurrence.predict_proba(_matrix(rows, OCCURRENCE))[:, 1],
        "volume_esperado_mwmed": expected,
        "volume_condicional_mwmed": model.conditional.predict(x_volume),
        # Quantis de modelos separados podem cruzar; o intervalo precisa conter a média.
        "volume_p10_mwmed": np.minimum(np.minimum(low, high), expected),
        "volume_p90_mwmed": np.maximum(np.maximum(low, high), expected),
    }
    if model.cause is not None:
        proba = model.cause.predict_proba(_matrix(rows, CAUSE))
        order = [list(model.cause.classes_).index(c) for c in PREDICTABLE_CAUSES]
        for name, index in zip(_CAUSE_COLUMNS, order, strict=True):
            columns[name] = proba[:, index]
    return rows.with_columns(pl.Series(k, v, dtype=pl.Float64) for k, v in columns.items())


def apply_serving(rows: pl.DataFrame, serving: dict[str, str]) -> pl.DataFrame:
    """Substitui componentes do modelo pelos baselines escolhidos para a fonte.

    Acrescenta `tipo_saida_volume` e `tipo_saida_causa` por linha. Sem histórico no slot, o
    volume volta ao modelo; sem ordens com causa na usina nem no estado, a causa fica nula.
    """
    if rows.is_empty():
        return rows
    for name in _CAUSE_COLUMNS:
        if name not in rows.columns:
            rows = rows.with_columns(pl.lit(None, pl.Float64).alias(name))
    if serving.get("volume") == "historico":
        known = pl.col("vol_hist_28d").is_not_null()
        rows = rows.with_columns(
            pl.when(known)
            .then(pl.col("vol_hist_28d").cast(pl.Float64))
            .otherwise(pl.col("volume_esperado_mwmed"))
            .alias("volume_esperado_mwmed"),
            pl.when(known)
            .then(pl.lit("baseline_historico_28d"))
            .otherwise(pl.lit("modelo"))
            .alias("tipo_saida_volume"),
        )
    else:
        rows = rows.with_columns(pl.lit("modelo").alias("tipo_saida_volume"))
    if serving.get("causa") == "usina_28d":
        plant = [f"causa_{c.lower()}_28d" for c in PREDICTABLE_CAUSES]
        state = [f"estado_{c.lower()}_7d" for c in PREDICTABLE_CAUSES]
        has_plant = pl.all_horizontal(pl.col(c).is_not_null() for c in plant)
        has_state = pl.all_horizontal(pl.col(c).is_not_null() for c in state)
        rows = rows.with_columns(
            *(
                pl.when(has_plant)
                .then(pl.col(a))
                .when(has_state)
                .then(pl.col(b))
                .cast(pl.Float64)
                .alias(name)
                for name, a, b in zip(_CAUSE_COLUMNS, plant, state, strict=True)
            ),
            pl.when(has_plant)
            .then(pl.lit("baseline_usina_28d"))
            .when(has_state)
            .then(pl.lit("baseline_estado_7d"))
            .alias("tipo_saida_causa"),
        )
    else:
        rows = rows.with_columns(
            pl.when(pl.col("p_causa_rel").is_not_null())
            .then(pl.lit("modelo"))
            .alias("tipo_saida_causa")
        )
    return rows


@dataclass
class DailyModel:
    """Modelos por fonte e metadados de rastreabilidade do artefato."""

    sources: dict[str, SourceModel]
    metadata: dict = field(default_factory=dict)

    @property
    def model_id(self) -> str:
        return f"{MODEL_VERSION}_{self.metadata.get('treino_ate', 'sem_data')}"

    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.model_id}.joblib"
        joblib.dump(self, path)
        path.with_suffix(".json").write_text(
            json.dumps(self.metadata, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def load(path: Path) -> "DailyModel":
        return joblib.load(path)


def training_rows(base: pl.DataFrame, mapping: pl.DataFrame, last_label_day: date) -> pl.DataFrame:
    """Linhas rotuladas de dias-alvo até `last_label_day` (inclusive), nos últimos 365 dias."""
    window = mapping.filter(
        pl.col("dia") <= last_label_day,
        pl.col("dia") > last_label_day - timedelta(days=TRAIN_DAYS),
    )
    return attach_targets(build_features(base, window), base)


def fit(base: pl.DataFrame, mapping: pl.DataFrame, last_label_day: date, **metadata) -> DailyModel:
    """Treina um modelo por fonte com rótulos liberados até `last_label_day`."""
    if base["dia"].max() > last_label_day:
        base = base.filter(pl.col("dia") <= last_label_day)
    rows = training_rows(base, mapping, last_label_day)
    sources = {
        source: fit_source(rows.filter(pl.col("fonte") == source))
        for source in SOURCES
        if rows.filter(pl.col("fonte") == source).height
    }
    info = {
        "versao": MODEL_VERSION,
        "treino_ate": last_label_day.isoformat(),
        "janela_treino_dias": TRAIN_DAYS,
        "linhas_treino": {s: rows.filter(pl.col("fonte") == s).height for s in sources},
        "features_ocorrencia": OCCURRENCE,
        "features_volume": VOLUME,
        "features_causa": CAUSE,
        "parametros": PARAMS,
        "parametros_causa": CAUSE_PARAMS,
        "quantis": QUANTILES,
        "semente": SEED,
        "servico": SERVING,
        **metadata,
    }
    return DailyModel(sources, info)


def forecast_mapping(t0: datetime, data_cutoff: datetime, calendar: Calendar) -> pl.DataFrame:
    """Dias-alvo das 48 meias-horas a partir de `t0`, com L = véspera de `data_cutoff`."""
    last = data_cutoff.date() - timedelta(days=1)
    days = sorted({(t0 + h * STEP).date() for h in range(HORIZONS)})
    return pl.DataFrame(
        {
            "dia": days,
            "ultimo_dia": [last] * len(days),
            "idade": [(d - last).days for d in days],
            "dia_semana": [d.weekday() for d in days],
            "feriado": [int(calendar.is_national_holiday(d)) for d in days],
        },
        schema={
            "dia": pl.Date,
            "ultimo_dia": pl.Date,
            "idade": pl.Int8,
            "dia_semana": pl.Int8,
            "feriado": pl.Int8,
        },
    )


class DailyForecaster:
    """Preditor do produto (`Predictor`): uma emissão gera as 48 meias-horas a partir de t0.

    O uso previsto é a emissão diária às 20h com `t0` = 00h do dia seguinte, mas qualquer
    `t0` na grade funciona. Idades fora do intervalo visto no treino (2 a 7 dias) são
    extrapolação e ficam registradas em `idade_informacao_dias`.
    """

    def __init__(self, model: DailyModel, calendar: Calendar | None = None):
        self.model = model
        self.model_id = model.model_id
        self.calendar = calendar or load_calendar()

    def predict(
        self,
        history: pl.DataFrame,
        t0: datetime,
        data_cutoff: datetime,
        *,
        generated_at: datetime | None = None,
        emitted_at: datetime | None = None,
        allow_reserved_test: bool = False,
    ) -> pl.DataFrame:
        if t0.minute % 30 or t0.second or t0.microsecond:
            raise ValueError("t0 precisa estar na grade de 30 minutos")
        if data_cutoff > t0:
            raise ValueError("corte de dados posterior a t0 vaza informação futura")
        if data_cutoff != datetime.combine(data_cutoff.date(), datetime.min.time()):
            raise ValueError("corte de dados precisa ser o fim de um dia civil")
        if t0 + HORIZONS * STEP > RESERVED_TEST_START and not allow_reserved_test:
            raise ValueError(
                f"período a partir de {RESERVED_TEST_START:%d/%m/%Y} é o teste reservado; "
                "só a validação final congelada pode lê-lo"
            )
        released = history.filter(pl.col("din_instante") + STEP <= data_cutoff)
        base = base_from_history(released)
        mapping = forecast_mapping(t0, data_cutoff, self.calendar)
        features = build_features(base, mapping)
        if features.is_empty():
            return validate_forecast(pl.DataFrame(schema=FORECAST_SCHEMA))
        serving = self.model.metadata.get("servico", SERVING)
        parts = [
            apply_serving(
                predict_source(model, features.filter(pl.col("fonte") == source)),
                serving.get(source, {}),
            )
            for source, model in self.model.sources.items()
        ]
        predicted = pl.concat([p for p in parts if not p.is_empty()], how="diagonal_relaxed")
        return self._to_contract(predicted, t0, data_cutoff, generated_at, emitted_at)

    def _to_contract(self, rows, t0, data_cutoff, generated_at, emitted_at) -> pl.DataFrame:
        source_threshold = {s: m.threshold for s, m in self.model.sources.items()}
        tau = pl.col("dia").cast(pl.Datetime("us")) + pl.duration(
            minutes=30 * pl.col("slot").cast(pl.Int64)
        )
        start = pl.lit(t0).cast(pl.Datetime("us"))
        horizon = ((tau - start).dt.total_minutes() // 30 + 1).cast(pl.Int16)
        cause_present = pl.col("p_causa_rel").is_not_null()
        top_cause = pl.concat_list(_CAUSE_COLUMNS).list.arg_max()
        threshold = pl.col("fonte").replace_strict(source_threshold, return_dtype=pl.Float64)
        p_corte = pl.col("p_corte").clip(0.0, 1.0)
        expected = pl.col("volume_esperado_mwmed").clip(lower_bound=0.0)
        frame = rows.with_columns(tau.alias("tau"), horizon.alias("horizonte")).filter(
            pl.col("horizonte").is_between(1, HORIZONS)
        )
        frame = frame.select(
            "fonte",
            "id_ons",
            start.alias("t0"),
            "horizonte",
            "tau",
            pl.max_horizontal(pl.col("restricao_hist_28d").fill_null(0.0), p_corte)
            .clip(0.0, 1.0)
            .alias("p_restricao"),
            p_corte.alias("p_corte"),
            threshold.alias("limiar_alerta"),
            (p_corte >= threshold).alias("alerta"),
            pl.col("volume_condicional_mwmed").clip(lower_bound=0.0),
            expected.alias("volume_esperado_mwmed"),
            (expected * 0.5).alias("energia_esperada_mwh"),
            pl.col("volume_p10_mwmed").clip(lower_bound=0.0),
            pl.col("volume_p90_mwmed").clip(lower_bound=0.0),
            pl.when(cause_present)
            .then(top_cause.replace_strict(dict(enumerate(PREDICTABLE_CAUSES))))
            .alias("causa_prevista"),
            *(pl.col(name) for name in _CAUSE_COLUMNS),
            pl.when(pl.col("origem_sis_28d").is_not_null())
            .then(
                pl.when(pl.col("origem_sis_28d") >= 0.5)
                .then(pl.lit("SIS"))
                .otherwise(pl.lit("LOC"))
            )
            .alias("origem_prevista"),
            pl.lit(None, pl.String).alias("motivo_sem_previsao"),
            pl.when(~cause_present)
            .then(pl.lit("sem_ordem_com_causa_conhecida_usina_28d_estado_7d"))
            .alias("motivo_sem_causa"),
            pl.lit("modelo").alias("tipo_saida"),
            pl.lit(self.model_id).alias("modelo_id"),
            pl.lit(data_cutoff).cast(pl.Datetime("us")).alias("corte_dados"),
            pl.lit(AVAILABILITY_SCENARIO).alias("cenario_disponibilidade"),
            pl.lit(None, pl.Datetime("us")).alias("instante_observacao"),
            pl.col("cobertura_28d").clip(0.0, 1.0).alias("cobertura_historico"),
            pl.lit(generated_at or datetime.now(UTC).replace(tzinfo=None))
            .cast(pl.Datetime("us"))
            .alias("gerado_em"),
            # Extras (permitidos pelo contrato).
            pl.lit(emitted_at, pl.Datetime("us")).alias("emitido_em"),
            pl.col("idade").cast(pl.Int16).alias("idade_informacao_dias"),
            pl.col("hist_28d").alias("baseline_historico_28d"),
            "tipo_saida_volume",
            "tipo_saida_causa",
        )
        # p_causa_* somam 1 dentro da tolerância; renormaliza contra erro de ponto flutuante.
        total = pl.sum_horizontal(_CAUSE_COLUMNS)
        frame = frame.with_columns(pl.col(c) / total for c in _CAUSE_COLUMNS)
        ordered = frame.select(
            *FORECAST_SCHEMA.names(), *[c for c in frame.columns if c not in FORECAST_SCHEMA]
        )
        return validate_forecast(
            ordered.cast(dict(FORECAST_SCHEMA)).sort(["fonte", "id_ons", "horizonte"])
        )
