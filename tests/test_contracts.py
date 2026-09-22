from datetime import datetime, timedelta

import polars as pl
import pytest

from curtamap.contracts import (
    FORECAST_SCHEMA,
    HORIZONS,
    RECOMMENDATION_SCHEMA,
    ContractError,
    validate_forecast,
    validate_recommendations,
)

T0 = datetime(2025, 3, 10, 10, 0)


def _forecast_row(horizonte: int = 1, **overrides) -> dict:
    row = {
        "fonte": "eolica",
        "id_ons": "BAUSI1",
        "t0": T0,
        "horizonte": horizonte,
        "tau": T0 + timedelta(minutes=30 * (horizonte - 1)),
        "p_restricao": 0.8,
        "p_corte": 0.6,
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
        "origem_prevista": None,
        "motivo_sem_previsao": None,
        "motivo_sem_causa": None,
        "tipo_saida": "baseline",
        "modelo_id": "baseline_mesmo_horario_recente_v1",
        "corte_dados": datetime(2025, 3, 7),
        "cenario_disponibilidade": "noturno_fim_de_semana",
        "instante_observacao": datetime(2025, 3, 6, 10, 0),
        "cobertura_historico": 0.95,
        "gerado_em": datetime(2026, 9, 22, 12, 0),
    }
    row.update(overrides)
    return row


def _forecast(*rows: dict) -> pl.DataFrame:
    return pl.DataFrame(list(rows) or [_forecast_row()], schema=FORECAST_SCHEMA)


def _recommendation(**overrides) -> pl.DataFrame:
    row = {
        "fonte": "eolica",
        "id_ons": "BAUSI1",
        "t0": T0,
        "inicio": T0,
        "fim": T0 + timedelta(hours=2),
        "causa_base": "ENE",
        "acao_codigo": "ARMAZENAR",
        "acao_descricao": "Deslocar energia para armazenamento.",
        "energia_em_risco_mwh": 40.0,
        "energia_recuperavel_mwh": 10.0,
        "valor_estimado_brl": None,
        "co2_evitado_t": None,
        "premissas_versao": "premissas_v0",
        "tipo_saida": "simulado",
        "modelo_id": "baseline_mesmo_horario_recente_v1",
    }
    row.update(overrides)
    return pl.DataFrame([row], schema=RECOMMENDATION_SCHEMA)


def test_valid_forecast_is_returned_unchanged():
    frame = _forecast(*(_forecast_row(h) for h in range(1, HORIZONS + 1)))
    assert validate_forecast(frame).equals(frame)


def test_extra_columns_are_allowed_for_model_diagnostics():
    frame = _forecast().with_columns(pl.lit(1.0).alias("shap_top1"))
    assert "shap_top1" in validate_forecast(frame).columns


def test_missing_column_is_rejected():
    with pytest.raises(ContractError, match="p_corte"):
        validate_forecast(_forecast().drop("p_corte"))


def test_wrong_dtype_is_rejected():
    frame = _forecast().with_columns(pl.col("horizonte").cast(pl.Float64))
    with pytest.raises(ContractError, match="horizonte"):
        validate_forecast(frame)


def test_duplicate_key_is_rejected():
    with pytest.raises(ContractError, match="duplicada"):
        validate_forecast(_forecast(_forecast_row(), _forecast_row()))


def test_same_id_in_other_source_is_a_different_key():
    other = _forecast_row(fonte="fotovoltaica")
    assert validate_forecast(_forecast(_forecast_row(), other)).height == 2


@pytest.mark.parametrize("horizonte", [0, 49])
def test_horizon_outside_range_is_rejected(horizonte):
    with pytest.raises(ContractError, match="horizonte"):
        validate_forecast(_forecast(_forecast_row(horizonte)))


def test_tau_must_follow_horizon():
    with pytest.raises(ContractError, match="tau"):
        validate_forecast(_forecast(_forecast_row(2, tau=T0)))


@pytest.mark.parametrize("column", ["p_restricao", "p_corte", "p_causa_ene", "limiar_alerta"])
@pytest.mark.parametrize("value", [-0.01, 1.01, float("nan")])
def test_probabilities_must_be_in_unit_interval(column, value):
    with pytest.raises(ContractError, match=column):
        validate_forecast(_forecast(_forecast_row(**{column: value})))


@pytest.mark.parametrize("value", [-1.0, float("inf"), float("nan")])
def test_volume_must_be_finite_and_non_negative(value):
    row = _forecast_row(volume_esperado_mwmed=value, energia_esperada_mwh=None)
    with pytest.raises(ContractError, match="volume_esperado_mwmed"):
        validate_forecast(_forecast(row))


