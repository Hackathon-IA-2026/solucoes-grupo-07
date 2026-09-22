from datetime import datetime, timedelta
from itertools import product

import numpy as np
import polars as pl
import pytest
import reference_campaign_stage2b as oracle

from curtamap.experimental.campaign import _plan_chunks, _slice_frames, _task_filter
from curtamap.experimental.runner import TASKS, _task_frame

ORIGIN = datetime(2025, 1, 1)


def _t0(*hours: float) -> pl.LazyFrame:
    return pl.LazyFrame(
        {"t0": [ORIGIN + timedelta(hours=value) for value in hours], "row": range(len(hours))},
        schema={"t0": pl.Datetime("us"), "row": pl.Int64},
    )


def test_plan_chunks_follows_row_order_when_each_part_is_contiguous() -> None:
    frame = _t0(5, 0, 23.5, 30, 26, 80, 79)
    chunks = _plan_chunks(frame, ORIGIN, 1)
    assert [(chunk.start, chunk.end) for chunk in chunks] == [
        (ORIGIN, ORIGIN + timedelta(days=1)),
        (ORIGIN + timedelta(days=1), ORIGIN + timedelta(days=2)),
        (ORIGIN + timedelta(days=3), ORIGIN + timedelta(days=4)),
    ]
    rebuilt = pl.concat(frame.filter(chunk.expression()).collect() for chunk in chunks)
    assert rebuilt.equals(frame.collect())
    assert len(_plan_chunks(frame, ORIGIN, 7)) == 1


def test_plan_chunks_falls_back_to_single_part_when_order_interleaves_or_is_empty() -> None:
    interleaved = _t0(0, 30, 5)
    (single,) = _plan_chunks(interleaved, ORIGIN, 1)
    assert single.start is None and single.end is None
    assert interleaved.filter(single.expression()).collect().equals(interleaved.collect())
    (empty,) = _plan_chunks(_t0(), ORIGIN, 1)
    assert empty.start is None
    with pytest.raises(ValueError, match="positivo"):
        _plan_chunks(_t0(0), ORIGIN, 0)


def test_lazy_task_filter_selects_the_same_rows_as_task_frame_including_nulls() -> None:
    options = {
        "target_observed": (True, False, None),
        "true_positive": (True, False, None),
        "true_volume_valid": (True, False, None),
        "true_volume_mwmed": (5.0, 0.0, None),
        "true_restriction": (True, False, None),
        "true_cause": ("REL", "PAR", None),
    }
    rows = list(product(*options.values()))
    frame = pl.DataFrame(
        {name: [row[index] for row in rows] for index, name in enumerate(options)},
        schema={
            "target_observed": pl.Boolean,
            "true_positive": pl.Boolean,
            "true_volume_valid": pl.Boolean,
            "true_volume_mwmed": pl.Float64,
            "true_restriction": pl.Boolean,
            "true_cause": pl.String,
        },
    ).with_row_index("row")
    for task_id in TASKS:
        expected, target = _task_frame(frame, task_id)
        actual = frame.lazy().filter(_task_filter(task_id)).collect()
        assert not expected.is_empty(), task_id
        assert actual.equals(expected), task_id
        assert np.array_equal(actual[TASKS[task_id][1]].to_numpy(), target)


def test_slice_generator_matches_oracle_names_order_and_frames() -> None:
    size = 200
    rng = np.random.default_rng(3)
    frame = pl.DataFrame(
        {
            "horizon": rng.integers(1, 49, size),
            "eligible_history": rng.random(size) < 0.8,
            "entity_new": np.zeros(size, dtype=bool),  # recorte vazio é omitido
            "panel_fixed": rng.random(size) < 0.5,
            "tau_weekend_or_holiday": rng.random(size) < 0.3,
            "history_age_hours": pl.Series(rng.uniform(0, 150, size)).scatter(
                np.flatnonzero(rng.random(size) < 0.1), None
            ),
            "episode_start": rng.random(size) < 0.2,
            "post_episode_zero": rng.random(size) < 0.2,
            "volume_tail": rng.random(size) < 0.05,
        }
    )
    expected = oracle._slice_frames(frame)
    actual = list(_slice_frames(frame))
    assert [name for name, _ in actual] == [name for name, _ in expected]
    assert "entidade_nova" not in [name for name, _ in actual]
    for (_, left), (_, right) in zip(expected, actual, strict=True):
        assert right.equals(left)
    minimal = frame.select("horizon", "history_age_hours")
    assert [name for name, _ in _slice_frames(minimal)] == [
        name for name, _ in oracle._slice_frames(minimal)
    ]
