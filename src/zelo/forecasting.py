"""Preditor provisório do produto: mesmo horário mais recente disponível.

Regra do §7.2 do protocolo experimental da Etapa 2A (`docs/experimental-protocol.md`, na
branch `etapa-2-experimental`).

Serve para que recomendação, dashboard e deploy trabalhem com números reais antes da
decisão da Etapa 2C. Ele é marcado como `baseline` no contrato e será substituído pelo
preditor escolhido sem mudar o formato de saída.

Diferenças conscientes em relação ao baseline experimental da Etapa 2:

- a disponibilidade usa `nightly_cutoff`, que delega ao calendário de feriados de
  `zelo.previsao.calendario` (fonte única do corte para todo o produto);
- não há fallback estatístico regional: sem observação válida no horário, a previsão
  fica nula com motivo explícito, em vez de um número de baixa evidência.

`instante_observacao` é o instante da observação de volume usada; comando e causa podem
vir de dias diferentes do mesmo horário, sempre dentro da janela de 28 dias.
"""

from datetime import datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Protocol

import polars as pl

from zelo.contracts import (
    FORECAST_SCHEMA,
    HORIZONS,
    PREDICTABLE_CAUSES,
    RESERVED_TEST_START,
    SOURCES,
    STEP,
    validate_forecast,
)
from zelo.data_contract import SPECS
from zelo.previsao.calendario import Calendar, load_calendar, release_cutoff
from zelo.targets import derive_targets

HISTORY_DAYS = 28
AVAILABILITY_SCENARIO = "noturno_fim_de_semana"
ENTITY_ATTRIBUTES = ("nom_usina", "id_estado", "id_subsistema")
_RAW_COLUMNS = (
    "fonte",
    "id_ons",
    *ENTITY_ATTRIBUTES,
    "din_instante",
    "val_geracaolimitada",
    "val_geracaoreferencia",
    "val_geracao",
    "cod_razaorestricao",
    "cod_origemrestricao",
)
_KEY = ["fonte", "id_ons"]
_SLOT_KEY = [*_KEY, "slot"]


class Predictor(Protocol):
    """Interface de qualquer preditor do produto; a saída obedece `FORECAST_SCHEMA`."""

    model_id: str

    def predict(
        self, history: pl.DataFrame, t0: datetime, data_cutoff: datetime
    ) -> pl.DataFrame: ...


@cache
def _calendar() -> Calendar:
    return load_calendar()


def nightly_cutoff(t0: datetime) -> datetime:
    """Fim do último dia civil liberado até `t0` (lote às 19h30 do dia útil seguinte)."""
    return release_cutoff(t0, _calendar())


def _guard_reserved(end: datetime, allow_reserved_test: bool) -> None:
    if end > RESERVED_TEST_START and not allow_reserved_test:
        raise ValueError(
            f"período a partir de {RESERVED_TEST_START:%d/%m/%Y} é o teste reservado; "
            "só a validação final congelada pode lê-lo"
        )


def load_history(
    data_dir: Path,
    start: datetime,
    end: datetime,
    *,
    sources: tuple[str, ...] = SOURCES,
    allow_reserved_test: bool = False,
) -> pl.DataFrame:
    """Lê `[start, end)` das bases principais em `data_dir/raw` e deriva os alvos."""
    _guard_reserved(end, allow_reserved_test)
    frames = [
        pl.scan_parquet(Path(data_dir) / "raw" / SPECS[source].filename)
        .select(_RAW_COLUMNS)
        .with_columns(pl.col("din_instante").cast(pl.Datetime("us")))
        .filter(pl.col("din_instante").is_between(start, end, closed="left"))
        .collect()
        for source in sources
    ]
    return derive_targets(pl.concat(frames, how="vertical"))


def _available(history: pl.DataFrame, cutoff: datetime) -> pl.DataFrame:
    return history.filter(pl.col("din_instante") + STEP <= cutoff)


def known_entities(history: pl.DataFrame, data_cutoff: datetime) -> pl.DataFrame:
    """Entidades vistas até o corte, com os atributos mais recentes conhecidos então."""
    return (
        _available(history, data_cutoff)
        .sort("din_instante")
        .group_by(_KEY)
        .agg(pl.col(list(ENTITY_ATTRIBUTES)).last(), pl.col("din_instante").max().alias("visto_em"))
        .sort(_KEY)
    )


def _slot(column: str) -> pl.Expr:
    moment = pl.col(column)
    return (moment.dt.hour().cast(pl.Int16) * 2 + moment.dt.minute().cast(pl.Int16) // 30).alias(
        "slot"
    )


def _latest(frame: pl.DataFrame, condition: pl.Expr, columns: list[str]) -> pl.DataFrame:
    return (
        frame.filter(condition).sort("din_instante").group_by(_SLOT_KEY).agg(pl.col(columns).last())
    )


