"""Casos sintéticos; nenhuma observação do teste reservado é consultada."""

import json
from datetime import datetime, timedelta

import polars as pl
import pytest
from test_forecasting import CUTOFF, RAW_TYPES, T0, _row
from test_recommendation import forecast, forecast_row, observed_rows

from curtamap.contracts import FORECAST_SCHEMA
from curtamap.forecasting import SameSlotRecentBaseline, load_history
from curtamap.recommendation import (
    build_recommendations,
    group_risk_windows,
    impact_sensitivity,
    load_assumptions,
    recommendation_rule,
    summarize_history,
)

ACTION = "AVALIAR_ARMAZENAMENTO"


@pytest.mark.parametrize("energy", [-1, float("nan"), float("inf"), True])
def test_invalid_energy_is_rejected(energy):
    with pytest.raises(ValueError, match="energia"):
        impact_sensitivity(energy, timedelta(hours=1), ACTION, load_assumptions())


@pytest.mark.parametrize("hours", [-1, 0])
def test_nonpositive_duration_is_rejected(hours):
    with pytest.raises(ValueError, match="dura"):
        impact_sensitivity(10, timedelta(hours=hours), ACTION, load_assumptions())


@pytest.mark.parametrize(
    "field,value",
    [
        ("potencia_mw", -1),
        ("capacidade_mwh", -1),
        ("eficiencia", -0.1),
        ("eficiencia", 1.1),
        ("eficiencia", float("nan")),
        ("potencia_mw", float("inf")),
    ],
)
def test_invalid_storage_is_rejected(field, value):
    a = load_assumptions()
    a["cenarios"]["base"]["armazenamento"][field]["valor"] = value
    with pytest.raises(ValueError):
        impact_sensitivity(10, timedelta(hours=1), ACTION, a)


@pytest.mark.parametrize("field", ["preco_energia_brl_mwh", "fator_emissao_tco2_mwh"])
@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True])
def test_invalid_price_or_carbon_is_rejected(field, value):
    a = load_assumptions()
    a["cenarios"]["alto"][field]["valor"] = value
    with pytest.raises(ValueError):
        impact_sensitivity(10, timedelta(hours=1), ACTION, a)


@pytest.mark.parametrize(
    "field,value",
    [
        ("unidade", "kWh"),
        ("fonte", ""),
        ("url", "file:///tmp/x"),
        ("url", "https://"),
        ("consultado_em", "2026-02-30"),
        ("valor", "30"),
        ("extra", 1),
    ],
)
def test_load_validates_metadata_and_schema(tmp_path, field, value):
    a = load_assumptions()
    a["cenarios"]["base"]["armazenamento"]["potencia_mw"][field] = value
    path = tmp_path / "premissas.json"
    path.write_text(json.dumps(a), encoding="utf-8")
    with pytest.raises(ValueError):
        load_assumptions(path)


@pytest.mark.parametrize("part", ["baixo", "base", "alto"])
def test_missing_scenario_is_rejected(part):
    a = load_assumptions()
    del a["cenarios"][part]
    with pytest.raises(ValueError, match="cenarios"):
        impact_sensitivity(10, timedelta(hours=1), ACTION, a)


def test_missing_storage_value_is_unknown_and_cannot_enter_required_energy_contract():
    a = load_assumptions()
    a["cenarios"]["base"]["armazenamento"]["eficiencia"]["valor"] = None
    a["cenarios"]["base"]["armazenamento"]["eficiencia"]["lacuna"] = "Sem dado do ativo"
    result = impact_sensitivity(10, timedelta(hours=1), ACTION, a)
    assert result.filter(pl.col("cenario") == "base")["energia_recuperavel_mwh"].item() is None
    with pytest.raises(ValueError, match="indeterminada"):
        build_recommendations(forecast(forecast_row(1)), a)


def test_missing_price_preserves_null():
    a = load_assumptions()
    a["cenarios"]["base"]["preco_energia_brl_mwh"]["valor"] = None
    a["cenarios"]["base"]["preco_energia_brl_mwh"]["lacuna"] = "Sem preço aplicável"
    assert impact_sensitivity(10, timedelta(hours=1), ACTION, a)["valor_estimado_brl"][1] is None


def test_unknown_action_is_rejected():
    with pytest.raises(ValueError, match="acao"):
        impact_sensitivity(10, timedelta(hours=1), "XYZ", load_assumptions())


