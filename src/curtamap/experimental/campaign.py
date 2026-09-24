"""Campanha V1–V4 e sensibilidade +24h executadas por partes, sem materializar a rodada.

A semântica é a da implementação materializada original, preservada como oráculo em
``tests/reference_campaign_stage2b.py`` e exigida por testes de paridade: mesmos modelos,
previsões (conteúdo, colunas e ordem de linhas), métricas e diagnósticos. Mudou apenas a
forma de execução:

- features e baselines entram como ``LazyFrame`` (``DataFrame`` também é aceito) e cada
  leitura projeta só as colunas necessárias, com filtros empurrados para o Parquet;
- conjuntos globais (IDs anteriores a ``U``, painel fixo, verdade para episódios e cauda p99)
  vêm de coletas pequenas e são aplicados como expressões ou junções por parte;
- os trechos de ajuste são coletados por tarefa, no motor padrão, preservando a ordem;
- a validação é percorrida uma única vez em partes de ``chunk_days`` dias de ``t0``; cada
  parte alimenta todos os modelos e é gravada em Parquet incremental (``ParquetStream``);
- métricas usam a previsão completa de um modelo por vez, relida do Parquet com projeção,
  nunca médias entre partes; recortes são gerados um de cada vez;
- combinações de volume e baselines são montados por parte a partir de um Parquet temporário
  da validação, gravado fora do run (``scratch_dir``) e removido ao final.

A divisão só é usada quando as linhas de cada parte formam um trecho contíguo e crescente da
ordem original (caso do leiaute diário do dataset); do contrário usa-se uma parte única, o que
preserva a ordem ao custo de memória. O relatório ganha o campo ``execution`` com o número de
partes e o pico de memória residente do processo (``peak_rss_bytes``) ao final da rodada.
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from contextlib import ExitStack
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import polars as pl

from curtamap.experimental.artifacts import ParquetStream, RunStore
from curtamap.experimental.metrics import cause_metrics, occurrence_metrics, volume_metrics
from curtamap.experimental.models import expected_volume
from curtamap.experimental.resources import peak_rss_bytes
from curtamap.experimental.runner import CATEGORICAL_FEATURES, NUMERIC_FEATURES, TASKS
from curtamap.experimental.sampling import METHOD, emission_mask
from curtamap.experimental.temporal import AvailabilityScenario, BusinessCalendar, ExternalRound
from curtamap.experimental.training import DatasetSplit, internal_boundaries, train_family

DEFAULT_CHUNK_DAYS = 7
KEYS = ["fonte", "id_ons", "t0", "tau", "horizon"]
TASK_IDS = ("corte_positivo", "restricao_registrada", "volume_condicional", "causa")
FAMILIES = ("linear", "lightgbm")
OCCURRENCE_TASKS = frozenset({"corte_positivo", "restricao_registrada"})
TASK_KIND = {
    "corte_positivo": "occurrence",
    "restricao_registrada": "occurrence",
    "volume_condicional": "volume",
    "causa": "cause",
}
FALLBACK_COLUMN = {
    "corte_positivo": "prob_positive",
    "restricao_registrada": "prob_restriction",
    "volume_condicional": "volume_positive_mean",
    "causa": "cause_prediction",
}
METRIC_TARGET = {
    "corte_positivo": "true_positive",
    "restricao_registrada": "true_restriction",
    "volume_condicional": "true_volume_mwmed",
    "volume_pipeline": "true_volume_mwmed",
    "causa": "true_cause",
}
TRUTH_COLUMNS = [
    "true_positive",
    "true_restriction",
    "true_volume_mwmed",
    "true_volume_valid",
    "true_cause",
]
CONTEXT_COLUMNS = [
    "eligible_history",
    "history_age_hours",
    "entity_new",
    "panel_fixed",
    "tau_weekend_or_holiday",
]
DIAGNOSTIC_COLUMNS = ["episode_start", "post_episode_zero", "volume_tail", "episode_id"]
# Colunas cuja presença e valores definem os recortes de ``_slice_frames``.
SLICE_COLUMNS = (
    "horizon",
    "eligible_history",
    "entity_new",
    "panel_fixed",
    "tau_weekend_or_holiday",
    "history_age_hours",
    "episode_start",
    "post_episode_zero",
    "volume_tail",
)
MODEL_INPUT_COLUMNS = list(
    dict.fromkeys(
        [*KEYS, *NUMERIC_FEATURES, *CATEGORICAL_FEATURES, *TRUTH_COLUMNS, *CONTEXT_COLUMNS[:2]]
    )
)
CAMPAIGN_PREDICTION_COLUMNS = [
    *KEYS,
    "prediction",
    *TRUTH_COLUMNS,
    *CONTEXT_COLUMNS,
    *DIAGNOSTIC_COLUMNS,
]
CAMPAIGN_VALIDATION_COLUMNS = [*KEYS, *TRUTH_COLUMNS, *CONTEXT_COLUMNS, *DIAGNOSTIC_COLUMNS]
CAMPAIGN_PIPELINE_COLUMNS = [*KEYS, "true_volume_mwmed", *CONTEXT_COLUMNS, *DIAGNOSTIC_COLUMNS]
SENSITIVITY_PIPELINE_COLUMNS = [*KEYS, "true_volume_mwmed", *CONTEXT_COLUMNS]
BASELINE_TASKS = (
    ("corte_positivo", "prob_positive"),
    ("restricao_registrada", "prob_restriction"),
    ("volume_pipeline", "volume_expected"),
    ("causa", "cause_prediction"),
)


def _range(
    frame: pl.LazyFrame,
    start,
    end,
    *,
    label_cutoff=None,
) -> pl.LazyFrame:
    selected = frame.filter(
        (pl.col("t0") >= start)
        & (pl.col("t0") + timedelta(hours=24) <= end)
        & pl.col("eligible_history")
    )
    if label_cutoff is not None:
        selected = selected.filter(pl.col("target_available_at") <= label_cutoff)
    return selected


def _task_filter(task_id: str) -> pl.Expr:
    """Mesmo filtro de ``runner._task_frame``, como expressão aplicável de forma preguiçosa."""
    if task_id == "volume_condicional":
        return (
            pl.col("target_observed")
            & pl.col("true_volume_valid")
            & pl.col("true_positive")
            & (pl.col("true_volume_mwmed") > 0)
        )
    if task_id == "causa":
        return (
            pl.col("target_observed")
            & pl.col("true_restriction")
            & pl.col("true_cause").is_in(["REL", "CNF", "ENE"])
        )
    return pl.col("target_observed") & pl.col(TASKS[task_id][1]).is_not_null()


def _split(segment: pl.LazyFrame, task_id: str) -> DatasetSplit:
    target = TASKS[task_id][1]
    columns = list(dict.fromkeys([*NUMERIC_FEATURES, *CATEGORICAL_FEATURES, target]))
    # Motor padrão: a ordem das linhas é a do dataset, como no oráculo (importa ao LightGBM).
    selected = segment.filter(_task_filter(task_id)).select(columns).collect()
    if selected.is_empty():
        raise ValueError(f"segmento sem exemplos para {task_id}")
    return DatasetSplit(selected, selected[target].to_numpy())


def _training_segments(
    features: pl.LazyFrame,
    round_: ExternalRound,
    boundary: Any,
    first_t0: datetime,
    sample: pl.Expr | None,
) -> dict[str, pl.LazyFrame]:
    """Segmentos internos da rodada; a amostra, se houver, restringe initial e refit."""
    initial = _range(features, first_t0, boundary.tuning_start, label_cutoff=boundary.tuning_start)
    refit = _range(
        features, first_t0, boundary.calibration_start, label_cutoff=boundary.calibration_start
    )
    if sample is not None:
        initial, refit = initial.filter(sample), refit.filter(sample)
    return {
        "initial": initial,
        "tuning": _range(
            features,
            boundary.tuning_start,
            boundary.calibration_start,
            label_cutoff=boundary.calibration_start,
        ),
        "refit": refit,
        "calibration": _range(
            features, boundary.calibration_start, boundary.cutoff, label_cutoff=round_.start
        ),
    }


def _target_mean(target: np.ndarray) -> float | None:
    """Prevalência (ou média) do alvo numérico; ``None`` para causa categórica."""
    if target.dtype.kind in "biuf" and target.size:
        return float(np.mean(target.astype(float)))
    return None


def _validation_filter(round_: ExternalRound) -> pl.Expr:
    return (pl.col("t0") >= round_.start) & (pl.col("t0") + timedelta(hours=24) <= round_.end)


def _weekend_or_holiday(calendar: BusinessCalendar) -> pl.Expr:
    return (
        (pl.col("tau").dt.weekday() >= 6)
        | pl.col("tau").dt.date().is_in(list(calendar.non_business_days))
    ).alias("tau_weekend_or_holiday")


@dataclass(frozen=True)
class _Chunk:
    """Intervalo ``[start, end)`` de ``t0``; sem limites representa a validação inteira."""

    start: datetime | None = None
    end: datetime | None = None

    def expression(self) -> pl.Expr:
        if self.start is None or self.end is None:
            return pl.lit(True)
        return (pl.col("t0") >= self.start) & (pl.col("t0") < self.end)


def _plan_chunks(frame: pl.LazyFrame, origin: datetime, chunk_days: int) -> list[_Chunk]:
    """Partes de ``chunk_days`` dias com linhas, na ordem em que aparecem em ``frame``.

    Concatenar as partes só reproduz a ordem original se cada uma ocupar um trecho contíguo
    e crescente das linhas. Caso contrário (ou sem linhas), devolve uma parte única.
    """
    if chunk_days < 1:
        raise ValueError("chunk_days deve ser positivo")
    step = timedelta(days=chunk_days)
    width = int(step / timedelta(microseconds=1))
    index = (
        frame.select(
            ((pl.col("t0") - pl.lit(origin)).dt.total_microseconds() // width).alias("chunk")
        )
        .collect()
        .get_column("chunk")
    )
    if index.is_empty() or index.null_count() or bool((index.diff().drop_nulls() < 0).any()):
        return [_Chunk()]
    return [
        _Chunk(origin + step * value, origin + step * (value + 1))
        for value in index.unique(maintain_order=True).to_list()
    ]


def _slice_frames(frame: pl.DataFrame) -> Iterator[tuple[str, pl.DataFrame]]:
    """Recortes não vazios, na ordem do oráculo, materializados um de cada vez."""

    def candidates() -> Iterator[tuple[str, pl.DataFrame]]:
        yield "global", frame
        for start, end, name in ((1, 12, "0_6h"), (13, 24, "6_12h"), (25, 48, "12_24h")):
            yield (
                f"faixa_horizonte:{name}",
                frame.filter(pl.col("horizon").is_between(start, end)),
            )
        for horizon in range(1, 49):
            yield f"horizonte:{horizon}", frame.filter(pl.col("horizon") == horizon)
        if "eligible_history" in frame.columns:
            yield "historico_insuficiente", frame.filter(~pl.col("eligible_history"))
        if "entity_new" in frame.columns:
            yield "entidade_nova", frame.filter(pl.col("entity_new"))
        if "panel_fixed" in frame.columns:
            yield "painel_fixo", frame.filter(pl.col("panel_fixed"))
            yield "painel_aberto", frame
        if "tau_weekend_or_holiday" in frame.columns:
            yield "fim_semana_feriado", frame.filter(pl.col("tau_weekend_or_holiday"))
        for lower, upper, label in (
            (0, 48, "ate_48h"),
            (48, 96, "48_96h"),
            (96, None, "acima_96h"),
        ):
            condition = (
                pl.col("history_age_hours") <= upper
                if lower == 0
                else pl.col("history_age_hours") > lower
            )
            if upper is not None and lower:
                condition &= pl.col("history_age_hours") <= upper
            yield f"idade:{label}", frame.filter(condition)
        if "episode_start" in frame.columns:
            yield "inicio_episodio", frame.filter(pl.col("episode_start"))
            yield "primeiro_zero_pos_episodio", frame.filter(pl.col("post_episode_zero"))
        if "volume_tail" in frame.columns:
            yield "cauda_volume_p99_treino", frame.filter(pl.col("volume_tail"))
            yield "fora_cauda_volume", frame.filter(~pl.col("volume_tail"))

    for name, subset in candidates():
        if not subset.is_empty():
            yield name, subset


def _tail_threshold(refit: pl.LazyFrame) -> float | None:
    positive_training = (
        refit.filter(pl.col("true_volume_valid") & (pl.col("true_volume_mwmed") > 0))
        .select("true_volume_mwmed")
        .collect(engine="streaming")
        .get_column("true_volume_mwmed")
    )
    return (
        float(positive_training.quantile(0.99, interpolation="nearest"))
        if not positive_training.is_empty()
        else None
    )


def _post_event_truth(validation: pl.LazyFrame, tail_threshold: float | None) -> pl.DataFrame:
    """Episódios e cauda por (entidade, tau) de toda a validação, a partir de projeção única.

    A verdade de um ``tau`` é a mesma em qualquer emissão; ``unique`` apenas deduplica.
    """
    unique = (
        validation.select("fonte", "id_ons", "tau", "true_positive", "true_volume_mwmed")
        .unique(["fonte", "id_ons", "tau"])
        .collect(engine="streaming")
    )
    return (
        unique.sort("fonte", "id_ons", "tau")
        .with_columns(
            pl.col("true_positive").shift(1).over("fonte", "id_ons").alias("previous_positive"),
            pl.col("tau").shift(1).over("fonte", "id_ons").alias("previous_tau"),
        )
        .with_columns(
            (
                pl.col("true_positive")
                & pl.col("previous_positive").not_()
                & (pl.col("tau") - pl.col("previous_tau") == timedelta(minutes=30))
            )
            .fill_null(False)
            .alias("episode_start"),
            (
                pl.col("true_positive").not_()
                & pl.col("previous_positive")
                & (pl.col("tau") - pl.col("previous_tau") == timedelta(minutes=30))
            )
            .fill_null(False)
            .alias("post_episode_zero"),
            (
                pl.col("true_positive")
                & (
                    pl.col("previous_positive").fill_null(False).not_()
                    | (pl.col("tau") - pl.col("previous_tau") != timedelta(minutes=30))
                )
            )
            .fill_null(False)
            .alias("new_episode"),
            (
                (pl.col("true_volume_mwmed") > tail_threshold)
                if tail_threshold is not None
                else pl.lit(False)
            ).alias("volume_tail"),
        )
        .with_columns(
            pl.when(pl.col("true_positive"))
            .then(pl.col("new_episode").cast(pl.Int64).cum_sum().over("fonte", "id_ons"))
            .otherwise(None)
            .alias("episode_id")
        )
        .select(
            "fonte",
            "id_ons",
            "tau",
            "episode_start",
            "post_episode_zero",
            "volume_tail",
            "episode_id",
        )
    )


def _metrics_for_prediction(
    frame: pl.DataFrame, task_id: str, threshold: float | None
) -> list[dict]:
    columns = [name for name in SLICE_COLUMNS if name in frame.columns]
    frame = frame.select([*columns, METRIC_TARGET[task_id], "prediction"])
    reports = []
    for slice_id, subset in _slice_frames(frame):
        if task_id in {"corte_positivo", "restricao_registrada"}:
            target = "true_positive" if task_id == "corte_positivo" else "true_restriction"
            valid = subset.filter(pl.col(target).is_not_null())
            metrics = occurrence_metrics(
                valid[target].cast(pl.Int8).to_numpy(),
                valid["prediction"].to_numpy(),
                threshold=threshold or 0.5,
            )
        elif task_id == "causa":
            valid = subset.filter(pl.col("true_cause").is_in(["REL", "CNF", "ENE"]))
            metrics = cause_metrics(valid["true_cause"].to_numpy(), valid["prediction"].to_numpy())
        else:
            metrics = volume_metrics(
                subset["true_volume_mwmed"].to_numpy(), subset["prediction"].to_numpy()
            )
        reports.append({"slice": slice_id, "metrics": metrics})
    return reports


def _metrics_from_parquet(path: Path, task_id: str, threshold: float | None) -> list[dict]:
    """Métricas sobre a previsão completa de um modelo, relida só com as colunas usadas."""
    available = pl.read_parquet_schema(path)
    columns = [name for name in SLICE_COLUMNS if name in available]
    columns = list(dict.fromkeys([*columns, METRIC_TARGET[task_id], "prediction"]))
    return _metrics_for_prediction(pl.read_parquet(path, columns=columns), task_id, threshold)


def _predict(trained: Any, task_id: str, frame: pl.DataFrame) -> np.ndarray:
    if task_id in OCCURRENCE_TASKS:
        raw = trained.model.predict_proba(frame)
        return trained.calibrator.predict(raw) if trained.calibrator else raw
    return trained.model.predict(frame)


def _with_prediction(
    part: pl.DataFrame, prediction: np.ndarray, fallback: pl.DataFrame, task_id: str
) -> pl.DataFrame:
    predicted = part.with_columns(pl.Series("model_prediction", prediction)).join(
        fallback, on=KEYS, how="left", maintain_order="left"
    )
    fallback_expression = pl.col(FALLBACK_COLUMN[task_id])
    if task_id == "volume_condicional":
        fallback_expression = fallback_expression.fill_null(0.0)
    return predicted.with_columns(
        pl.when(pl.col("eligible_history"))
        .then(pl.col("model_prediction"))
        .otherwise(fallback_expression)
        .alias("prediction")
    )


def _write_prediction(
    stream: ParquetStream,
    part: pl.DataFrame,
    fallback: pl.DataFrame,
    trained: Any,
    task_id: str,
    output_columns: list[str] | None,
) -> None:
    """Prevê uma parte com um modelo; a previsão sai de memória ao retornar."""
    predicted = _with_prediction(part, _predict(trained, task_id, part), fallback, task_id)
    stream.write(predicted.select(output_columns) if output_columns else predicted)


@dataclass
class _Validation:
    """Leitura por partes da validação, com colunas derivadas e diagnósticos pós-evento."""

    features: pl.LazyFrame
    baselines: pl.LazyFrame
    round_: ExternalRound
    columns: list[str] | None
    derived: list[pl.Expr]
    truth: pl.DataFrame | None
    fallback_columns: list[str]

    def part(self, chunk: _Chunk) -> pl.DataFrame:
        selected = self.features.filter(_validation_filter(self.round_) & chunk.expression())
        if self.columns is not None:
            selected = selected.select(self.columns)
        frame = selected.collect().with_columns(self.derived)
        if self.truth is not None:
            frame = frame.join(
                self.truth, on=["fonte", "id_ons", "tau"], how="left", maintain_order="left"
            )
        return frame

    def fallback(self, chunk: _Chunk) -> pl.DataFrame:
        return (
            self.baselines.filter(
                (pl.col("baseline_id") == "historico")
                & _validation_filter(self.round_)
                & chunk.expression()
            )
            .select(KEYS + self.fallback_columns)
            .collect()
        )


def _stream_predictions(
    validation: _Validation,
    chunks: list[_Chunk],
    models: dict[str, tuple[str, Any]],
    streams: dict[str, ParquetStream],
    scratch: ParquetStream,
    *,
    scratch_columns: list[str],
    output_columns: list[str] | None,
    errors: dict[str, BaseException],
) -> int:
    """Percorre a validação uma vez; cada parte alimenta todos os modelos ainda ativos.

    Uma falha de previsão descarta só aquele modelo (como no oráculo, sem artefatos).
    Devolve o número de linhas da validação.
    """
    rows = 0
    active = dict(models)
    with ExitStack() as cleanup:
        for stream in [*streams.values(), scratch]:
            cleanup.callback(stream.abort)
        for chunk in chunks:
            part = validation.part(chunk)
            fallback = validation.fallback(chunk)
            rows += part.height
            scratch.write(part.select(scratch_columns))
            for identity, (task_id, trained) in list(active.items()):
                try:
                    _write_prediction(
                        streams[identity], part, fallback, trained, task_id, output_columns
                    )
                except Exception as error:
                    streams[identity].abort()
                    errors[identity] = error
                    del active[identity]
            del part, fallback
        scratch.close()
        for identity in active:
            streams[identity].close()
    return rows


def _write_pipelines(
    store: RunStore,
    *,
    identity_prefix: str,
    available: dict[tuple[str, str], Path],
    chunks: list[_Chunk],
    scratch_path: Path,
    validation_columns: list[str],
    diagnostics: bool,
) -> None:
    """Produto ocorrência × volume por parte, relendo as previsões gravadas (1:1 por chave).

    Os três lados estão na ordem da validação; a junção mantém essa ordem.
    """
    for occurrence_family in FAMILIES:
        occurrence_path = available.get(("corte_positivo", occurrence_family))
        if occurrence_path is None:
            continue
        for volume_family in FAMILIES:
            volume_path = available.get(("volume_condicional", volume_family))
            if volume_path is None:
                continue
            identity = f"{identity_prefix}-volume-{occurrence_family}-{volume_family}"
            relative = f"predictions/{identity}.parquet"
            with store.open_parquet_stream(relative) as stream:
                for chunk in chunks:
                    occurrence = (
                        pl.scan_parquet(occurrence_path)
                        .filter(chunk.expression())
                        .select(KEYS + [pl.col("prediction").alias("probability")])
                        .collect()
                    )
                    volume = (
                        pl.scan_parquet(volume_path)
                        .filter(chunk.expression())
                        .select(KEYS + [pl.col("prediction").alias("conditional_volume")])
                        .collect()
                    )
                    truth = (
                        pl.scan_parquet(scratch_path)
                        .filter(chunk.expression())
                        .select(validation_columns)
                        .collect()
                    )
                    pipeline = occurrence.join(volume, on=KEYS, maintain_order="right").join(
                        truth, on=KEYS, maintain_order="right"
                    )
                    del occurrence, volume, truth
                    pipeline = pipeline.with_columns(
                        pl.Series(
                            "prediction",
                            expected_volume(
                                pipeline["probability"].to_numpy(),
                                pipeline["conditional_volume"].to_numpy(),
                            ),
                        )
                    )
                    stream.write(pipeline)
                    del pipeline
            path = store.path / relative
            store.write_json(
                f"metrics/{identity}.json",
                _metrics_from_parquet(path, "volume_pipeline", None),
            )
            if not diagnostics:
                continue
            errors = (
                pl.read_parquet(
                    path,
                    columns=["fonte", "id_ons", "episode_id", "true_volume_mwmed", "prediction"],
                )
                .rechunk()
                .with_columns(
                    (pl.col("true_volume_mwmed") - pl.col("prediction"))
                    .abs()
                    .alias("absolute_error")
                )
            )
            # ``maintain_order`` torna a soma por grupo determinística (na ordem das linhas).
            # No oráculo, sem ele, a soma paralela varia no último bit entre execuções.
            top_entities = (
                errors.group_by("fonte", "id_ons", maintain_order=True)
                .agg(pl.col("absolute_error").sum().alias("absolute_error"))
                .sort("absolute_error", descending=True, maintain_order=True)
                .head(10)
                .to_dicts()
            )
            top_episodes = (
                errors.filter(pl.col("episode_id").is_not_null())
                .group_by("fonte", "id_ons", "episode_id", maintain_order=True)
                .agg(pl.col("absolute_error").sum().alias("absolute_error"))
                .sort("absolute_error", descending=True, maintain_order=True)
                .head(10)
                .to_dicts()
            )
            del errors
            store.write_json(
                f"diagnostics/{identity}.json",
                {"top_error_entities": top_entities, "top_error_episodes": top_episodes},
            )


def _baseline_subset(
    window: pl.LazyFrame,
    scratch_path: Path,
    chunks: list[_Chunk],
    *,
    order: str,
    baseline_schema: pl.Schema,
) -> pl.DataFrame:
    """Junção baseline × validação de um comparador, por partes, só com colunas das métricas.

    Reproduz a junção interna do oráculo: colunas homônimas vêm do baseline (lado esquerdo),
    como ``history_age_hours``, cuja versão das features ficaria com sufixo e não é usada.
    """
    needed = [
        *SLICE_COLUMNS,
        *(column for _, column in BASELINE_TASKS),
        "true_positive",
        "true_restriction",
        "true_volume_mwmed",
        "true_cause",
    ]
    left = [name for name in dict.fromkeys(needed) if name in baseline_schema and name not in KEYS]
    right = [
        name
        for name in CAMPAIGN_VALIDATION_COLUMNS
        if name in needed and name not in KEYS and name not in left
    ]
    parts = []
    for chunk in chunks:
        baseline = window.filter(chunk.expression()).select(KEYS + left).collect()
        truth = (
            pl.scan_parquet(scratch_path).filter(chunk.expression()).select(KEYS + right).collect()
        )
        joined = baseline.join(truth, on=KEYS, maintain_order=order)
        parts.append(joined.drop("fonte", "id_ons", "t0", "tau"))
        del baseline, truth, joined
    return pl.concat(parts)


def _baseline_metrics(
    baselines: pl.LazyFrame,
    store: RunStore,
    reports: dict[str, Any],
    *,
    source: str,
    round_: ExternalRound,
    scratch_path: Path,
    validation_chunks: list[_Chunk],
    validation_rows: int,
    chunk_days: int,
) -> None:
    window = baselines.filter(_validation_filter(round_))
    # O oráculo junta todos os comparadores à validação de uma vez; o Polars preserva a ordem
    # do lado maior (baselines, ~4x), e do direito em empate. A escolha é reproduzida aqui.
    window_rows = window.select(pl.len()).collect(engine="streaming").item()
    order = "left" if window_rows > validation_rows else "right"
    identifiers = (
        window.select(pl.col("baseline_id").unique())
        .collect(engine="streaming")
        .get_column("baseline_id")
        .sort()
        .to_list()
    )
    schema = baselines.collect_schema()
    reports["baselines"] = {}
    rows = 0
    for baseline_id in identifiers:
        selected = window.filter(pl.col("baseline_id") == baseline_id)
        chunks = (
            _plan_chunks(selected, round_.start, chunk_days)
            if order == "left"
            else validation_chunks
        )
        subset = _baseline_subset(
            selected, scratch_path, chunks, order=order, baseline_schema=schema
        )
        if subset.is_empty():
            continue
        rows += subset.height
        for task_id, column in BASELINE_TASKS:
            predicted = subset.with_columns(pl.col(column).alias("prediction"))
            identity = f"baseline-{baseline_id}-{task_id}"
            metrics = _metrics_for_prediction(predicted, task_id, 0.5)
            reports["baselines"][identity] = metrics
            store.write_json(f"metrics/{source}-{round_.round_id}-{identity}.json", metrics)
            del predicted
        del subset
    reports["baseline_rows"] = rows


def _execution(chunk_days: int, chunks: list[_Chunk], rows: int) -> dict[str, Any]:
    return {
        "mode": "validacao_por_partes_de_t0",
        "validation_chunk_days": chunk_days,
        "validation_chunks": len(chunks),
        "validation_rows": rows,
        "peak_rss_bytes": peak_rss_bytes(),
    }


def run_campaign_round(
    features: pl.LazyFrame | pl.DataFrame,
    baselines: pl.LazyFrame | pl.DataFrame,
    store: RunStore,
    *,
    source: str,
    round_: ExternalRound,
    calendar: BusinessCalendar,
    seed: int,
    chunk_days: int = DEFAULT_CHUNK_DAYS,
    scratch_dir: Path | None = None,
    training_slots: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Ajusta, calibra e valida as oito famílias da rodada, gravando todos os artefatos.

    ``training_slots`` aplica a contingência de ``sampling`` (meias-horas por dia, por
    tarefa) somente a initial e refit; ``None`` usa todos os exemplos elegíveis.

    ``chunk_days`` controla o tamanho das partes de validação em memória; ``scratch_dir``
    recebe o Parquet temporário da validação (padrão: diretório temporário do sistema).
    """
    if round_.reserved:
        raise ValueError("teste reservado não pode ser executado pela campanha V1–V4")
    features, baselines = features.lazy(), baselines.lazy()
    boundary = internal_boundaries(round_, AvailabilityScenario.main(), calendar)
    first_t0 = features.select(pl.col("t0").min()).collect(engine="streaming").item()
    known_ids = (
        features.filter(pl.col("t0") < boundary.tuning_start)
        .select(pl.col("id_ons").unique())
        .collect(engine="streaming")
        .get_column("id_ons")
    )
    fixed_ids = (
        features.filter((pl.col("t0") == datetime(2025, 1, 1)) & pl.col("eligible_history"))
        .select(pl.col("id_ons").unique())
        .collect(engine="streaming")
        .get_column("id_ons")
    )
    derived = [
        (~pl.col("id_ons").is_in(known_ids)).alias("entity_new"),
        _weekend_or_holiday(calendar),
        pl.col("id_ons").is_in(fixed_ids).alias("panel_fixed"),
    ]
    segments = _training_segments(features, round_, boundary, first_t0, None)
    tail_threshold = _tail_threshold(segments["refit"])
    validation_frame = features.filter(_validation_filter(round_))
    truth = _post_event_truth(validation_frame, tail_threshold)
    chunks = _plan_chunks(validation_frame, round_.start, chunk_days)
    reports: dict[str, Any] = {
        "source": source,
        "round": round_.round_id,
        "boundaries": asdict(boundary),
        "models": {},
        "failures": [],
        "volume_tail_p99_training": tail_threshold,
        "training_sampling": None
        if training_slots is None
        else {
            "method": METHOD,
            "seed": seed,
            "slots_per_day": dict(training_slots),
            "segments": ["initial", "refit"],
            "complete_segments": ["tuning", "calibration", "validation"],
        },
        "training_rows": {},
    }

    identities = {
        (task_id, family): f"{source}-{round_.round_id}-{task_id}-{family}"
        for task_id in TASK_IDS
        for family in FAMILIES
    }
    errors: dict[str, BaseException] = {}
    trained_models: dict[str, tuple[str, Any]] = {}
    for task_id in TASK_IDS:
        try:
            sample = (
                emission_mask(training_slots[task_id], seed) if training_slots is not None else None
            )
            task_segments = _training_segments(features, round_, boundary, first_t0, sample)
            splits = {
                "initial": _split(task_segments["initial"], task_id),
                "tuning": _split(task_segments["tuning"], task_id),
                "refit": _split(task_segments["refit"], task_id),
                "calibration": _split(task_segments["calibration"], task_id)
                if task_id in OCCURRENCE_TASKS
                else None,
            }
            reports["training_rows"][task_id] = {
                name: {
                    "rows": split.features.height,
                    "target_mean": _target_mean(split.target),
                }
                for name, split in splits.items()
                if split is not None
            }
        except Exception as error:
            for family in FAMILIES:
                errors[identities[(task_id, family)]] = error
            continue
        for family in FAMILIES:
            identity = identities[(task_id, family)]
            try:
                trained_models[identity] = (
                    task_id,
                    train_family(
                        task=TASK_KIND[task_id],
                        family=family,
                        **splits,
                        numeric=NUMERIC_FEATURES,
                        categorical=CATEGORICAL_FEATURES,
                        seed=seed,
                    ),
                )
            except Exception as error:
                errors[identity] = error
        del splits

    validation = _Validation(
        features=features,
        baselines=baselines,
        round_=round_,
        columns=MODEL_INPUT_COLUMNS,
        derived=derived,
        truth=truth,
        fallback_columns=[
            "prob_positive",
            "prob_restriction",
            "volume_positive_mean",
            "volume_expected",
            "cause_prediction",
        ],
    )
    with tempfile.TemporaryDirectory(
        dir=scratch_dir, prefix="curtamap-validacao-", ignore_cleanup_errors=True
    ) as temporary:
        scratch_path = Path(temporary) / "validation.parquet"
        streams = {
            identity: store.open_parquet_stream(f"predictions/{identity}.parquet")
            for identity in trained_models
        }
        validation_rows = _stream_predictions(
            validation,
            chunks,
            trained_models,
            streams,
            ParquetStream(scratch_path),
            scratch_columns=CAMPAIGN_VALIDATION_COLUMNS,
            output_columns=CAMPAIGN_PREDICTION_COLUMNS,
            errors=errors,
        )
        del truth, validation

        available: dict[tuple[str, str], Path] = {}
        for (task_id, family), identity in identities.items():
            if identity in errors:
                continue
            trained = trained_models[identity][1]
            try:
                available[(task_id, family)] = streams[identity].target
                store.write_model(f"models/{identity}.joblib", trained)
                task_metrics = _metrics_from_parquet(
                    streams[identity].target, task_id, trained.threshold
                )
                store.write_json(f"metrics/{identity}.json", task_metrics)
                reports["models"][identity] = {
                    "selected_params": trained.selected_params,
                    "internal_scores": trained.internal_scores,
                    "fit_seconds": trained.fit_seconds,
                    "calibration_status": trained.calibration_status,
                    "threshold": trained.threshold,
                }
            except Exception as error:
                errors[identity] = error
        for identity in identities.values():
            if identity in errors:
                reports["failures"].append(identity)
                store.record_failure(f"campaign/{identity}.json", errors[identity], resumable=True)

        _write_pipelines(
            store,
            identity_prefix=f"{source}-{round_.round_id}",
            available=available,
            chunks=chunks,
            scratch_path=scratch_path,
            validation_columns=CAMPAIGN_PIPELINE_COLUMNS,
            diagnostics=True,
        )
        _baseline_metrics(
            baselines,
            store,
            reports,
            source=source,
            round_=round_,
            scratch_path=scratch_path,
            validation_chunks=chunks,
            validation_rows=validation_rows,
            chunk_days=chunk_days,
        )
    reports["execution"] = _execution(chunk_days, chunks, validation_rows)
    store.write_json(f"reports/{source}-{round_.round_id}.json", reports)
    return reports


