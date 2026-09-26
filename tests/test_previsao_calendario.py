from datetime import date, datetime

import pytest

from curtamap.forecasting import nightly_cutoff
from curtamap.previsao.calendario import (
    Calendar,
    emission_cutoff,
    load_calendar,
    release_cutoff,
)

CAL = load_calendar()


@pytest.mark.parametrize(
    ("t0", "expected"),
    [
        # Terça às 20h: segunda foi liberada às 19h30 de terça.
        (datetime(2026, 8, 25, 20), datetime(2026, 8, 25)),
        # Terça às 19h: segunda ainda não saiu; o último dia liberado é domingo.
        (datetime(2026, 8, 25, 19), datetime(2026, 8, 24)),
        # Exatamente às 19h30 o lote já está liberado.
        (datetime(2026, 8, 25, 19, 30), datetime(2026, 8, 25)),
        # Sábado e domingo às 20h: sexta só sai na segunda; o último dia é quinta.
        (datetime(2026, 8, 29, 20), datetime(2026, 8, 28)),
        (datetime(2026, 8, 30, 20), datetime(2026, 8, 28)),
        # Segunda às 20h: sexta, sábado e domingo saem juntos às 19h30.
        (datetime(2026, 8, 31, 20), datetime(2026, 8, 31)),
        # Segunda de manhã (15/06/2026): o último dia liberado ainda é quinta.
        (datetime(2026, 6, 15, 10), datetime(2026, 6, 12)),
    ],
)
def test_release_cutoff_follows_business_days(t0, expected):
    assert release_cutoff(t0, CAL) == expected


def test_holiday_delays_release_of_previous_days():
    # 07/09/2026 (segunda) é feriado nacional: a sexta 04/09 só sai na terça 08/09.
    assert release_cutoff(datetime(2026, 9, 7, 20), CAL) == datetime(2026, 9, 4)
    assert release_cutoff(datetime(2026, 9, 8, 20), CAL) == datetime(2026, 9, 8)


def test_rio_holidays_delay_release_but_are_not_low_load_days():
    # São Sebastião (20/01, municipal do Rio, sede do ONS) atrasa a publicação,
    # mas não derruba a carga do Nordeste.
    sao_sebastiao = date(2026, 1, 20)
    assert not CAL.is_business_day(sao_sebastiao)
    assert not CAL.is_national_holiday(sao_sebastiao)
    assert CAL.is_national_holiday(date(2026, 9, 7))


def test_partial_days_count_as_non_business_days():
    assert not CAL.is_business_day(date(2026, 12, 24))


def test_emission_cutoff_is_the_20h_release_state_of_the_previous_day():
    # Previsão para quarta 26/08: emitida terça 25/08 às 20h, conhece até segunda.
    assert emission_cutoff(date(2026, 8, 26), CAL) == datetime(2026, 8, 25)
    # Previsão para segunda 31/08: emitida domingo às 20h, conhece até quinta.
    assert emission_cutoff(date(2026, 8, 31), CAL) == datetime(2026, 8, 28)


def test_calendar_refuses_dates_outside_its_coverage():
    with pytest.raises(ValueError, match="cobertura"):
        release_cutoff(datetime(2027, 3, 1, 20), CAL)


def test_custom_calendar_without_holidays_matches_weekend_rule():
    plain = Calendar(frozenset(), frozenset(), date(2020, 1, 1), date(2030, 12, 31))
    assert release_cutoff(datetime(2026, 9, 7, 20), plain) == datetime(2026, 9, 7)


def test_nightly_cutoff_of_the_product_uses_the_holiday_calendar():
    assert nightly_cutoff(datetime(2026, 9, 7, 20)) == datetime(2026, 9, 4)
