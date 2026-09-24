"""Testes para a lógica da interface do CurtaMap (ui_logic.py)."""

from datetime import datetime
import polars as pl
import pytest

from curtamap.contracts import validate_recommendations
from curtamap.ui_logic import (
    compute_tactical_history_summary,
    filter_forecasts,
    format_no_forecast_reason,
    generate_simulated_recommendations,
    get_entity_horizon_profile,
    rank_entities_at_risk,
)


@pytest.fixture
def mock_forecasts() -> pl.DataFrame:
    t0 = datetime(2026, 4, 15, 10, 0)
    rows = []
    # Usina A: com alertas
    for h in range(1, 49):
        tau = t0 + pl.duration(minutes=30 * (h - 1))
        alerta = h <= 10
        p_corte = 0.85 if alerta else 0.10
        rows.append(
            {
                "fonte": "eolica",
                "id_ons": "EOL_A",
                "t0": t0,
                "horizonte": h,
                "tau": tau,
                "p_restricao": 0.9,
                "p_corte": p_corte,
                "limiar_alerta": 0.5,
                "alerta": alerta,
                "volume_condicional_mwmed": 100.0,
                "volume_esperado_mwmed": 85.0 if alerta else 10.0,
                "energia_esperada_mwh": 42.5 if alerta else 5.0,
                "volume_p10_mwmed": 5.0,
                "volume_p90_mwmed": 95.0,
                "causa_prevista": "ENE",
                "p_causa_rel": 0.1,
                "p_causa_cnf": 0.2,
                "p_causa_ene": 0.7,
                "origem_prevista": "SIS",
                "motivo_sem_previsao": None,
                "motivo_sem_causa": None,
                "tipo_saida": "baseline",
                "modelo_id": "SameSlotRecentBaseline",
                "corte_dados": datetime(2026, 4, 14, 0, 0),
                "cenario_disponibilidade": "nightly_cutoff",
                "instante_observacao": datetime(2026, 4, 13, 10, 0),
                "cobertura_historico": 1.0,
                "gerado_em": datetime(2026, 4, 15, 10, 5),
            }
        )
    # Usina B: sem previsão
    for h in range(1, 49):
        tau = t0 + pl.duration(minutes=30 * (h - 1))
        rows.append(
            {
                "fonte": "fotovoltaica",
                "id_ons": "SOL_B",
                "t0": t0,
                "horizonte": h,
                "tau": tau,
                "p_restricao": None,
                "p_corte": None,
                "limiar_alerta": None,
                "alerta": None,
                "volume_condicional_mwmed": None,
                "volume_esperado_mwmed": None,
                "energia_esperada_mwh": None,
                "volume_p10_mwmed": None,
                "volume_p90_mwmed": None,
                "causa_prevista": None,
                "p_causa_rel": None,
                "p_causa_cnf": None,
                "p_causa_ene": None,
                "origem_prevista": None,
                "motivo_sem_previsao": "historico_insuficiente",
                "motivo_sem_causa": "sem_previsao",
                "tipo_saida": "baseline",
                "modelo_id": "SameSlotRecentBaseline",
                "corte_dados": datetime(2026, 4, 14, 0, 0),
                "cenario_disponibilidade": "nightly_cutoff",
                "instante_observacao": None,
                "cobertura_historico": 0.2,
                "gerado_em": datetime(2026, 4, 15, 10, 5),
            }
        )
    return pl.DataFrame(rows)


def test_filter_forecasts(mock_forecasts):
    # Sem filtros
    res = filter_forecasts(mock_forecasts, fonte=None, subsistema=None, uf=None)
    assert len(res) == 96

    # Filtro de fonte
    res_eolica = filter_forecasts(mock_forecasts, fonte="eolica")
    assert len(res_eolica) == 48
    assert res_eolica["id_ons"].unique().to_list() == ["EOL_A"]


def test_rank_entities_at_risk(mock_forecasts):
    ranked = rank_entities_at_risk(mock_forecasts)
    assert len(ranked) == 2
    # Usina EOL_A deve estar em 1º devido a maior energia em risco
    top_entity = ranked[0]
    assert top_entity["id_ons"] == "EOL_A"
    assert top_entity["total_alertas"] == 10
    assert top_entity["energia_em_risco_mwh"] > 0
    assert top_entity["causa_predominante"] == "ENE"

    # Usina SOL_B deve aparecer sem evidência
    bot_entity = ranked[1]
    assert bot_entity["id_ons"] == "SOL_B"
    assert bot_entity["tem_previsao"] is False


def test_get_entity_horizon_profile(mock_forecasts):
    profile = get_entity_horizon_profile(mock_forecasts, fonte="eolica", id_ons="EOL_A")
    assert len(profile) == 48
    assert profile["horizonte"].to_list() == list(range(1, 49))


def test_format_no_forecast_reason():
    assert "Histórico" in format_no_forecast_reason("historico_insuficiente")
    assert "Disponível" in format_no_forecast_reason("desconhecido") or "sem" in format_no_forecast_reason("desconhecido").lower()
    assert format_no_forecast_reason(None) == "Previsão normal"


def test_generate_simulated_recommendations(mock_forecasts):
    recs = generate_simulated_recommendations(mock_forecasts)
    # Valida contra o RECOMMENDATION_SCHEMA estrito
    validated = validate_recommendations(recs)
    assert len(validated) > 0
    assert validated["tipo_saida"].unique().to_list() == ["simulado"]


def test_compute_tactical_history_summary():
    history_data = pl.DataFrame(
        [
            {
                "fonte": "eolica",
                "id_ons": "EOL_A",
                "din_instante": datetime(2025, 6, 1, 10, 0),
                "val_geracao": 10.0,
                "val_referenciageração": 50.0,
                "razao_limite": "ENE",
                "origem_limite": "SIS",
                "val_limitegeracao": 10.0,
                "uf": "RN",
                "subsistema": "NE",
            },
            {
                "fonte": "eolica",
                "id_ons": "EOL_A",
                "din_instante": datetime(2025, 6, 1, 10, 30),
                "val_geracao": 10.0,
                "val_referenciageração": 60.0,
                "razao_limite": "ENE",
                "origem_limite": "SIS",
                "val_limitegeracao": 10.0,
                "uf": "RN",
                "subsistema": "NE",
            },
        ]
    )
    summary = compute_tactical_history_summary(history_data)
    assert len(summary) > 0
    assert "corte_mwh" in summary.columns
    assert summary["corte_mwh"].sum() == 45.0  # (40 + 50) * 0.5 MWh
