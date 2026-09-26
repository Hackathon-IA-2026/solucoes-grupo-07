from datetime import timedelta

import polars as pl
import pytest
from painel_dados import NO_EVIDENCE, T0, entities, entity_forecast

from curtamap.contracts import RECOMMENDATION_SCHEMA, STEP, validate_recommendations
from curtamap.painel.ranking import (
    STATUS_ALERT,
    STATUS_NO_ALERT,
    STATUS_NO_EVIDENCE,
    filter_ranking,
    rank_entities,
    window_profile,
)

ATTRS = entities(
    ("eolica", "A", "Usina A", "RN", "NE"),
    ("eolica", "B", "Usina B", "BA", "NE"),
    ("fotovoltaica", "A", "Solar A", "MG", "SE"),
    ("eolica", "C", "Usina C", None, None),
)


def _row(ranking: pl.DataFrame, fonte: str, id_ons: str) -> dict:
    return ranking.filter((pl.col("fonte") == fonte) & (pl.col("id_ons") == id_ons)).row(
        0, named=True
    )


def _recommendation(fonte: str, id_ons: str, start_h: int, code: str) -> dict:
    inicio = T0 + (start_h - 1) * STEP
    return {
        "fonte": fonte,
        "id_ons": id_ons,
        "t0": T0,
        "inicio": inicio,
        "fim": inicio + STEP,
        "causa_base": "ENE",
        "acao_codigo": code,
        "acao_descricao": f"descrição {code}",
        "energia_em_risco_mwh": 5.0,
        "energia_recuperavel_mwh": 1.0,
        "valor_estimado_brl": None,
        "co2_evitado_t": None,
        "premissas_versao": "teste",
        "tipo_saida": "simulado",
        "modelo_id": "teste",
    }


def test_alert_energy_first_window_and_cause() -> None:
    forecast = entity_forecast("eolica", "A", alerts={3: (10.0, "ENE"), 4: (5.0, "ENE")})

    row = _row(rank_entities(forecast, ATTRS), "eolica", "A")

    assert row["status"] == STATUS_ALERT
    assert row["janelas_alerta"] == 2
    assert row["energia_em_risco_mwh"] == pytest.approx(15.0)
    assert row["primeira_janela_alerta"] == T0 + 2 * STEP
    assert row["causa_provavel"] == "ENE"
    assert row["causa_mista"] is False
    assert row["confianca"] == pytest.approx(1.0)
    assert (row["nom_usina"], row["id_estado"], row["id_subsistema"]) == ("Usina A", "RN", "NE")


def test_same_id_ons_in_different_sources_stays_separate() -> None:
    forecast = pl.concat(
        [
            entity_forecast("eolica", "A", alerts={1: (10.0, "ENE")}),
            entity_forecast("fotovoltaica", "A", alerts={20: (3.0, "CNF")}),
        ]
    )

    ranking = rank_entities(forecast, ATTRS)

    assert ranking.height == 2
    solar = _row(ranking, "fotovoltaica", "A")
    assert solar["nom_usina"] == "Solar A"
    assert solar["energia_em_risco_mwh"] == pytest.approx(3.0)
    assert solar["causa_provavel"] == "CNF"


def test_entity_without_evidence_is_never_zero() -> None:
    forecast = entity_forecast("eolica", "B", missing=set(range(1, 49)))

    row = _row(rank_entities(forecast, ATTRS), "eolica", "B")

    assert row["status"] == STATUS_NO_EVIDENCE
    assert row["janelas_sem_evidencia"] == 48
    assert row["energia_em_risco_mwh"] is None
    assert row["energia_esperada_24h_mwh"] is None
    assert row["confianca"] is None
    assert row["motivo_sem_previsao"] == NO_EVIDENCE


def test_quiet_entity_has_zero_risk_and_partial_gaps_are_counted() -> None:
    forecast = entity_forecast("eolica", "A", missing={47, 48})

    row = _row(rank_entities(forecast, ATTRS), "eolica", "A")

    assert row["status"] == STATUS_NO_ALERT
    assert row["janelas_alerta"] == 0
    assert row["janelas_sem_evidencia"] == 2
    # Zero conhecido: há previsão e nenhuma janela em alerta.
    assert row["energia_em_risco_mwh"] == 0.0
    assert row["energia_esperada_24h_mwh"] == pytest.approx(0.0)
    assert row["primeira_janela_alerta"] is None
    assert row["causa_provavel"] is None


def test_alert_with_unknown_volume_keeps_energy_unknown() -> None:
    forecast = entity_forecast("eolica", "A", alerts={5: (None, "REL")})

    row = _row(rank_entities(forecast, ATTRS), "eolica", "A")

    assert row["status"] == STATUS_ALERT
    assert row["energia_em_risco_mwh"] is None


