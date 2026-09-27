from datetime import date, datetime, timedelta

import polars as pl
import pytest

from zelo.forecasting import load_history
from zelo.previsao.calendario import load_calendar
from zelo.previsao.features import (
    FEATURES,
    base_from_history,
    build_features,
    release_map,
)
from zelo.targets import derive_targets

CAL = load_calendar()
RAW_TYPES = {
    "din_instante": pl.Datetime("us"),
    "val_geracaolimitada": pl.Float64,
    "val_geracaoreferencia": pl.Float64,
    "val_geracao": pl.Float64,
    "cod_razaorestricao": pl.String,
    "cod_origemrestricao": pl.String,
}


def _row(when, *, id_ons="BAUSI1", fonte="eolica", estado="BA", cut=0.0, cause="ENE"):
    limited = cut > 0
    return {
        "fonte": fonte,
        "id_ons": id_ons,
        "nom_usina": f"Usina {id_ons}",
        "id_estado": estado,
        "id_subsistema": "NE",
        "din_instante": when,
        "val_geracaolimitada": 5.0 if limited else None,
        "val_geracaoreferencia": 30.0,
        "val_geracao": 30.0 - cut,
        "cod_razaorestricao": cause if limited else None,
        "cod_origemrestricao": "SIS" if limited else None,
    }


def _history(rows) -> pl.DataFrame:
    return derive_targets(pl.DataFrame(rows, schema_overrides=RAW_TYPES))


def _days(start: date, n: int, **kwargs) -> list[dict]:
    """Uma linha às 12h de cada dia; `cut` pode ser função do dia."""
    rows = []
    for i in range(n):
        day = start + timedelta(days=i)
        cut = kwargs.get("cut", 0.0)
        rows.append(
            _row(
                datetime.combine(day, datetime.min.time()) + timedelta(hours=12),
                **{**kwargs, "cut": cut(day) if callable(cut) else cut},
            )
        )
    return rows


def test_base_has_one_row_per_entity_day_slot_and_drops_indeterminate_volume():
    history = _history(
        [
            _row(datetime(2026, 8, 3, 12), cut=10.0),
            {**_row(datetime(2026, 8, 3, 12, 30), cut=10.0), "val_geracao": -1.0},
        ]
    )
    base = base_from_history(history)
    assert base.select("dia", "slot", "corte", "volume").rows() == [
        (date(2026, 8, 3), 24, 1.0, 10.0)
    ]


def test_release_map_uses_emission_at_20h_of_previous_day():
    frame = release_map([date(2026, 8, 26), date(2026, 8, 31), date(2026, 9, 8)], CAL)
    rows = frame.select("dia", "ultimo_dia", "idade", "feriado").rows()
    assert rows == [
        (date(2026, 8, 26), date(2026, 8, 24), 2, 0),
        (date(2026, 8, 31), date(2026, 8, 27), 4, 0),
        # 08/09: emitido em 07/09 (feriado), conhece até quinta 03/09.
        (date(2026, 9, 8), date(2026, 9, 3), 5, 0),
    ]
    assert release_map([date(2026, 9, 7)], CAL)["feriado"].to_list() == [1]


def test_features_only_see_days_up_to_the_last_released_day():
    target = date(2026, 8, 26)  # último dia liberado: 24/08
    rows = _days(date(2026, 7, 1), 50, cut=lambda d: 10.0 if d.day % 2 else 0.0)
    base = base_from_history(_history(rows))
    mapping = release_map([target], CAL)
    before = build_features(base, mapping)
    # Mudar os dias posteriores a L (25/08 em diante) não pode mudar nada.
    changed = [
        {**r, "val_geracao": 0.0, "val_geracaolimitada": 1.0, "cod_razaorestricao": "CNF"}
        if r["din_instante"].date() > date(2026, 8, 24)
        else r
        for r in rows
    ]
    after = build_features(base_from_history(_history(changed)), mapping)
    assert before.select(FEATURES).equals(after.select(FEATURES))


def test_slot_history_counts_the_28_days_ending_at_the_last_released_day():
    # Corte em todos os dias até 10/08, sem corte de 11/08 em diante.
    rows = _days(date(2026, 7, 1), 55, cut=lambda d: 10.0 if d <= date(2026, 8, 10) else 0.0)
    features = build_features(
        base_from_history(_history(rows)), release_map([date(2026, 8, 26)], CAL)
    )
    row = features.filter(pl.col("slot") == 24).row(0, named=True)
    # Janela (27/07, 24/08]: 28 dias, dos quais 28/07–10/08 (14) com corte.
    assert row["hist_28d"] == pytest.approx(14 / 28)
    assert row["ultimo_slot"] == 0.0
    assert row["idade"] == 2
    assert row["vol_hist_28d"] == pytest.approx(14 * 10.0 / 28)


def test_state_features_aggregate_plants_of_the_same_source_and_state():
    rows = [
        _row(datetime(2026, 8, 24, 12), id_ons="A", cut=10.0),
        _row(datetime(2026, 8, 24, 12), id_ons="B", cut=0.0),
        _row(datetime(2026, 8, 24, 12), id_ons="C", estado="RN", cut=10.0),
        _row(datetime(2026, 8, 24, 12), id_ons="D", fonte="fotovoltaica", cut=0.0),
    ]
    features = build_features(
        base_from_history(_history(rows)), release_map([date(2026, 8, 26)], CAL)
    )
    level = dict(features.select("id_ons", "estado_nivel_ultimo").rows())
    assert level == {"A": 0.5, "B": 0.5, "C": 1.0, "D": 0.0}


def test_grid_covers_48_slots_for_every_known_entity_and_target_day():
    base = base_from_history(_history([_row(datetime(2026, 8, 24, 12))]))
    features = build_features(base, release_map([date(2026, 8, 26), date(2026, 8, 27)], CAL))
    assert features.height == 2 * 48
    assert features.select(pl.struct("dia", "slot").is_duplicated().any()).item() is False


def test_entities_unseen_until_the_last_released_day_are_not_predicted():
    base = base_from_history(_history([_row(datetime(2026, 8, 25, 12), id_ons="NOVA")]))
    features = build_features(base, release_map([date(2026, 8, 26)], CAL))
    assert features.height == 0


def test_base_from_raw_parquet_via_load_history(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    frame = pl.DataFrame(
        [_row(datetime(2026, 8, 24, 12), cut=10.0)], schema_overrides=RAW_TYPES
    ).with_columns(pl.col("din_instante").cast(pl.Datetime("ns")))
    frame.write_parquet(raw / "constrained_off_eolica_tm.parquet")
    history = load_history(
        tmp_path, datetime(2026, 8, 1), datetime(2026, 9, 1), sources=("eolica",)
    )
    assert base_from_history(history).height == 1


def test_last_available_value_is_the_last_half_hour_of_the_last_released_day():
    rows = [
        _row(datetime(2026, 8, 24, 12), cut=10.0),
        _row(datetime(2026, 8, 24, 23, 30), cut=4.0),
        _row(datetime(2026, 8, 25, 23, 30), cut=0.0),  # ainda não liberado
    ]
    features = build_features(
        base_from_history(_history(rows)), release_map([date(2026, 8, 26)], CAL)
    )
    assert features["ultimo_valor_corte"].unique().to_list() == [1.0]
    assert features["ultimo_valor_volume"].unique().to_list() == [4.0]
