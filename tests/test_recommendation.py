from datetime import datetime, timedelta

import polars as pl
import pytest

from curtamap.contracts import FORECAST_SCHEMA, RESERVED_TEST_START, validate_recommendations
from curtamap.recommendation import (
    build_recommendations,
    group_risk_windows,
    impact_sensitivity,
    load_assumptions,
    recommendation_rule,
    summarize_history,
)

T0 = datetime(2025, 3, 10, 10)


def forecast_row(horizon: int, **overrides) -> dict:
    tau = T0 + timedelta(minutes=30 * (horizon - 1))
    row = {
        "fonte": "eolica",
        "id_ons": "NE-USI-1",
        "t0": T0,
        "horizonte": horizon,
        "tau": tau,
        "p_restricao": 0.8,
        "p_corte": 0.7,
        "limiar_alerta": 0.5,
        "alerta": True,
        "volume_condicional_mwmed": 20.0,
        "volume_esperado_mwmed": 12.0,
        "energia_esperada_mwh": 6.0,
        "volume_p10_mwmed": None,
        "volume_p90_mwmed": None,
        "causa_prevista": "ENE",
        "p_causa_rel": 0.1,
        "p_causa_cnf": 0.2,
        "p_causa_ene": 0.7,
        "origem_prevista": "SIS",
        "motivo_sem_previsao": None,
        "motivo_sem_causa": None,
        "tipo_saida": "baseline",
        "modelo_id": "baseline_teste",
        "corte_dados": datetime(2025, 3, 7),
        "cenario_disponibilidade": "teste",
        "instante_observacao": datetime(2025, 3, 6, 10),
        "cobertura_historico": 1.0,
        "gerado_em": datetime(2026, 9, 23),
    }
    row.update(overrides)
    return row


def forecast(*rows: dict) -> pl.DataFrame:
    return pl.DataFrame(rows, schema=FORECAST_SCHEMA)


def test_single_alert_is_one_half_hour_episode():
    episodes = group_risk_windows(forecast(forecast_row(1)))
    row = episodes.row(0, named=True)
    assert row["inicio"] == T0
    assert row["fim"] == T0 + timedelta(minutes=30)
    assert row["energia_em_risco_mwh"] == 6.0


def test_gap_splits_episodes_and_consecutive_alerts_are_summed():
    frame = forecast(
        forecast_row(1),
        forecast_row(2),
        forecast_row(3, p_corte=0.2, alerta=False),
        forecast_row(4),
    )
    episodes = group_risk_windows(frame)
    assert episodes.select("inicio", "fim", "energia_em_risco_mwh").rows() == [
        (T0, T0 + timedelta(hours=1), 12.0),
        (T0 + timedelta(hours=1, minutes=30), T0 + timedelta(hours=2), 6.0),
    ]


def test_same_id_from_different_sources_never_merges():
    episodes = group_risk_windows(forecast(forecast_row(1), forecast_row(1, fonte="fotovoltaica")))
    assert episodes.height == 2
    assert episodes["fonte"].to_list() == ["eolica", "fotovoltaica"]


def test_mixed_or_missing_cause_stays_unknown_instead_of_being_invented():
    no_cause = {
        "causa_prevista": None,
        "p_causa_rel": None,
        "p_causa_cnf": None,
        "p_causa_ene": None,
        "motivo_sem_causa": "tarefa_inelegivel",
    }
    episodes = group_risk_windows(forecast(forecast_row(1), forecast_row(2, **no_cause)))
    assert episodes["causa_base"].item() is None


def test_null_energy_in_alert_is_rejected_instead_of_silently_summed():
    row = forecast_row(
        1,
        volume_esperado_mwmed=None,
        energia_esperada_mwh=None,
        motivo_sem_previsao="sem_volume",
    )
    with pytest.raises(ValueError, match="energia_esperada_mwh"):
        group_risk_windows(forecast(row))


def test_sensitivity_caps_recovery_and_keeps_scenarios_explicit():
    assumptions = load_assumptions()
    result = impact_sensitivity(500.0, timedelta(hours=6), "AVALIAR_ARMAZENAMENTO", assumptions)
    assert result["cenario"].to_list() == ["baixo", "base", "alto"]
    assert (result["energia_recuperavel_mwh"] <= 500.0).all()
    assert result["energia_recuperavel_mwh"].to_list() == [102.0, 108.0, 108.0]
    assert result["valor_estimado_brl"].null_count() == 0
    assert result["co2_evitado_t"].null_count() == 0