def test_energy_is_half_of_average_power():
    with pytest.raises(ContractError, match="energia_esperada_mwh"):
        validate_forecast(_forecast(_forecast_row(energia_esperada_mwh=12.0)))


def test_interval_bounds_must_be_ordered():
    row = _forecast_row(volume_p10_mwmed=30.0, volume_p90_mwmed=10.0)
    with pytest.raises(ContractError, match="volume_p10_mwmed"):
        validate_forecast(_forecast(row))


def test_missing_probability_requires_reason():
    row = _forecast_row(p_corte=None, alerta=None)
    with pytest.raises(ContractError, match="motivo_sem_previsao"):
        validate_forecast(_forecast(row))
    explained = _forecast_row(p_corte=None, alerta=None, motivo_sem_previsao="sem_observacao_28d")
    assert validate_forecast(_forecast(explained)).height == 1


def test_missing_cause_requires_reason():
    row = _forecast_row(causa_prevista=None, p_causa_rel=None, p_causa_cnf=None, p_causa_ene=None)
    with pytest.raises(ContractError, match="motivo_sem_causa"):
        validate_forecast(_forecast(row))
    row["motivo_sem_causa"] = "tarefa_inelegivel"
    assert validate_forecast(_forecast(row)).height == 1


@pytest.mark.parametrize("cause", ["PAR", "DESCONHECIDA", "ene"])
def test_only_learnable_causes_can_be_predicted(cause):
    with pytest.raises(ContractError, match="causa_prevista"):
        validate_forecast(_forecast(_forecast_row(causa_prevista=cause)))


def test_cause_distribution_must_sum_to_one():
    with pytest.raises(ContractError, match="p_causa"):
        validate_forecast(_forecast(_forecast_row(p_causa_ene=0.2)))


def test_alert_must_match_threshold():
    with pytest.raises(ContractError, match="alerta"):
        validate_forecast(_forecast(_forecast_row(p_corte=0.4)))


@pytest.mark.parametrize(
    ("column", "value"),
    [("fonte", "hidreletrica"), ("tipo_saida", "real"), ("origem_prevista", "XXX")],
)
def test_categorical_domains_are_closed(column, value):
    with pytest.raises(ContractError, match=column):
        validate_forecast(_forecast(_forecast_row(**{column: value})))


def test_data_cutoff_cannot_be_after_issue_time():
    with pytest.raises(ContractError, match="corte_dados"):
        validate_forecast(_forecast(_forecast_row(corte_dados=T0 + timedelta(minutes=30))))


def test_model_id_is_required():
    with pytest.raises(ContractError, match="modelo_id"):
        validate_forecast(_forecast(_forecast_row(modelo_id="")))


def test_valid_recommendation_passes():
    frame = _recommendation()
    assert validate_recommendations(frame).equals(frame)


def test_recoverable_energy_cannot_exceed_energy_at_risk():
    with pytest.raises(ContractError, match="energia_recuperavel_mwh"):
        validate_recommendations(_recommendation(energia_recuperavel_mwh=41.0))


def test_recommendation_requires_assumptions_version():
    with pytest.raises(ContractError, match="premissas_versao"):
        validate_recommendations(_recommendation(premissas_versao=None))


def test_recommendation_window_must_be_ordered():
    with pytest.raises(ContractError, match="fim"):
        validate_recommendations(_recommendation(fim=T0))


@pytest.mark.parametrize(
    ("overrides", "column"),
    [
        ({"p_corte": None, "alerta": True, "motivo_sem_previsao": "x"}, "alerta"),
        ({"limiar_alerta": None, "alerta": False}, "limiar_alerta"),
        ({"tau": None}, "tau"),
        ({"energia_esperada_mwh": None}, "energia_esperada_mwh"),
        ({"cenario_disponibilidade": ""}, "cenario_disponibilidade"),
        ({"cobertura_historico": 1.5}, "cobertura_historico"),
        ({"instante_observacao": T0}, "instante_observacao"),
        ({"causa_prevista": "REL"}, "causa_prevista"),
    ],
)
def test_null_or_incoherent_fields_are_rejected(overrides, column):
    with pytest.raises(ContractError, match=column):
        validate_forecast(_forecast(_forecast_row(**overrides)))


@pytest.mark.parametrize("column", ["energia_em_risco_mwh", "energia_recuperavel_mwh"])
def test_recommendation_energy_is_required(column):
    with pytest.raises(ContractError, match=column):
        validate_recommendations(_recommendation(**{column: None}))


def test_recommendation_may_state_unknown_cause():
    assert validate_recommendations(_recommendation(causa_base=None)).height == 1