def test_mixed_causes_pick_the_largest_energy_and_flag_it() -> None:
    forecast = entity_forecast(
        "eolica", "A", alerts={1: (2.0, "CNF"), 2: (2.0, "CNF"), 3: (9.0, "ENE"), 4: (1.0, None)}
    )

    row = _row(rank_entities(forecast, ATTRS), "eolica", "A")

    assert row["causa_provavel"] == "ENE"
    assert row["causa_mista"] is True


def test_ranking_order_alerts_by_energy_then_no_evidence_then_quiet() -> None:
    forecast = pl.concat(
        [
            entity_forecast("eolica", "A", alerts={1: (1.0, "ENE")}),
            entity_forecast("eolica", "B", missing=set(range(1, 49))),
            entity_forecast("fotovoltaica", "A", alerts={10: (8.0, "ENE")}),
            entity_forecast("eolica", "C"),
        ]
    )

    ranking = rank_entities(forecast, ATTRS)

    assert list(zip(ranking["fonte"], ranking["id_ons"], strict=True)) == [
        ("fotovoltaica", "A"),
        ("eolica", "A"),
        ("eolica", "B"),
        ("eolica", "C"),
    ]


def test_entity_missing_from_attributes_keeps_its_forecast() -> None:
    forecast = entity_forecast("eolica", "Z", alerts={1: (1.0, "ENE")})

    row = _row(rank_entities(forecast, ATTRS), "eolica", "Z")

    assert row["nom_usina"] is None
    assert row["energia_em_risco_mwh"] == pytest.approx(1.0)


def test_confidence_is_the_mean_probability_of_alert_windows() -> None:
    forecast = entity_forecast(
        "eolica", "A", alerts={1: (1.0, "ENE"), 2: (1.0, "ENE")}, p_alert=0.7
    )

    assert _row(rank_entities(forecast, ATTRS), "eolica", "A")["confianca"] == pytest.approx(0.7)


def test_recommendation_joins_by_source_and_id_and_takes_the_first() -> None:
    forecast = pl.concat(
        [
            entity_forecast("eolica", "A", alerts={1: (1.0, "ENE"), 10: (1.0, "ENE")}),
            entity_forecast("fotovoltaica", "A"),
        ]
    )
    recommendations = validate_recommendations(
        pl.DataFrame(
            [
                _recommendation("eolica", "A", 10, "SEGUNDA"),
                _recommendation("eolica", "A", 1, "PRIMEIRA"),
            ],
            schema=RECOMMENDATION_SCHEMA,
        )
    )

    ranking = rank_entities(forecast, ATTRS, recommendations)

    assert _row(ranking, "eolica", "A")["acao_codigo"] == "PRIMEIRA"
    assert _row(ranking, "eolica", "A")["acao_tipo_saida"] == "simulado"
    assert _row(ranking, "fotovoltaica", "A")["acao_codigo"] is None


def test_recommendation_from_another_emission_is_ignored() -> None:
    forecast = entity_forecast("eolica", "A", alerts={1: (1.0, "ENE")})
    other = _recommendation("eolica", "A", 1, "ANTIGA")
    other.update(t0=T0 - timedelta(days=1), inicio=T0 - timedelta(days=1))
    other["fim"] = other["inicio"] + STEP

    ranking = rank_entities(forecast, ATTRS, pl.DataFrame([other], schema=RECOMMENDATION_SCHEMA))

    assert _row(ranking, "eolica", "A")["acao_codigo"] is None


def test_filters_combine_and_empty_means_all() -> None:
    forecast = pl.concat(
        [
            entity_forecast("eolica", "A"),
            entity_forecast("eolica", "B"),
            entity_forecast("fotovoltaica", "A"),
            entity_forecast("eolica", "C"),
        ]
    )
    ranking = rank_entities(forecast, ATTRS)

    assert filter_ranking(ranking).height == 4
    assert filter_ranking(ranking, fontes=["eolica"]).height == 3
    assert filter_ranking(ranking, fontes=["eolica"], ufs=["BA"])["id_ons"].to_list() == ["B"]
    assert filter_ranking(ranking, subsistemas=["SE"])["fonte"].to_list() == ["fotovoltaica"]
    # Usina sem UF só aparece quando a UF não está filtrada.
    assert "C" not in filter_ranking(ranking, ufs=["RN", "BA", "MG"])["id_ons"].to_list()


def test_window_profile_labels_each_window() -> None:
    forecast = pl.concat(
        [
            entity_forecast("eolica", "A", alerts={2: (4.0, "ENE")}, missing={3}),
            entity_forecast("fotovoltaica", "A", alerts={1: (9.0, "CNF")}),
        ]
    )

    profile = window_profile(forecast, "eolica", "A")

    assert profile.height == 48
    assert profile["horizonte"].to_list() == list(range(1, 49))
    assert profile["status"][:3].to_list() == [STATUS_NO_ALERT, STATUS_ALERT, STATUS_NO_EVIDENCE]
    assert profile["energia_esperada_mwh"][1] == pytest.approx(4.0)


def test_window_profile_of_unknown_entity_is_empty() -> None:
    assert window_profile(entity_forecast("eolica", "A"), "eolica", "X").is_empty()