def test_missing_assumptions_make_monetary_and_carbon_impacts_null():
    missing = {"versao": "premissas_teste", "cenarios": {"base": {}}}
    result = impact_sensitivity(10.0, timedelta(hours=1), "AVALIAR_ARMAZENAMENTO", missing)
    row = result.row(0, named=True)
    assert row["energia_recuperavel_mwh"] == 0.0
    assert row["valor_estimado_brl"] is None
    assert row["co2_evitado_t"] is None


def test_recommendations_pass_contract_and_propagate_provenance():
    recommendations = build_recommendations(forecast(forecast_row(1)), load_assumptions())
    assert validate_recommendations(recommendations).equals(recommendations)
    row = recommendations.row(0, named=True)
    assert row["tipo_saida"] == "baseline"
    assert row["modelo_id"] == "baseline_teste"
    assert row["premissas_versao"] == "premissas_v1"
    assert "cenário" in row["acao_descricao"].lower()


def test_unknown_cause_recommendation_declares_uncertainty():
    row = forecast_row(
        1,
        causa_prevista=None,
        p_causa_rel=None,
        p_causa_cnf=None,
        p_causa_ene=None,
        motivo_sem_causa="tarefa_inelegivel",
    )
    recommendation = build_recommendations(forecast(row), load_assumptions()).row(0, named=True)
    assert recommendation["causa_base"] is None
    assert recommendation["acao_codigo"] == "VALIDAR_CAUSA"
    assert "causa indeterminada" in recommendation["acao_descricao"].lower()


@pytest.mark.parametrize(
    ("cause", "code"),
    [
        ("REL", "PRESERVAR_EVIDENCIAS_ESS"),
        ("CNF", "COORDENAR_OPERACAO"),
        ("ENE", "AVALIAR_ARMAZENAMENTO"),
        ("PAR", "REVISAR_PARECER_ACESSO"),
        (None, "VALIDAR_CAUSA"),
    ],
)
def test_every_contract_cause_has_an_explicit_rule(cause, code):
    rule = recommendation_rule(cause, "fotovoltaica", "LOC", lead_hours=2.5)
    assert rule["acao_codigo"] == code
    assert "usina fotovoltaica" in rule["acao_descricao"]
    assert "2.5 h" in rule["acao_descricao"]


def test_recommendation_rule_rejects_unknown_taxonomy():
    with pytest.raises(ValueError, match="causa"):
        recommendation_rule("XYZ", "eolica", None, lead_hours=1)


def observed_rows() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "fonte": ["eolica", "eolica", "fotovoltaica"],
            "id_ons": ["A", "A", "B"],
            "din_instante": [datetime(2025, 1, 1), datetime(2025, 1, 8), datetime(2025, 1, 8)],
            "id_estado": ["RN", "RN", "BA"],
            "id_subsistema": ["NE", "NE", "NE"],
            "val_geracaolimitada": [5.0, 5.0, None],
            "val_geracaoreferencia": [20.0, 30.0, 10.0],
            "val_geracao": [10.0, 10.0, 10.0],
            "cod_razaorestricao": ["ENE", "CNF", None],
            "cod_origemrestricao": ["SIS", "LOC", None],
        },
        schema_overrides={
            "val_geracaolimitada": pl.Float64,
            "val_geracaoreferencia": pl.Float64,
            "val_geracao": pl.Float64,
            "cod_razaorestricao": pl.String,
            "cod_origemrestricao": pl.String,
        },
    )


@pytest.mark.parametrize("grain", ["semana", "mes"])
def test_tactical_summary_aggregates_observed_targets(grain):
    result = summarize_history(observed_rows(), grain)
    assert {
        "fonte",
        "id_ons",
        "periodo",
        "causa",
        "uf",
        "subsistema",
        "energia_observada_mwh",
    } <= set(result.columns)
    assert result["energia_observada_mwh"].sum() == 15.0


def test_tactical_summary_refuses_reserved_period():
    frame = observed_rows().with_columns(pl.lit(RESERVED_TEST_START).alias("din_instante"))
    with pytest.raises(ValueError, match="reservado"):
        summarize_history(frame, "mes")
