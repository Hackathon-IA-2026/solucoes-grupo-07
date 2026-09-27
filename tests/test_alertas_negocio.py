from datetime import datetime, timedelta

import polars as pl
import pytest

from curtamap.alertas_negocio import opportunity_cost, read_pld, select_window


def test_pld_matches_hour_zero_and_last_hour_without_shift(tmp_path):
    path = tmp_path / "pld.csv"
    path.write_text(
        "MES_REFERENCIA;SUBMERCADO;DIA;HORA;PLD_HORA\n"
        "202608;NORDESTE;1;0;123.45\n202608;SUDESTE;1;23;234.56\n"
    )
    prices = read_pld(path)
    assert prices["hora"].to_list() == [datetime(2026, 8, 1), datetime(2026, 8, 1, 23)]
    assert prices["id_subsistema"].to_list() == ["NE", "SE"]


def test_duplicate_or_invalid_prices_fail_instead_of_multiplying_money(tmp_path):
    path = tmp_path / "pld.csv"
    path.write_text(
        "MES_REFERENCIA;SUBMERCADO;DIA;HORA;PLD_HORA\n"
        "202608;NORDESTE;1;0;123.45\n202608;NORDESTE;1;0;123.45\n"
    )
    with pytest.raises(ValueError):
        read_pld(path)


def profile():
    return pl.DataFrame(
        {
            "tau": [datetime(2026, 8, 1) + timedelta(minutes=30 * i) for i in range(48)],
            "p_corte": [0.1] * 20 + [0.9] * 4 + [0.1] * 24,
            "geracao_mw": [10.0] * 48,
            "pld_brl_mwh": [100.0] * 48,
        }
    )


def test_window_uses_only_probability_and_stays_in_working_hours():
    frame = profile()
    assert select_window(frame, "p_corte") == 20  # 10h–12h
    poisoned = frame.with_columns(pl.lit(1e9).alias("geracao_mw"), pl.lit(1.0).alias("pld_brl_mwh"))
    assert select_window(poisoned, "p_corte") == 20
    assert (
        select_window(frame.with_columns(pl.lit(None, pl.Float64).alias("p_corte")), "p_corte")
        is None
    )


def test_cost_has_half_hour_and_fraction_units_and_preserves_unknown():
    assert opportunity_cost(profile(), 20, fraction=0.1) == 200.0
    assert opportunity_cost(profile(), 20, fraction=0.2) == 400.0
    assert (
        opportunity_cost(
            profile().with_columns(pl.lit(None, pl.Float64).alias("pld_brl_mwh")), 20, fraction=0.1
        )
        is None
    )
    with pytest.raises(ValueError):
        opportunity_cost(profile(), 20, fraction=1.5)


def test_historical_cause_is_observed_only_before_cutoff():
    from curtamap.alertas_negocio import historical_context

    cutoff = datetime(2026, 8, 1)
    history = pl.DataFrame(
        {
            "fonte": ["eolica"] * 3,
            "id_ons": ["A"] * 3,
            "din_instante": [cutoff - timedelta(days=29), cutoff - timedelta(hours=1), cutoff],
            "val_geracao": [999.0, 10.0, 999.0],
            "causa": ["CNF", "ENE", "REL"],
            "restricao_registrada": [True] * 3,
        }
    )
    generation, causes = historical_context(history, cutoff)
    assert generation["geracao_historica_28d"].to_list() == [10.0]
    assert causes["causa"].to_list() == ["ENE"]
    assert causes["n_ordens"].to_list() == [1]
    assert causes["participacao"].to_list() == [1.0]


def test_all_missing_costs_produce_no_estimated_savings():
    from curtamap.alertas_negocio import summarize

    row = {
        "fonte": "eolica",
        "cenario": "PLD_CCEE_observado",
        "avaliavel": False,
        "custo_curtamap_brl": None,
    }
    for name in ("fixo_08h", "historico_corte", "menor_geracao_historica"):
        row[f"custo_{name}_brl"] = None
        row[f"diferenca_vs_{name}_brl"] = None
    summary = summarize(pl.DataFrame([row]))
    assert summary["avaliaveis"].to_list() == [0, 0, 0]
    assert summary["diferenca_soma_brl"].null_count() == 3