@pytest.mark.parametrize("origin,hours", [("XXX", 1), ("SIS", -1), ("LOC", float("nan"))])
def test_rule_rejects_bad_origin_or_lead(origin, hours):
    with pytest.raises(ValueError):
        recommendation_rule("ENE", "eolica", origin, lead_hours=hours)


def test_tactical_all_null_and_partially_null_are_not_totals():
    base = observed_rows().head(1)
    bad = base.with_columns(pl.lit(None, pl.Float64).alias("val_geracao"))
    for frame, valid in [
        (bad, 0),
        (
            pl.concat(
                [
                    base,
                    bad.with_columns(
                        (pl.col("din_instante") + timedelta(minutes=30)).alias("din_instante")
                    ),
                ]
            ),
            1,
        ),
    ]:
        row = summarize_history(frame).row(0, named=True)
        assert row["energia_observada_mwh"] is None
        assert row["janelas_volume_nulo"] == 1
        assert row["janelas_volume_valido"] == valid
        assert row["janelas_corte_indeterminado"] == 1
        assert row["energia_conhecida_mwh"] == (5.0 if valid else None)


@pytest.mark.parametrize(
    "col,value",
    [
        ("modelo_id", "outro"),
        ("tipo_saida", "modelo"),
        ("cenario_disponibilidade", "outra"),
        ("corte_dados", datetime(2025, 3, 6)),
        ("gerado_em", datetime(2026, 9, 22)),
    ],
)
def test_inconsistent_issue_provenance_is_rejected(col, value):
    # Observation times can differ legitimately; issue metadata cannot.
    row = forecast_row(2, **{col: value})
    row["instante_observacao"] = datetime(2025, 3, 5)
    with pytest.raises(ValueError, match="proveniencia"):
        group_risk_windows(forecast(forecast_row(1), row))


def test_off_grid_issue_is_rejected():
    row = forecast_row(1)
    row["t0"] += timedelta(minutes=1)
    row["tau"] += timedelta(minutes=1)
    with pytest.raises(ValueError, match="grade"):
        group_risk_windows(forecast(row))


def test_recommendation_guard_rejects_forecast_metadata_before_aggregation():
    # Only forecast timestamps, no reserved observed data or values.
    row = forecast_row(1, t0=datetime(2026, 5, 1), tau=datetime(2026, 5, 1))
    with pytest.raises(ValueError, match="reservado"):
        group_risk_windows(forecast(row))


def test_missing_horizon_splits_and_partial_issue_is_not_completed():
    frame = forecast(forecast_row(1), forecast_row(3))
    result = group_risk_windows(frame)
    assert result.height == 2
    assert result["energia_em_risco_mwh"].sum() == 12


def test_cause_and_origin_changes_remain_indeterminate():
    changed = forecast_row(
        2, causa_prevista="CNF", p_causa_cnf=0.7, p_causa_ene=0.2, origem_prevista="LOC"
    )
    row = group_risk_windows(forecast(forecast_row(1), changed)).row(0, named=True)
    assert row["causa_base"] is None and row["origem_base"] is None


def test_overlapping_issues_stay_separate():
    a = forecast_row(2)
    b = forecast_row(1, t0=a["tau"], tau=a["tau"])
    result = group_risk_windows(forecast(a, b))
    assert result.height == 2


def test_empty_forecast_preserves_schema():
    from curtamap.contracts import RECOMMENDATION_SCHEMA

    assert (
        build_recommendations(pl.DataFrame(schema=FORECAST_SCHEMA)).schema == RECOMMENDATION_SCHEMA
    )


def test_recovery_uses_each_half_hour_power_limit():
    frame = forecast(
        forecast_row(1, volume_esperado_mwmed=198.0, energia_esperada_mwh=99.0),
        forecast_row(2, volume_esperado_mwmed=2.0, energia_esperada_mwh=1.0),
    )
    # 30 MW: only 15 + 1 MWh can be charged, not min(100, 30 * 1h).
    row = build_recommendations(frame).row(0, named=True)
    assert row["energia_recuperavel_mwh"] == pytest.approx(16 * 0.9)


def test_scenario_names_do_not_imply_monotonicity():
    a = load_assumptions()
    a["cenarios"]["alto"]["armazenamento"]["potencia_mw"]["valor"] = 1
    result = impact_sensitivity(20, timedelta(hours=1), ACTION, a)
    assert result["energia_recuperavel_mwh"][2] < result["energia_recuperavel_mwh"][1]


