"""Proveniência de uma previsão, no formato que a tela de metodologia e o selo exibem.

Lê só colunas do contrato. As colunas extras `emitido_em`, `idade_informacao_dias`,
`tipo_saida_volume` e `tipo_saida_causa`, publicadas pelo modelo diário, são usadas quando
existem, para mostrar a proveniência por componente.
"""

from dataclasses import dataclass, field
from datetime import datetime

import polars as pl

_COMPONENTS = {"volume": "tipo_saida_volume", "causa": "tipo_saida_causa"}
_DAY_US = 86_400_000_000


@dataclass(frozen=True)
class Provenance:
    output_kinds: tuple[str, ...]
    model_ids: tuple[str, ...]
    scenarios: tuple[str, ...]
    t0: datetime
    data_cutoff: datetime
    generated_at: datetime
    emitted_at: datetime | None
    entities: int
    windows: int
    windows_without_forecast: int
    windows_without_cause: int
    oldest_evidence: datetime | None
    newest_evidence: datetime | None
    evidence_age_days: tuple[float, float] | None
    coverage_min: float
    coverage_median: float
    interval_share: float
    components: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def is_baseline(self) -> bool:
        return "baseline" in self.output_kinds


def _unique(frame: pl.DataFrame, column: str) -> tuple:
    return tuple(sorted(frame[column].drop_nulls().unique().to_list()))


def _age_days(frame: pl.DataFrame) -> tuple[float, float] | None:
    if frame["instante_observacao"].null_count() < frame.height:
        age = (pl.col("t0") - pl.col("instante_observacao")).dt.total_microseconds() / _DAY_US
    elif "idade_informacao_dias" in frame.columns:
        age = pl.col("idade_informacao_dias").cast(pl.Float64)
    else:
        return None
    low, high = frame.select(low=age.min(), high=age.max()).row(0)
    return None if low is None else (float(low), float(high))


def summarize_provenance(forecast: pl.DataFrame) -> Provenance:
    if forecast.is_empty():
        raise ValueError("previsão vazia: não há proveniência a mostrar")
    no_forecast = pl.col("p_corte").is_null() | pl.col("volume_esperado_mwmed").is_null()
    stats = forecast.select(
        t0=pl.col("t0").max(),
        corte=pl.col("corte_dados").max(),
        gerado=pl.col("gerado_em").max(),
        entidades=pl.struct("fonte", "id_ons").n_unique(),
        sem_previsao=no_forecast.sum(),
        sem_causa=pl.col("causa_prevista").is_null().sum(),
        obs_min=pl.col("instante_observacao").min(),
        obs_max=pl.col("instante_observacao").max(),
        cob_min=pl.col("cobertura_historico").min(),
        cob_med=pl.col("cobertura_historico").median(),
        intervalo=pl.col("volume_p10_mwmed").is_not_null().mean(),
    ).row(0)
    components = {
        name: dict(forecast[column].drop_nulls().value_counts().sort(column).iter_rows())
        for name, column in _COMPONENTS.items()
        if column in forecast.columns
    }
    emitted = forecast["emitido_em"].max() if "emitido_em" in forecast.columns else None
    return Provenance(
        output_kinds=_unique(forecast, "tipo_saida"),
        model_ids=_unique(forecast, "modelo_id"),
        scenarios=_unique(forecast, "cenario_disponibilidade"),
        t0=stats[0],
        data_cutoff=stats[1],
        generated_at=stats[2],
        emitted_at=emitted,
        entities=stats[3],
        windows=forecast.height,
        windows_without_forecast=stats[4],
        windows_without_cause=stats[5],
        oldest_evidence=stats[6],
        newest_evidence=stats[7],
        evidence_age_days=_age_days(forecast),
        coverage_min=stats[8],
        coverage_median=stats[9],
        interval_share=stats[10],
        components=components,
    )