class SameSlotRecentBaseline:
    """Valor do mesmo horário no dia disponível mais recente, até 28 dias antes do corte."""

    model_id = "baseline_mesmo_horario_recente_v1"
    threshold = 0.5

    def predict(
        self,
        history: pl.DataFrame,
        t0: datetime,
        data_cutoff: datetime,
        *,
        generated_at: datetime | None = None,
        allow_reserved_test: bool = False,
    ) -> pl.DataFrame:
        if t0.minute % 30 or t0.second or t0.microsecond:
            raise ValueError("t0 precisa estar na grade de 30 minutos")
        if data_cutoff > t0:
            raise ValueError("corte de dados posterior a t0 vaza informação futura")
        _guard_reserved(t0 + HORIZONS * STEP, allow_reserved_test)

        recent = (
            _available(history, data_cutoff)
            .filter(pl.col("din_instante") >= data_cutoff - timedelta(days=HISTORY_DAYS))
            .with_columns(_slot("din_instante"))
        )
        command = _latest(
            recent, pl.col("restricao_registrada").is_not_null(), ["restricao_registrada"]
        )
        volume = _latest(
            recent,
            pl.col("volume_valido") & pl.col("volume_mwmed").is_not_null(),
            ["corte_positivo", "volume_mwmed", "din_instante"],
        ).rename({"din_instante": "instante_observacao"})
        cause = _latest(recent, pl.col("causa").is_in(PREDICTABLE_CAUSES), ["causa"])
        coverage = recent.group_by(_KEY).agg(
            (pl.col("din_instante").n_unique() / (HISTORY_DAYS * 48)).alias("cobertura_historico")
        )

        horizons = pl.DataFrame({"horizonte": pl.int_range(1, HORIZONS + 1, eager=True)})
        grid = (
            known_entities(history, data_cutoff)
            .select(_KEY)
            .join(horizons, how="cross")
            .with_columns(
                pl.lit(t0).cast(pl.Datetime("us")).alias("t0"),
                pl.lit(t0).cast(pl.Datetime("us")).alias("tau")
                + pl.duration(minutes=30 * (pl.col("horizonte").cast(pl.Int64) - 1)),
            )
            .with_columns(_slot("tau"))
            .join(command, on=_SLOT_KEY, how="left")
            .join(volume, on=_SLOT_KEY, how="left")
            .join(cause, on=_SLOT_KEY, how="left")
            .join(coverage, on=_KEY, how="left")
        )

        p_corte = pl.col("corte_positivo").cast(pl.Float64)
        volume_mwmed = pl.col("volume_mwmed")
        known_cause = pl.col("causa").is_not_null()
        forecast = grid.select(
            pl.col("fonte"),
            pl.col("id_ons"),
            pl.col("t0"),
            pl.col("horizonte").cast(pl.Int16),
            pl.col("tau"),
            pl.col("restricao_registrada").cast(pl.Float64).alias("p_restricao"),
            p_corte.alias("p_corte"),
            pl.lit(self.threshold).alias("limiar_alerta"),
            (p_corte >= self.threshold).alias("alerta"),
            pl.when(volume_mwmed > 0).then(volume_mwmed).alias("volume_condicional_mwmed"),
            volume_mwmed.alias("volume_esperado_mwmed"),
            (volume_mwmed * 0.5).alias("energia_esperada_mwh"),
            pl.lit(None, pl.Float64).alias("volume_p10_mwmed"),
            pl.lit(None, pl.Float64).alias("volume_p90_mwmed"),
            pl.col("causa").alias("causa_prevista"),
            *(
                pl.when(known_cause)
                .then((pl.col("causa") == code).cast(pl.Float64))
                .alias(f"p_causa_{code.lower()}")
                for code in ("REL", "CNF", "ENE")
            ),
            pl.lit(None, pl.String).alias("origem_prevista"),
            pl.when(p_corte.is_null())
            .then(pl.lit("sem_observacao_valida_no_horario_28d"))
            .alias("motivo_sem_previsao"),
            pl.when(~known_cause)
            .then(pl.lit("sem_ordem_reconhecida_no_horario_28d"))
            .alias("motivo_sem_causa"),
            pl.lit("baseline").alias("tipo_saida"),
            pl.lit(self.model_id).alias("modelo_id"),
            pl.lit(data_cutoff).cast(pl.Datetime("us")).alias("corte_dados"),
            pl.lit(AVAILABILITY_SCENARIO).alias("cenario_disponibilidade"),
            pl.col("instante_observacao"),
            pl.col("cobertura_historico").fill_null(0.0),
            pl.lit(generated_at or datetime.now()).cast(pl.Datetime("us")).alias("gerado_em"),
        )
        return validate_forecast(forecast.cast(dict(FORECAST_SCHEMA)).sort([*_KEY, "horizonte"]))
