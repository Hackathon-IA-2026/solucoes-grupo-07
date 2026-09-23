import json
from datetime import datetime, timedelta

import polars as pl
import pytest

from curtamap.experimental import campaign
from curtamap.experimental.campaign import TASK_IDS, _range, _task_filter, _validation_filter
from curtamap.experimental.population_measurement import measure_populations, population_query
from curtamap.experimental.temporal import AvailabilityScenario, BusinessCalendar, external_rounds
from curtamap.experimental.training import internal_boundaries

CALENDAR = BusinessCalendar(frozenset(), "synthetic")
ROUND = external_rounds()[0]
BOUNDARY = internal_boundaries(ROUND, AvailabilityScenario.main(), CALENDAR)


def features(t0):
    return pl.DataFrame(
        {
            "fonte": ["eolica"] * 8,
            "id_ons": list("AAAABBCC"),
            "t0": [t0] * 8,
            "horizon": [1, 2, 3, 4, 1, 2, 47, 48],
            "target_available_at": [t0 + timedelta(days=2)] * 8,
            "eligible_history": [True, True, False, None, True, True, True, True],
            "target_observed": [True, True, True, True, False, True, True, True],
            "true_positive": [True, False, True, False, True, None, True, True],
            "true_restriction": [True, True, True, False, True, True, False, True],
            "true_volume_valid": [True, True, True, False, True, None, False, True],
            "true_volume_mwmed": [2.0, 0.0, 5.0, None, 4.0, float("nan"), -1.0, 3.0],
            "true_cause": ["REL", "CNF", "ENE", "PAR", "REL", None, "ENE", "ENE"],
        }
    )


@pytest.mark.parametrize("segment", ["initial", "tuning", "refit", "calibration"])
@pytest.mark.parametrize("task", TASK_IDS)
def test_training_counts_match_real_filters_with_nulls_and_exact_boundaries(segment, task):
    first = datetime(2023, 10, 2)
    limits = {
        "initial": (first, BOUNDARY.tuning_start, BOUNDARY.tuning_start),
        "tuning": (BOUNDARY.tuning_start, BOUNDARY.calibration_start, BOUNDARY.calibration_start),
        "refit": (first, BOUNDARY.calibration_start, BOUNDARY.calibration_start),
        "calibration": (BOUNDARY.calibration_start, BOUNDARY.cutoff, ROUND.start),
    }
    start, end, cutoff = limits[segment]
    frame = pl.concat(
        [
            features(start - timedelta(minutes=30)),
            features(start),
            features(end - timedelta(hours=24)),
            features(end - timedelta(hours=23, minutes=30)),
        ]
    ).with_columns(pl.lit(cutoff).alias("target_available_at"))
    late = features(start).with_columns(
        pl.lit(cutoff + timedelta(microseconds=1)).alias("target_available_at")
    )
    frame = pl.concat([frame, late]).lazy()
    actual = (
        population_query(frame, ROUND, BOUNDARY, first, segment, task).collect().row(0, named=True)
    )
    if segment == "calibration" and task in {"volume_condicional", "causa"}:
        assert actual["used"] is False
        assert actual["rows"] is None
    else:
        expected = _range(frame, start, end, label_cutoff=cutoff).filter(_task_filter(task))
        assert actual["rows"] == expected.select(pl.len()).collect().item()
        assert actual["rows"] > 0


@pytest.mark.parametrize("task", TASK_IDS)
def test_validation_is_open_panel_and_uses_metric_population(task, monkeypatch):
    frame = features(ROUND.start).lazy()
    actual = (
        population_query(frame, ROUND, BOUNDARY, datetime(2023, 1, 1), "validation", task)
        .collect()
        .row(0, named=True)
    )
    assert actual["prediction_rows"] == 8
    expected = {"corte_positivo": 7, "restricao_registrada": 8, "volume_condicional": 6, "causa": 6}
    assert actual["rows"] == expected[task]
    monkeypatch.setattr(campaign, "_slice_frames", lambda frame: [("global", frame)])
    predicted = frame.collect().with_columns(
        pl.lit("REL" if task == "causa" else 0.4).alias("prediction")
    )
    metrics = campaign._metrics_for_prediction(predicted, task, 0.5)[0]["metrics"]
    assert actual["rows"] == metrics["support"]
    if task == "volume_condicional":
        assert actual["positive_volume_rows"] == 4
        assert actual["eligible_rows"] == 5


