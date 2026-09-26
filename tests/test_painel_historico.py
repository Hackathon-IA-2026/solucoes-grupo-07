from datetime import date, datetime

import polars as pl
import pytest

from curtamap.contracts import RESERVED_TEST_START
from curtamap.painel.historico import DIMENSIONS, historical_losses
from curtamap.targets import derive_targets


def _raw(rows: list[tuple]) -> pl.DataFrame:
    """(fonte, id_ons, nome, UF, instante, limitada, referência, geração, causa)."""
    frame = pl.DataFrame(
        rows,
        schema={
            "fonte": pl.String,
            "id_ons": pl.String,
            "nom_usina": pl.String,
            "id_estado": pl.String,
            "din_instante": pl.Datetime("us"),
            "val_geracaolimitada": pl.Float64,
            "val_geracaoreferencia": pl.Float64,
            "val_geracao": pl.Float64,
            "cod_razaorestricao": pl.String,
        },
        orient="row",
    ).with_columns(
        pl.lit("NE").alias("id_subsistema"),
        pl.lit("LOC").alias("cod_origemrestricao"),
    )
    return derive_targets(frame)


HISTORY = _raw(
    [
        # Semana de 03/08/2026 (segunda): 10 MWmed → 5 MWh; 4 MWmed → 2 MWh.
        ("eolica", "A", "Usina A", "RN", datetime(2026, 8, 3, 10), 50, 60, 50, "ENE"),
        ("eolica", "A", "Usina A", "RN", datetime(2026, 8, 3, 10, 30), 50, 54, 50, "CNF"),
        # Mesmo id_ons em outra fonte.
        ("fotovoltaica", "A", "Solar A", "BA", datetime(2026, 8, 4, 12), 10, 16, 10, "ENE"),
        # Sem limitação: energia zero, não entra como perda.
        ("eolica", "B", None, None, datetime(2026, 8, 4, 12), None, 30, 30, None),
        # Limitação com volume inválido: contada como lacuna, não como zero.
        ("eolica", "B", None, None, datetime(2026, 8, 5, 12), 10, None, 5, "REL"),
        # Semana seguinte, causa fora do domínio.
        ("eolica", "A", "Usina A", "RN", datetime(2026, 8, 11, 1), 20, 22, 20, "XYZ"),
    ]
)


def _as_dict(frame: pl.DataFrame) -> dict:
    return {(r["periodo"], r["grupo"]): r for r in frame.iter_rows(named=True)}


def test_weekly_losses_by_cause() -> None:
    losses = _as_dict(historical_losses(HISTORY, grain="semana", dimension="causa"))

    week = date(2026, 8, 3)
    assert losses[(week, "ENE")]["energia_mwh"] == pytest.approx(8.0)
    assert losses[(week, "ENE")]["usinas"] == 2
    assert losses[(week, "CNF")]["energia_mwh"] == pytest.approx(2.0)
    assert losses[(week, "REL")]["energia_mwh"] == pytest.approx(0.0)
    assert losses[(week, "REL")]["janelas_volume_nulo"] == 1
    assert losses[(date(2026, 8, 10), "DESCONHECIDA")]["energia_mwh"] == pytest.approx(1.0)


def test_monthly_losses_by_state_label_missing_values() -> None:
    losses = _as_dict(historical_losses(HISTORY, grain="mes", dimension="id_estado"))

    month = date(2026, 8, 1)
    assert losses[(month, "RN")]["energia_mwh"] == pytest.approx(8.0)
    assert losses[(month, "BA")]["energia_mwh"] == pytest.approx(3.0)
    assert losses[(month, "não informado")]["janelas_volume_nulo"] == 1
    assert losses[(month, "RN")]["janelas_com_corte"] == 3


def test_losses_by_plant_keep_source_and_id() -> None:
    losses = historical_losses(HISTORY, grain="mes", dimension="usina")

    assert sorted(losses["grupo"].to_list()) == [
        "Solar A · fotovoltaica/A",
        "Usina A · eolica/A",
        "eolica/B",
    ]


def test_all_dimensions_are_supported() -> None:
    for dimension in DIMENSIONS:
        assert not historical_losses(HISTORY, grain="mes", dimension=dimension).is_empty()


def test_invalid_grain_or_dimension() -> None:
    with pytest.raises(ValueError, match="grain"):
        historical_losses(HISTORY, grain="dia", dimension="causa")
    with pytest.raises(ValueError, match="dimension"):
        historical_losses(HISTORY, grain="mes", dimension="cor")


def test_reserved_period_is_refused() -> None:
    late = _raw([("eolica", "A", "Usina A", "RN", RESERVED_TEST_START, 1, 2, 1, "ENE")])

    with pytest.raises(ValueError, match="reservado"):
        historical_losses(pl.concat([HISTORY, late]), grain="mes", dimension="causa")


def test_empty_history_gives_empty_losses() -> None:
    assert historical_losses(HISTORY.clear(), grain="mes", dimension="causa").is_empty()


def test_periods_cut_by_the_loaded_window_are_flagged_partial() -> None:
    partial = historical_losses(
        HISTORY,
        grain="semana",
        dimension="fonte",
        window=(datetime(2026, 8, 4), datetime(2026, 8, 12)),
    )
    complete = historical_losses(
        HISTORY,
        grain="semana",
        dimension="fonte",
        window=(datetime(2026, 8, 3), datetime(2026, 8, 17)),
    )

    assert partial["periodo_parcial"].all()
    assert not complete["periodo_parcial"].any()


def test_month_ending_exactly_at_the_window_end_is_complete() -> None:
    losses = historical_losses(
        HISTORY, grain="mes", dimension="fonte", window=(datetime(2026, 8, 1), datetime(2026, 9, 1))
    )

    assert not losses["periodo_parcial"].any()