@pytest.mark.parametrize("energy", [0, 0.01, 10, 120, 1e6])
@pytest.mark.parametrize("hours", [0.5, 1, 24])
def test_recoverable_energy_bounds(energy, hours):
    result = impact_sensitivity(energy, timedelta(hours=hours), ACTION, load_assumptions())
    assert result["energia_recuperavel_mwh"].is_between(0, energy).all()


def test_load_baseline_recommendations_end_to_end(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    rows = [_row(datetime(2025, 3, 9, 10), limit=5.0, ref=30.0, gen=10.0, cause="ENE")]
    pl.DataFrame(rows, schema_overrides=RAW_TYPES).write_parquet(
        raw / "constrained_off_eolica_tm.parquet"
    )
    history = load_history(tmp_path, datetime(2025, 3, 9), CUTOFF, sources=("eolica",))
    predictions = SameSlotRecentBaseline().predict(history, T0, CUTOFF)
    result = build_recommendations(predictions)
    assert predictions.height == 48
    assert predictions["energia_esperada_mwh"].null_count() == 47
    assert result.height == 1
    assert result["energia_em_risco_mwh"].item() == 10
    assert result["energia_recuperavel_mwh"].item() == 9


def test_capacity_is_useful_output_and_roundtrip_applied_once():
    a = load_assumptions()
    assert a["base_capacidade"] == "saida_util"
    # Charge 150 MWh, deliver min(150 * .9, 120) = 120, not 108.
    result = impact_sensitivity(150, timedelta(hours=5), ACTION, a)
    assert result["energia_recuperavel_mwh"].to_list() == [120, 120, 120]


def test_legacy_assumptions_preserve_input_capacity_convention():
    from curtamap.recommendation import DEFAULT_ASSUMPTIONS_PATH

    a = load_assumptions(DEFAULT_ASSUMPTIONS_PATH.with_name("v1.json"))
    result = impact_sensitivity(500, timedelta(hours=6), ACTION, a)
    assert result["energia_recuperavel_mwh"].to_list() == [102, 108, 108]


def test_numeric_overflow_is_rejected():
    a = load_assumptions()
    a["cenarios"]["base"]["preco_energia_brl_mwh"]["valor"] = 1e308
    with pytest.raises(ValueError, match="overflow"):
        impact_sensitivity(100, timedelta(hours=1), ACTION, a)


@pytest.mark.parametrize("profile", [[1], [1, -1], [float("nan"), 2], [4, 4]])
def test_inconsistent_profiles_are_rejected(profile):
    with pytest.raises(ValueError):
        impact_sensitivity(
            10, timedelta(hours=1), ACTION, load_assumptions(), energy_profile_mwh=profile
        )


def test_null_timestamp_is_not_accepted_in_tactical_summary():
    frame = observed_rows().with_columns(pl.lit(None, pl.Datetime("us")).alias("din_instante"))
    with pytest.raises(ValueError, match="din_instante"):
        summarize_history(frame)


def test_historical_demo_profile_respects_power_limit():
    # Reconstituição 29/04/2026, histórico 26-27/04; fonte+entidade no relatório.
    profile = [2.9865, 83.5655, 61.4625, 0.1255]
    result = impact_sensitivity(
        sum(profile), timedelta(hours=2), ACTION, load_assumptions(), energy_profile_mwh=profile
    )
    assert result["energia_recuperavel_mwh"].to_list() == pytest.approx([28.1452, 29.8008, 29.8008])
    assert result["valor_estimado_brl"].to_list() == pytest.approx(
        [1649.30872, 9246.890232, 22402.155384]
    )


def test_real_small_pre_reserved_window_end_to_end():
    from curtamap.config import settings
    from curtamap.data_contract import SPECS
    from curtamap.forecasting import nightly_cutoff

    if not all(
        (settings.data_dir / "raw" / SPECS[s].filename).exists() for s in ("eolica", "fotovoltaica")
    ):
        pytest.skip("Recorte real opcional: Parquet principais ausentes")
    issue = datetime(2026, 4, 29, 10)
    end = nightly_cutoff(issue)
    history = load_history(settings.data_dir, end - timedelta(days=2), end)
    assert history.height and history["din_instante"].max() < datetime(2026, 5, 1)
    predictions = SameSlotRecentBaseline().predict(history, issue, end)
    result = build_recommendations(predictions)
    assert result.height
    assert result.select(
        (pl.col("energia_recuperavel_mwh") <= pl.col("energia_em_risco_mwh")).all()
    ).item()
