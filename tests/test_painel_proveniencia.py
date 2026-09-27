from datetime import datetime, timedelta

import polars as pl
import pytest
from painel_dados import T0, entity_forecast

from curtamap.painel.proveniencia import summarize_provenance


def test_baseline_provenance() -> None:
    forecast = pl.concat(
        [
            entity_forecast("eolica", "A", alerts={1: (2.0, "ENE")}, missing={48}),
            entity_forecast("fotovoltaica", "A", missing=set(range(1, 49))),
        ]
    ).with_columns(
        pl.when(pl.col("p_corte").is_not_null())
        .then(pl.col("corte_dados") - timedelta(days=1))
        .alias("instante_observacao")
    )

    prov = summarize_provenance(forecast)

    assert prov.is_baseline
    assert prov.output_kinds == ("baseline",)
    assert prov.model_ids == ("baseline_teste",)
    assert prov.t0 == T0
    assert prov.data_cutoff == T0 - timedelta(days=2)
    assert prov.scenarios == ("noturno_teste",)
    assert prov.generated_at == T0
    assert prov.emitted_at is None
    assert prov.entities == 2
    assert prov.windows == 96
    assert prov.windows_without_forecast == 49
    assert prov.oldest_evidence == T0 - timedelta(days=3)
    assert prov.newest_evidence == T0 - timedelta(days=3)
    assert prov.evidence_age_days == (3.0, 3.0)
    assert prov.coverage_min == pytest.approx(0.9)
    assert prov.interval_share == 0.0
    assert prov.components == {}


def test_model_provenance_reports_components_and_information_age() -> None:
    forecast = entity_forecast(
        "fotovoltaica",
        "A",
        kind="modelo",
        extra={
            "emitido_em": datetime(2026, 8, 19, 20),
            "idade_informacao_dias": 2,
            "tipo_saida_volume": "modelo",
            "tipo_saida_causa": "baseline_usina_28d",
        },
    ).with_columns(
        pl.lit(1.0).alias("volume_p10_mwmed"),
        pl.lit(3.0).alias("volume_p90_mwmed"),
        pl.col("idade_informacao_dias").cast(pl.Int16),
        pl.col("emitido_em").cast(pl.Datetime("us")),
    )

    prov = summarize_provenance(forecast)

    assert not prov.is_baseline
    assert prov.emitted_at == datetime(2026, 8, 19, 20)
    assert prov.oldest_evidence is None
    assert prov.evidence_age_days == (2.0, 2.0)
    assert prov.interval_share == 1.0
    assert prov.components == {
        "volume": {"modelo": 48},
        "causa": {"baseline_usina_28d": 48},
    }


def test_mixed_output_kinds_still_flag_the_baseline() -> None:
    forecast = pl.concat(
        [entity_forecast("eolica", "A"), entity_forecast("eolica", "B", kind="modelo")]
    )

    prov = summarize_provenance(forecast)

    assert prov.is_baseline
    assert prov.output_kinds == ("baseline", "modelo")


def test_empty_forecast_is_an_error() -> None:
    with pytest.raises(ValueError, match="vazia"):
        summarize_provenance(entity_forecast("eolica", "A").clear())