def run_sensitivity_round(
    features: pl.LazyFrame | pl.DataFrame,
    baselines: pl.LazyFrame | pl.DataFrame,
    store: RunStore,
    *,
    frozen_run: Path,
    source: str,
    round_: ExternalRound,
    calendar: BusinessCalendar,
    chunk_days: int = DEFAULT_CHUNK_DAYS,
    scratch_dir: Path | None = None,
) -> dict[str, Any]:
    """Aplica, sem reajuste, modelos/calibradores/limiares do cenário principal no +24h."""
    features, baselines = features.lazy(), baselines.lazy()
    validation_frame = features.filter(_validation_filter(round_))
    chunks = _plan_chunks(validation_frame, round_.start, chunk_days)
    reports: dict[str, Any] = {
        "source": source,
        "round": round_.round_id,
        "scenario": "noturno_mais_24h",
        "frozen_run": str(frozen_run),
        "models_retrained": False,
        "models": {},
        "failures": [],
    }
    identities = {
        (task_id, family): f"{source}-{round_.round_id}-{task_id}-{family}"
        for task_id in TASK_IDS
        for family in FAMILIES
    }
    errors: dict[str, BaseException] = {}
    loaded: dict[str, tuple[str, Any]] = {}
    for (task_id, _family), identity in identities.items():
        try:
            loaded[identity] = (
                task_id,
                joblib.load(frozen_run / "models" / f"{identity}.joblib"),
            )
        except Exception as error:
            errors[identity] = error

    validation = _Validation(
        features=features,
        baselines=baselines,
        round_=round_,
        columns=None,  # a previsão da sensibilidade grava todas as colunas da validação
        derived=[
            pl.lit(False).alias("entity_new"),
            pl.lit(False).alias("panel_fixed"),
            _weekend_or_holiday(calendar),
        ],
        truth=None,
        fallback_columns=[
            "prob_positive",
            "prob_restriction",
            "volume_positive_mean",
            "cause_prediction",
        ],
    )
    with tempfile.TemporaryDirectory(
        dir=scratch_dir, prefix="curtamap-validacao-", ignore_cleanup_errors=True
    ) as temporary:
        scratch_path = Path(temporary) / "validation.parquet"
        streams = {
            identity: store.open_parquet_stream(f"predictions/sensitivity-{identity}.parquet")
            for identity in loaded
        }
        validation_rows = _stream_predictions(
            validation,
            chunks,
            loaded,
            streams,
            ParquetStream(scratch_path),
            scratch_columns=SENSITIVITY_PIPELINE_COLUMNS,
            output_columns=None,
            errors=errors,
        )
        del validation

        available: dict[tuple[str, str], Path] = {}
        # No oráculo as métricas vêm antes do Parquet: se falharem, a previsão não é gravada,
        # mas ainda alimenta as combinações de volume. Ela é descartada depois delas.
        discard: list[Path] = []
        for (task_id, family), identity in identities.items():
            if identity in errors:
                continue
            trained = loaded[identity][1]
            path = streams[identity].target
            available[(task_id, family)] = path
            try:
                metrics = _metrics_from_parquet(path, task_id, trained.threshold)
                store.write_json(f"metrics/sensitivity-{identity}.json", metrics)
                reports["models"][identity] = {
                    "frozen_model": str(frozen_run / "models" / f"{identity}.joblib"),
                    "threshold": trained.threshold,
                    "calibration_status": trained.calibration_status,
                }
            except Exception as error:
                errors[identity] = error
                discard.append(path)
        for identity in identities.values():
            if identity in errors:
                reports["failures"].append(identity)
                store.record_failure(
                    f"sensitivity/{identity}.json", errors[identity], resumable=True
                )

        _write_pipelines(
            store,
            identity_prefix=f"sensitivity-{source}-{round_.round_id}",
            available=available,
            chunks=chunks,
            scratch_path=scratch_path,
            validation_columns=SENSITIVITY_PIPELINE_COLUMNS,
            diagnostics=False,
        )
        for path in discard:
            path.unlink(missing_ok=True)
    reports["execution"] = _execution(chunk_days, chunks, validation_rows)
    store.write_json(f"reports/sensitivity-{source}-{round_.round_id}.json", reports)
    return reports
