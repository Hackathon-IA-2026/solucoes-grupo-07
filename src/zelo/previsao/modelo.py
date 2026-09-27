"""Modelo diário: HistGradientBoosting de ocorrência por fonte sobre as features de `features.py`.

O produto prevê só **quando** haverá corte (`p_corte`), treinado apenas com dias-alvo cujo
rótulo já estava liberado. Volume e causa não são modelos (decisão de 26/09/2026,
`docs/decisao-foco-ocorrencia-causa.md`):

- causa: participação de cada causa nas ordens da usina no slot em 28 dias, com recurso ao
  estado em 7 dias (`attach_cause_baseline`), com proveniência em `tipo_saida_causa`;
- volume: não é previsto; as colunas de volume do contrato ficam nulas e
  `tipo_saida_volume` é `nao_previsto`.

`p_restricao` e a origem são baselines declarados (frequência da usina no slot em 28 dias).
`p_restricao` nunca fica abaixo de `p_corte`, porque todo corte exige ordem.
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import joblib
import numpy as np
import polars as pl
from sklearn.ensemble import HistGradientBoostingClassifier

from zelo.contracts import (
    FORECAST_SCHEMA,
    HORIZONS,
    PREDICTABLE_CAUSES,
    RESERVED_TEST_START,
    SOURCES,
    STEP,
    validate_forecast,
)
from zelo.previsao.calendario import Calendar, load_calendar
from zelo.previsao.features import (
    OCCURRENCE,
    attach_targets,
    base_from_history,
    build_features,
)

MODEL_VERSION = "diario_ocorrencia_v1"
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
DEFAULT_THRESHOLD = 0.5
# Coluna da classe na ordem de PREDICTABLE_CAUSES.
_CAUSE_COLUMNS = [f"p_causa_{c.lower()}" for c in PREDICTABLE_CAUSES]


def _matrix(frame: pl.DataFrame, columns: list[str]) -> np.ndarray:
    return frame.select(pl.col(columns).cast(pl.Float32)).to_numpy()


@dataclass
class SourceModel:
    occurrence: HistGradientBoostingClassifier
    threshold: float = DEFAULT_THRESHOLD


def fit_source(rows: pl.DataFrame) -> SourceModel:
    """Treina o classificador de ocorrência de uma fonte com linhas de `attach_targets`."""
    labelled = rows.filter(pl.col("y_corte").is_not_null())
    occurrence = HistGradientBoostingClassifier(**PARAMS).fit(
        _matrix(labelled, OCCURRENCE), labelled["y_corte"].to_numpy()
    )
    return SourceModel(occurrence)


def predict_source(model: SourceModel, rows: pl.DataFrame) -> pl.DataFrame:
    """`p_corte` para as linhas de `build_features` de uma fonte."""
    if rows.is_empty():
        return rows
    p_corte = model.occurrence.predict_proba(_matrix(rows, OCCURRENCE))[:, 1]
    return rows.with_columns(pl.Series("p_corte", p_corte, dtype=pl.Float64))


def attach_cause_baseline(rows: pl.DataFrame) -> pl.DataFrame:
    """Causa pela participação nas ordens da usina em 28 d, com recurso ao estado em 7 d.

    Acrescenta `p_causa_*` e `tipo_saida_causa`; sem ordens com causa na usina nem no estado,
    a causa fica nula.
    """
    if rows.is_empty():
        return rows
    plant = [f"causa_{c.lower()}_28d" for c in PREDICTABLE_CAUSES]
    state = [f"estado_{c.lower()}_7d" for c in PREDICTABLE_CAUSES]
    has_plant = pl.all_horizontal(pl.col(c).is_not_null() for c in plant)
    has_state = pl.all_horizontal(pl.col(c).is_not_null() for c in state)
    return rows.with_columns(
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
        "parametros": PARAMS,
        "semente": SEED,
        "servico": {"ocorrencia": "modelo", "causa": "usina_28d", "volume": "nao_previsto"},
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
        parts = [
            attach_cause_baseline(predict_source(model, features.filter(pl.col("fonte") == source)))
            for source, model in self.model.sources.items()
        ]
        predicted = pl.concat([p for p in parts if not p.is_empty()], how="diagonal_relaxed")
        return self._to_contract(predicted, t0, data_cutoff, generated_at, emitted_at)

    def from_rows(
        self,
        rows: pl.DataFrame,
        t0: datetime,
        data_cutoff: datetime,
        *,
        generated_at: datetime | None = None,
        emitted_at: datetime | None = None,
    ) -> pl.DataFrame:
        """Contrato a partir de linhas já pontuadas (features + `p_corte`), sem repontuar.

        Serve para publicar avisos já emitidos (por exemplo, os da validação de setembro)
        com o `p_corte` exatamente igual ao avaliado.
        """
        scored = pl.concat(
            [
                attach_cause_baseline(rows.filter(pl.col("fonte") == source))
                for source in self.model.sources
            ],
            how="diagonal_relaxed",
        )
        return self._to_contract(scored, t0, data_cutoff, generated_at, emitted_at)

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
        no_volume = pl.lit(None, pl.Float64)
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
            # Volume não é previsto: as colunas do contrato ficam nulas.
            no_volume.alias("volume_condicional_mwmed"),
            no_volume.alias("volume_esperado_mwmed"),
            no_volume.alias("energia_esperada_mwh"),
            no_volume.alias("volume_p10_mwmed"),
            no_volume.alias("volume_p90_mwmed"),
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
            pl.col("ref_hist_28d").cast(pl.Float64).alias("potencial_referencia_mwmed"),
            pl.lit("nao_previsto").alias("tipo_saida_volume"),
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
