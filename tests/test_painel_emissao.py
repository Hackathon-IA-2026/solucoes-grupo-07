from datetime import datetime, time, timedelta

import pytest

from curtamap.contracts import HORIZONS, RESERVED_TEST_START, STEP
from curtamap.painel.emissao import check_emission, emission_bounds, slots_for_day

START = datetime(2023, 10, 1)
END = datetime(2026, 8, 31, 23, 30)


def test_latest_emission_keeps_the_24h_horizon_before_the_reserved_test() -> None:
    _, latest = emission_bounds(START, END, history_days=92)

    assert latest + HORIZONS * STEP <= RESERVED_TEST_START
    assert latest == RESERVED_TEST_START - timedelta(days=1)


def test_latest_emission_follows_the_end_of_local_data() -> None:
    # Snapshot antigo: não há por que emitir depois do último dia com dados.
    _, latest = emission_bounds(START, datetime(2026, 4, 30, 23, 30), history_days=28)

    assert latest == datetime(2026, 5, 1)


def test_earliest_emission_leaves_the_full_history_window() -> None:
    earliest, _ = emission_bounds(START, END, history_days=92)

    assert earliest == START + timedelta(days=93)


def test_earliest_emission_rounds_a_partial_first_day_up() -> None:
    earliest, _ = emission_bounds(datetime(2023, 10, 1, 12), END, history_days=28)

    assert earliest == datetime(2023, 10, 2) + timedelta(days=29)


def test_no_possible_emission_is_an_error() -> None:
    with pytest.raises(ValueError, match="histórico insuficiente"):
        emission_bounds(datetime(2026, 8, 1), END, history_days=92)


def test_check_emission_accepts_the_bounds() -> None:
    bounds = emission_bounds(START, END, history_days=92)

    for t0 in bounds:
        assert check_emission(t0, bounds) == t0


@pytest.mark.parametrize(
    ("t0", "message"),
    [
        (datetime(2026, 8, 30, 10, 15), "grade de 30 minutos"),
        (datetime(2026, 8, 30, 10, 0, 1), "grade de 30 minutos"),
        (datetime(2026, 8, 31, 0, 30), "teste reservado"),
        (datetime(2026, 9, 2), "teste reservado"),
        (datetime(2023, 11, 1), "anterior"),
    ],
)
def test_check_emission_rejects_invalid_instants(t0: datetime, message: str) -> None:
    bounds = emission_bounds(START, END, history_days=92)

    with pytest.raises(ValueError, match=message):
        check_emission(t0, bounds)


def test_slots_cover_the_whole_day_inside_the_bounds() -> None:
    bounds = emission_bounds(START, END, history_days=92)

    slots = slots_for_day(datetime(2026, 7, 15).date(), bounds)

    assert len(slots) == 48
    assert slots[0] == time(0, 0)
    assert slots[-1] == time(23, 30)


def test_slots_stop_at_the_latest_emission() -> None:
    bounds = emission_bounds(START, END, history_days=92)

    assert slots_for_day(bounds[1].date(), bounds) == [time(0, 0)]


def test_slots_start_at_the_earliest_emission() -> None:
    bounds = (datetime(2024, 1, 2, 22, 0), datetime(2024, 6, 1))

    assert slots_for_day(datetime(2024, 1, 2).date(), bounds) == [
        time(22, 0),
        time(22, 30),
        time(23, 0),
        time(23, 30),
    ]
    assert slots_for_day(datetime(2024, 1, 1).date(), bounds) == []
