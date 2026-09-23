from datetime import date, datetime, timedelta

import polars as pl
import pytest

from curtamap.experimental.sampling import day_offset, emission_mask, selected_positions


def day_frame(day: datetime, entities=("A", "B")) -> pl.DataFrame:
    rows = [
        {"id_ons": entity, "t0": day + timedelta(minutes=30 * slot), "horizon": horizon}
        for slot in range(48)
        for entity in entities
        for horizon in (1, 48)
    ]
    return pl.DataFrame(rows)


@pytest.mark.parametrize("slots", [4, 14, 16])
def test_positions_are_spread_evenly_across_the_day(slots):
    positions = sorted(selected_positions(slots))
    assert len(positions) == slots
    gaps = {b - a for a, b in zip(positions, [*positions[1:], positions[0] + 48], strict=True)}
    assert max(gaps) - min(gaps) <= 1


def test_offset_uses_stable_sha256_of_seed_and_date():
    assert day_offset(date(2025, 1, 1), 42) == day_offset(date(2025, 1, 1), 42)
    assert 0 <= day_offset(date(2025, 1, 1), 42) < 48
    offsets = {day_offset(date(2025, 1, 1) + timedelta(days=d), 42) for d in range(60)}
    assert len(offsets) > 10  # o deslocamento gira entre os dias


def test_mask_keeps_whole_emissions_with_all_entities_and_horizons():
    frame = pl.concat([day_frame(datetime(2025, 1, 1) + timedelta(days=d)) for d in range(3)])
    selected = frame.filter(emission_mask(4, 42))
    per_day = selected.group_by(pl.col("t0").dt.date().alias("day")).agg(pl.col("t0").n_unique())
    assert per_day["t0"].to_list() == [4, 4, 4]
    per_t0 = selected.group_by("t0").agg(pl.len(), pl.col("id_ons").n_unique())
    assert per_t0["len"].to_list() == [4] * 12
    assert per_t0["id_ons"].to_list() == [2] * 12


def test_mask_is_nested_by_date_only_and_full_rate_keeps_everything():
    frame = day_frame(datetime(2025, 3, 7))
    earlier = frame.filter(emission_mask(4, 42))
    again = pl.concat([day_frame(datetime(2024, 1, 1)), frame]).filter(emission_mask(4, 42))
    assert earlier["t0"].unique().sort().to_list() == (
        again.filter(pl.col("t0") >= datetime(2025, 3, 7))["t0"].unique().sort().to_list()
    )
    assert frame.filter(emission_mask(48, 42)).height == frame.height


def test_mask_depends_on_seed_and_rejects_invalid_slots():
    frame = pl.concat([day_frame(datetime(2025, 1, 1) + timedelta(days=d)) for d in range(10)])
    a = frame.filter(emission_mask(4, 42))["t0"].unique().sort().to_list()
    b = frame.filter(emission_mask(4, 17))["t0"].unique().sort().to_list()
    assert a != b
    for slots in (0, 49):
        with pytest.raises(ValueError):
            emission_mask(slots, 42)


def test_cli_reads_slots_per_source_and_requires_main_seed():
    import json
    from pathlib import Path

    from curtamap.experimental.cli import _training_slots

    config = json.loads(Path("configs/experimental/stage2b.example.json").read_text("utf-8"))
    assert _training_slots(config, "eolica")["corte_positivo"] == 4
    assert _training_slots(config, "fotovoltaica")["causa"] == 48
    assert (
        _training_slots({k: v for k, v in config.items() if k != "training_sampling"}, "eolica")
        is None
    )
    with pytest.raises(ValueError, match="semente"):
        _training_slots(config | {"seed": 17}, "eolica")


def test_mask_is_pushed_down_into_the_parquet_scan(tmp_path):
    """Sem pushdown a campanha materializa o refit inteiro antes de amostrar (V1 de 23/09)."""
    path = tmp_path / "features.parquet"
    day_frame(datetime(2025, 1, 1)).write_parquet(path)
    # Mesma cadeia da campanha: filtro de intervalo, máscara, filtro de tarefa e projeção.
    query = (
        pl.scan_parquet(path)
        .filter(pl.col("horizon") >= 1)
        .filter(emission_mask(4, 42))
        .filter(pl.col("id_ons").is_not_null())
        .select("horizon")
    )
    plan = query.explain()
    assert "FILTER" not in plan
    assert "SELECTION" in plan
    assert query.collect().height == 4 * 2 * 2
