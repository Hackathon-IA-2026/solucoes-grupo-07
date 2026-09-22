from datetime import date, datetime, timedelta

import polars as pl

from curtamap.experimental.data import (
    add_release_times,
    aggregate_asof,
    history_eligibility,
    task_masks,
)
from curtamap.experimental.temporal import AvailabilityScenario, BusinessCalendar

CALENDAR = BusinessCalendar(frozenset({date(2025, 1, 1)}), "synthetic-test")


def test_labels_and_future_features_are_unavailable_before_release() -> None:
    rows = pl.DataFrame(
        {
            "fonte": ["eolica", "eolica"],
            "id_ons": ["A", "A"],
            "din_instante": [datetime(2025, 1, 2, 0), datetime(2025, 1, 3, 0)],
            "volume_mwmed": [1.0, 2.0],
        }
    )
    released = add_release_times(rows, AvailabilityScenario.main(), CALENDAR)

    before = datetime(2025, 1, 3, 19, 29)
    at_release = datetime(2025, 1, 3, 19, 30)
    assert released.filter(pl.col("disponivel_em") <= before).is_empty()
    assert released.filter(pl.col("disponivel_em") <= at_release)["volume_mwmed"].to_list() == [1.0]
    assert released.filter(pl.col("disponivel_em") <= at_release)["volume_mwmed"].to_list() != [2.0]


def test_delayed_scenario_recomputes_release_instead_of_reusing_main_mask() -> None:
    rows = pl.DataFrame(
        {
            "fonte": ["eolica"],
            "id_ons": ["A"],
            "din_instante": [datetime(2025, 1, 2, 0)],
        }
    )
    main = add_release_times(rows, AvailabilityScenario.main(), CALENDAR)
    delayed = add_release_times(rows, AvailabilityScenario.delayed_24h(), CALENDAR)
    assert delayed["disponivel_em"][0] - main["disponivel_em"][0] == timedelta(hours=24)


def test_eligibility_requires_28_days_extent_and_80_percent_coverage() -> None:
    end = datetime(2025, 2, 1)
    full_grid = [end - timedelta(minutes=30 * i) for i in range(1, 1345)]
    rows = pl.DataFrame(
        {
            "fonte": ["eolica"] * 1344,
            "id_ons": ["A"] * 1344,
            "din_instante": full_grid,
        }
    )

    coverage_1075 = pl.concat([rows.head(1074), rows.tail(1)])
    coverage_1076 = pl.concat([rows.head(1075), rows.tail(1)])
    assert history_eligibility(coverage_1075, end).row(0, named=True)["eligible"] is False
    assert history_eligibility(coverage_1076, end).row(0, named=True)["eligible"] is True
    too_short = rows.filter(pl.col("din_instante") >= end - timedelta(days=27))
    assert history_eligibility(too_short, end).row(0, named=True)["eligible"] is False


def test_new_entity_is_not_known_before_first_released_record() -> None:
    rows = pl.DataFrame(
        {
            "fonte": ["eolica"],
            "id_ons": ["NOVA"],
            "din_instante": [datetime(2025, 1, 2, 0)],
        }
    )
    released = add_release_times(rows, AvailabilityScenario.main(), CALENDAR)
    assert released.filter(pl.col("disponivel_em") <= datetime(2025, 1, 3, 19, 29)).is_empty()
    assert released.filter(pl.col("disponivel_em") <= datetime(2025, 1, 3, 19, 30)).height == 1


def test_missing_row_valid_zero_and_indeterminate_target_remain_distinct() -> None:
    frame = pl.DataFrame(
        {
            "restricao_registrada": [False, True, True],
            "corte_positivo": [False, False, None],
            "volume_mwmed": [0.0, 0.0, None],
            "volume_valido": [True, True, False],
            "causa": [None, "ENE", "REL"],
        }
    )
    masks = task_masks(frame)
    assert masks["occurrence_positive"].to_list() == [True, True, False]
    assert masks["occurrence_restriction"].to_list() == [True, True, True]
    assert masks["volume"].to_list() == [True, True, False]
    assert masks["cause"].to_list() == [False, True, True]


def test_all_21_indeterminate_wind_volumes_are_excluded_only_from_positive_and_volume() -> None:
    frame = pl.DataFrame(
        {
            "restricao_registrada": [True] * 21,
            "corte_positivo": [None] * 21,
            "volume_mwmed": [None] * 21,
            "volume_valido": [False] * 21,
            "causa": ["REL"] * 21,
        }
    )
    masks = task_masks(frame)
    assert masks["occurrence_positive"].sum() == 0
    assert masks["volume"].sum() == 0
    assert masks["occurrence_restriction"].sum() == 21
    assert masks["cause"].sum() == 21


def test_cause_excludes_unknown_and_never_creates_par() -> None:
    frame = pl.DataFrame(
        {
            "restricao_registrada": [True] * 4,
            "corte_positivo": [True] * 4,
            "volume_mwmed": [1.0] * 4,
            "volume_valido": [True] * 4,
            "causa": ["REL", "CNF", "ENE", "DESCONHECIDA"],
        }
    )
    masks = task_masks(frame)
    assert frame.filter(masks["cause"])["causa"].to_list() == ["REL", "CNF", "ENE"]


def test_regional_aggregate_uses_only_rows_released_asof() -> None:
    rows = pl.DataFrame(
        {
            "fonte": ["eolica", "eolica", "eolica"],
            "id_ons": ["A", "B", "C"],
            "id_estado": ["RJ", "RJ", "RJ"],
            "din_instante": [
                datetime(2025, 1, 2, 0),
                datetime(2025, 1, 2, 0),
                datetime(2025, 1, 3, 0),
            ],
            "corte_positivo": [True, False, True],
            "volume_mwmed": [10.0, 0.0, 999.0],
            "volume_valido": [True, True, True],
        }
    )
    rows = add_release_times(rows, AvailabilityScenario.main(), CALENDAR)
    result = aggregate_asof(rows, datetime(2025, 1, 3, 19, 30), ["fonte", "id_estado"])
    assert result.row(0, named=True) == {
        "fonte": "eolica",
        "id_estado": "RJ",
        "observations": 2,
        "entities": 2,
        "positive_frequency": 0.5,
        "mean_volume": 5.0,
    }
