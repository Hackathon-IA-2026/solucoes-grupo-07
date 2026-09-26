from datetime import date

import numpy as np
import polars as pl
import pytest

from curtamap.experimentos.rede_temporal.avaliar import (
    add_served,
    choose_thresholds,
    error_concentration,
    monthly_wins,
    select_best,
)


def _frame(fonte: str) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "fonte": [fonte] * 3,
            "id_ons": ["A", "A", "B"],
            "dia": [date(2026, 2, 1)] * 3,
            "slot": [0, 1, 0],
            "vol_hist_28d": [5.0, None, 2.0],
            "p_B0_original": [0.9, 0.2, 0.4],
            "v_B0_original": [7.0, 3.0, 1.0],
        }
    )


def test_served_wind_volume_uses_history_and_falls_back_to_the_model() -> None:
    served = add_served(_frame("eolica"))

    assert served["v_servido"].to_list() == [5.0, 3.0, 2.0]
    assert served["p_servido"].to_list() == [0.9, 0.2, 0.4]


def test_served_solar_volume_is_the_model() -> None:
    served = add_served(_frame("fotovoltaica"))

    assert served["v_servido"].to_list() == [7.0, 3.0, 1.0]


def test_thresholds_use_only_the_selection_months() -> None:
    frame = pl.DataFrame(
        {
            "fonte": ["eolica"] * 4,
            "mes": [date(2026, 1, 1)] * 2 + [date(2026, 5, 1)] * 2,
            "y_corte": [1.0, 0.0, 1.0, 1.0],
            "p_x": [0.8, 0.3, 0.1, 0.1],
        }
    )

    thresholds = choose_thresholds(frame, ["x"], until=date(2026, 5, 1))

    assert thresholds[("eolica", "x")] == pytest.approx(0.8)


def test_best_candidate_by_mean_of_monthly_metric() -> None:
    table = pl.DataFrame(
        {
            "fonte": ["eolica"] * 4,
            "periodo": ["2026-01-01", "2026-02-01"] * 2,
            "candidato": ["a", "a", "b", "b"],
            "wape_diario": [1.0, 0.8, 0.7, 1.2],
            "ap": [0.5, 0.6, 0.7, 0.4],
        }
    )

    assert select_best(table, ["a", "b"], "wape_diario", higher=False)["eolica"] == "a"
    assert select_best(table, ["a", "b"], "ap", higher=True)["eolica"] == "a"


def test_monthly_wins_counts_strict_improvements() -> None:
    table = pl.DataFrame(
        {
            "fonte": ["eolica"] * 6,
            "periodo": ["2026-05-01", "2026-06-01", "2026-07-01"] * 2,
            "candidato": ["c"] * 3 + ["ref"] * 3,
            "wape_diario": [0.5, 0.9, 0.7, 0.6, 0.8, 0.7],
        }
    )

    wins = monthly_wins(table, "c", "ref", "wape_diario", higher=False)

    assert wins.row(0, named=True)["meses_vencidos"] == 1
    assert wins.row(0, named=True)["meses"] == 3


def test_error_concentration_ranks_plants_by_absolute_error() -> None:
    frame = pl.DataFrame(
        {
            "fonte": ["eolica"] * 4,
            "id_ons": ["A", "A", "B", "C"],
            "dia": [date(2026, 2, 1)] * 4,
            "slot": [0, 1, 0, 0],
            "y_volume": [0.0, 0.0, 10.0, 0.0],
            "v_x": [30.0, 30.0, 10.0, 20.0],
        }
    )

    top = error_concentration(frame, "v_x")

    assert top["id_ons"].to_list()[0] == "A"
    assert top["parcela_erro"].to_list()[0] == pytest.approx(60 / 80)
    assert np.isclose(top["parcela_acumulada"].to_list()[-1], 1.0)


def test_adjusted_hgb_picks_the_frozen_variant_per_source_and_component() -> None:
    from curtamap.experimentos.rede_temporal.final import adjusted_columns

    frame = pl.DataFrame(
        {
            "fonte": ["eolica", "fotovoltaica"],
            "p_B1": [0.1, 0.2],
            "p_B3": [0.3, 0.4],
            "v_B1": [1.0, 2.0],
            "v_B3": [3.0, 4.0],
        }
    )
    frozen = {
        "hgb_ocorrencia": {"eolica": "B1", "fotovoltaica": "B3"},
        "hgb_volume": {"eolica": "B3", "fotovoltaica": "B1"},
    }

    adjusted = adjusted_columns(frame, frozen)

    assert adjusted["p_B_ajustado"].to_list() == [0.1, 0.4]
    assert adjusted["v_B_ajustado"].to_list() == [3.0, 2.0]


def test_diverged_volume_variants_are_detected_in_any_source() -> None:
    from curtamap.experimentos.rede_temporal.avaliar import diverged_volume

    frame = pl.DataFrame(
        {
            "fonte": ["eolica", "eolica", "fotovoltaica", "fotovoltaica"],
            "y_volume": [100.0, 0.0, 50.0, 0.0],
            "v_ok": [90.0, 1.0, 40.0, 0.0],
            "v_grande": [90.0, 1.0, 40.0, 600.0],
            "v_infinito": [float("inf"), 1.0, 40.0, 0.0],
        }
    )

    assert diverged_volume(frame, ["ok", "grande", "infinito"]) == {"grande", "infinito"}


def test_monthly_wins_ignore_floating_point_ties() -> None:
    table = pl.DataFrame(
        {
            "fonte": ["eolica"] * 2,
            "periodo": ["2026-05-01"] * 2,
            "candidato": ["c", "ref"],
            "wape_diario": [0.6110000000000001, 0.611],
        }
    )

    wins = monthly_wins(table, "ref", "c", "wape_diario", higher=False)

    assert wins.row(0, named=True)["meses_vencidos"] == 0