def write_day(root, frame):
    path = root / f"date={frame['t0'][0].date()}" / "features.parquet"
    path.parent.mkdir(parents=True)
    frame.write_parquet(path)
    return path


def test_daily_aggregate_output_is_durable_exclusive_and_read_only(tmp_path):
    root = tmp_path / "dataset"
    paths = [write_day(root, features(ROUND.start + timedelta(days=day))) for day in (0, 1)]
    before = {p: p.read_bytes() for p in paths}
    output = tmp_path / "counts.json"
    result = measure_populations(
        root,
        ROUND.start,
        ROUND.start + timedelta(days=2),
        output,
        calendar=CALENDAR,
        source="eolica",
        expected_partitions=2,
    )
    assert len(result["populations"]) == 80
    cells = {(c["round"], c["segment"], c["task"]): c for c in result["populations"]}
    assert cells[("V1", "validation", "volume_condicional")]["rows"] == 12
    assert cells[("V4", "calibration", "causa")]["rows"] is None
    assert result["dataset_rows"] == 16
    assert sum(x["rows"] for x in result["distributions"]["entity"]) == 16
    assert sum(x["rows"] for x in result["distributions"]["horizon"]) == 16
    assert len(result["distributions"]["day"]) == 2
    assert json.loads(output.read_text())["status"] == "complete"
    events = [
        json.loads(line) for line in output.with_suffix(".progress.jsonl").read_text().splitlines()
    ]
    assert [e["event"] for e in events].count("partition_completed") == 2
    assert before == {p: p.read_bytes() for p in paths}
    with pytest.raises(FileExistsError):
        measure_populations(
            root,
            ROUND.start,
            ROUND.start + timedelta(days=2),
            output,
            calendar=CALENDAR,
            source="eolica",
        )


def test_validation_endpoint_and_reserved_guard(tmp_path):
    frame = pl.concat(
        [features(ROUND.last_emission), features(ROUND.last_emission + timedelta(minutes=30))]
    ).lazy()
    actual = (
        population_query(
            frame, ROUND, BOUNDARY, datetime(2023, 1, 1), "validation", "corte_positivo"
        )
        .collect()
        .row(0, named=True)
    )
    assert (
        actual["prediction_rows"]
        == frame.filter(_validation_filter(ROUND)).select(pl.len()).collect().item()
        == 8
    )
    with pytest.raises(ValueError, match="reservado"):
        measure_populations(
            tmp_path / "not-read",
            datetime(2026, 4, 30),
            datetime(2026, 5, 2),
            tmp_path / "forbidden.json",
            calendar=CALENDAR,
            source="eolica",
        )


def test_wrong_partition_date_fails_with_durable_event(tmp_path):
    root = tmp_path / "dataset"
    path = write_day(root, features(ROUND.start))
    features(ROUND.start + timedelta(days=1)).write_parquet(path)
    output = tmp_path / "failed.json"
    with pytest.raises(ValueError, match="partição"):
        measure_populations(
            root,
            ROUND.start,
            ROUND.start + timedelta(days=1),
            output,
            calendar=CALENDAR,
            source="eolica",
        )
    events = [
        json.loads(line) for line in output.with_suffix(".progress.jsonl").read_text().splitlines()
    ]
    assert events[-1]["event"] == "failed"


def test_missing_partitions_reject_expected_inventory_and_input_directory_output(tmp_path):
    root = tmp_path / "dataset"
    write_day(root, features(ROUND.start))
    with pytest.raises(ValueError, match="partições encontradas"):
        measure_populations(
            root,
            ROUND.start,
            ROUND.start + timedelta(days=2),
            tmp_path / "missing.json",
            calendar=CALENDAR,
            source="eolica",
            expected_partitions=2,
        )
    with pytest.raises(ValueError, match="fora do dataset"):
        measure_populations(
            root,
            ROUND.start,
            ROUND.start + timedelta(days=1),
            root / "counts.json",
            calendar=CALENDAR,
            source="eolica",
        )


def test_reserved_partition_is_not_opened_at_exclusive_end(tmp_path):
    root = tmp_path / "dataset"
    start = datetime(2026, 4, 30)
    write_day(root, features(start))
    reserved = root / "date=2026-05-01" / "features.parquet"
    reserved.parent.mkdir()
    reserved.write_text("não é parquet; ler este arquivo deve falhar")
    report = measure_populations(
        root,
        start,
        datetime(2026, 5, 1),
        tmp_path / "safe.json",
        calendar=CALENDAR,
        source="eolica",
        expected_partitions=1,
    )
    assert report["completed_partitions"] == 1
