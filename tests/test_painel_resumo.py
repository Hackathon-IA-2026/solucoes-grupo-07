import polars as pl
import pytest
from painel_dados import T0, entities, entity_forecast

from curtamap.contracts import STEP
from curtamap.painel.proveniencia import summarize_provenance
from curtamap.painel.ranking import rank_entities
from curtamap.painel.resumo import operational_summary, ranking_totals

ATTRS = entities(
    ("eolica", "A", "Usina A", "RN", "NE"),
    ("eolica", "B", "Usina B", "BA", "NE"),
    ("fotovoltaica", "A", "Solar A", "MG", "SE"),
)


def _ranking(*forecasts: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    forecast = pl.concat(forecasts)
    return rank_entities(forecast, ATTRS), forecast


def test_totals_count_unknown_energy_apart() -> None:
    ranking, _ = _ranking(
        entity_forecast("eolica", "A", alerts={3: (10.0, "ENE")}),
        entity_forecast("eolica", "B", alerts={1: (None, "REL")}),
        entity_forecast("fotovoltaica", "A", missing=set(range(1, 49))),
    )

    totals = ranking_totals(ranking)

    assert totals.entities == 3
    assert totals.at_risk == 2
    assert totals.no_evidence == 1
    assert totals.energy_at_risk_mwh == pytest.approx(10.0)
    assert totals.at_risk_unknown_energy == 1
    assert totals.first_alert == T0


def test_totals_of_an_empty_ranking() -> None:
    ranking, _ = _ranking(entity_forecast("eolica", "A"))

    totals = ranking_totals(ranking.clear())

    assert totals.entities == 0
    assert totals.energy_at_risk_mwh == 0.0
    assert totals.first_alert is None


def test_summary_names_the_top_plant_and_the_provisional_predictor() -> None:
    ranking, forecast = _ranking(
        entity_forecast("eolica", "A", alerts={3: (10.0, "ENE"), 4: (2.5, "ENE")}),
        entity_forecast("eolica", "B"),
    )

    text = operational_summary(ranking, summarize_provenance(forecast))

    assert "1 de 2 usinas" in text
    assert "12,5 MWh" in text
    assert "Usina A (RN)" in text
    assert f"{(T0 + 2 * STEP):%d/%m %H:%M}" in text
    assert "ENE" in text
    assert "preditor provisório" in text
    assert "não é garantia" in text


def test_summary_mentions_plants_without_evidence_and_quiet_days() -> None:
    ranking, forecast = _ranking(
        entity_forecast("eolica", "A"),
        entity_forecast("eolica", "B", missing=set(range(1, 49))),
    )

    text = operational_summary(ranking, summarize_provenance(forecast))

    assert "Nenhuma usina em alerta" in text
    assert "1 usina sem evidência" in text


def test_summary_of_a_model_forecast_does_not_claim_baseline() -> None:
    ranking, forecast = _ranking(
        entity_forecast("eolica", "A", alerts={1: (1.0, None)}, kind="modelo", p_alert=0.8)
    )

    text = operational_summary(ranking, summarize_provenance(forecast))

    assert "preditor provisório" not in text
    assert "causa indeterminada" in text
    assert "80%" in text
