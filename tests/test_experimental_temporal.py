from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from curtamap.experimental.config import ExperimentalSettings
from curtamap.experimental.temporal import (
    AvailabilityScenario,
    BusinessCalendar,
    ReservedTestLocked,
    build_horizons,
    external_rounds,
    require_reserved_test_release,
)


def calendar() -> BusinessCalendar:
    return BusinessCalendar(
        non_business_days=frozenset({date(2025, 1, 1), date(2025, 4, 21)}),
        version="synthetic-test",
    )


def test_horizons_start_at_t0_and_cover_exactly_24_hours() -> None:
    t0 = datetime(2025, 1, 2, 10, 0)
    rows = build_horizons(t0)

    assert len(rows) == 48
    assert rows[0].horizon == 1
    assert rows[0].start == t0
    assert rows[0].end == t0 + timedelta(minutes=30)
    assert rows[-1].horizon == 48
    assert rows[-1].start == t0 + timedelta(hours=23, minutes=30)
    assert rows[-1].end == t0 + timedelta(hours=24)


@pytest.mark.parametrize("minute", [1, 29, 31, 45])
def test_t0_must_be_on_half_hour_grid(minute: int) -> None:
    with pytest.raises(ValueError, match="grade de 30 minutos"):
        build_horizons(datetime(2025, 1, 2, 10, minute))


def test_release_is_1930_of_next_business_day_across_weekend_and_monday() -> None:
    cal = calendar()
    main = AvailabilityScenario.main()

    friday = date(2025, 1, 3)
    assert main.release_for(friday, cal) == datetime(2025, 1, 6, 19, 30)
    assert main.release_for(date(2025, 1, 4), cal) == datetime(2025, 1, 6, 19, 30)
    assert main.release_for(date(2025, 1, 5), cal) == datetime(2025, 1, 6, 19, 30)


def test_release_skips_holiday_and_delayed_scenario_adds_24_clock_hours() -> None:
    cal = calendar()
    main = AvailabilityScenario.main()
    delayed = AvailabilityScenario.delayed_24h()

    observed = date(2025, 4, 20)  # domingo; segunda 21/4 também é feriado.
    assert main.release_for(observed, cal) == datetime(2025, 4, 22, 19, 30)
    assert delayed.release_for(observed, cal) == datetime(2025, 4, 23, 19, 30)


def test_cutoff_never_releases_a_day_before_1930() -> None:
    cal = calendar()
    main = AvailabilityScenario.main()

    assert main.last_fully_released_day(datetime(2025, 1, 6, 19, 29), cal) == date(2025, 1, 2)
    assert main.last_fully_released_day(datetime(2025, 1, 6, 19, 30), cal) == date(2025, 1, 5)


def test_external_rounds_exclude_last_47_emissions_and_mark_reserved_test() -> None:
    rounds = external_rounds()

    assert [r.round_id for r in rounds] == ["V1", "V2", "V3", "V4", "TESTE_RESERVADO"]
    assert rounds[0].start == datetime(2025, 1, 1)
    assert rounds[0].last_emission == datetime(2025, 4, 30)
    assert rounds[-1].reserved
    assert rounds[-1].start == datetime(2026, 5, 1)
    assert rounds[-1].end == datetime(2026, 9, 1)


def test_reserved_real_test_is_blocked_without_frozen_decision_reference() -> None:
    with pytest.raises(ReservedTestLocked):
        require_reserved_test_release(real_data=True, allow_reserved_test=False, decision_ref=None)
    with pytest.raises(ReservedTestLocked):
        require_reserved_test_release(real_data=True, allow_reserved_test=True, decision_ref="")

    require_reserved_test_release(
        real_data=True,
        allow_reserved_test=True,
        decision_ref="decisao-2c-congelada",
    )
    require_reserved_test_release(real_data=False, allow_reserved_test=False, decision_ref=None)


def test_external_paths_accept_absolute_paths_with_spaces(tmp_path: Path) -> None:
    root = tmp_path / "disco externo"
    settings = ExperimentalSettings(
        _env_file=None,
        data_dir=root / "dados",
        model_dir=root / "modelos",
        experiment_dir=root / "artefatos experimentais",
        cache_dir=root / "cache local",
        temp_dir=root / "temporarios duckdb",
    )

    assert settings.experiment_dir.is_absolute()
    settings.ensure_directories()
    assert all(
        path.is_dir()
        for path in (
            settings.data_dir,
            settings.model_dir,
            settings.experiment_dir,
            settings.cache_dir,
            settings.temp_dir,
        )
    )
