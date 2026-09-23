import json
from datetime import date, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from curtamap.experimental.dataset_verification import verify_dataset
from curtamap.experimental.temporal import AvailabilityScenario, BusinessCalendar

CALENDAR = BusinessCalendar(frozenset(), "synthetic")


def features(t0: datetime) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "fonte": ["eolica"] * 48,
            "id_ons": ["A"] * 48,
            "t0": [t0] * 48,
            "tau": [t0 + timedelta(minutes=30 * h) for h in range(48)],
            "horizon": list(range(1, 49)),
            "history_age_hours": [48.0] * 48,
            "target_observed": [True] * 48,
            "target_available_at": [t0 + timedelta(days=4)] * 48,
            "eligible_history": [True] * 48,
            "true_volume_valid": [True] * 48,
            "true_cause": ["REL", "CNF", "ENE"] * 16,
        }
    )


def baselines(frame: pl.DataFrame) -> pl.DataFrame:
    return pl.concat(
        [
            frame.select("fonte", "id_ons", "t0", "tau", "horizon").with_columns(
                pl.lit(name).alias("baseline_id"),
                pl.lit("entity").alias("fallback_level"),
                pl.lit(0.5).alias("prob_positive"),
                pl.lit(1.0).alias("volume_expected"),
            )
            for name in ("ultimo", "ontem", "recente", "frequencia")
        ]
    )


def write_day(root: Path, frame: pl.DataFrame, base=None, day=None) -> Path:
    path = root / f"date={day or frame['t0'][0].date()}"
    path.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(path / "features.parquet")
    (baselines(frame) if base is None else base).write_parquet(path / "baselines.parquet")
    return path


def verify(tmp_path, root, start, end, *, scenario=None, observed=None):
    scenario = scenario or AvailabilityScenario.main()
    observed = observed or start
    target = tmp_path / "targets.parquet"
    pl.DataFrame(
        {
            "fonte": ["eolica"],
            "din_instante": [observed],
            "disponivel_em": [scenario.release_for(observed.date(), CALENDAR)],
        }
    ).write_parquet(target)
    return verify_dataset(
        root,
        start,
        end,
        tmp_path / "report.json",
        targets_pattern=str(target),
        calendar=CALENDAR,
        scenario=scenario,
        source="eolica",
    )


def test_known_empty_day_and_exact_aggregates_without_touching_data(tmp_path):
    root = tmp_path / "dataset com espaços"
    first = features(datetime(2023, 10, 2, 23, 30))
    second = features(datetime(2023, 10, 3))
    invalid = datetime(2023, 10, 3)
    for frame in (first, second):
        write_day(root, frame.with_columns((pl.col("tau") != invalid).alias("true_volume_valid")))
    before = {p: p.read_bytes() for p in root.rglob("*.parquet")}
    report = verify(tmp_path, root, datetime(2023, 10, 1), datetime(2023, 10, 4))
    assert report["all_checks_pass"]
    assert report["expected_empty_days"] == ["2023-10-01"]
    assert report["features"]["rows"] == 96
    assert report["baselines"]["rows"] == 384
    assert report["features"]["causes"] == ["CNF", "ENE", "REL"]
    assert len(report["baselines"]["baseline_ids"]) == 4
    assert report["emissions"]["emissions"] == 2
    assert report["indeterminate_distinct_targets"] == 1
    assert report["features"]["indeterminate_volume_rows"] == 2
    assert report["indeterminate_target_months"] == [{"month": "2023-10", "len": 1}]
    assert before == {p: p.read_bytes() for p in before}
    events = [
        json.loads(line) for line in (tmp_path / "report.progress.jsonl").read_text().splitlines()
    ]
    assert [e["event"] for e in events].count("partition_completed") == 2


def test_delayed_release_does_not_excuse_missing_day_after_population_is_known(tmp_path):
    root = tmp_path / "dataset"
    write_day(root, features(datetime(2023, 10, 4)))
    report = verify(
        tmp_path,
        root,
        datetime(2023, 10, 1),
        datetime(2023, 10, 5),
        scenario=AvailabilityScenario.delayed_24h(),
    )
    assert report["expected_empty_days"] == ["2023-10-01", "2023-10-02"]
    assert report["unexpected_missing_days"] == ["2023-10-03"]
    assert not report["checks"]["all_partitions_present"]


def test_reserved_tau_is_counted_but_excluded_by_actual_validation_filter(tmp_path):
    frame = pl.concat([features(datetime(2026, 4, 30)), features(datetime(2026, 4, 30, 23, 30))])
    root = tmp_path / "dataset"
    write_day(root, frame)
    report = verify(
        tmp_path,
        root,
        datetime(2026, 4, 30),
        datetime(2026, 5, 1),
        observed=datetime(2026, 4, 28),
    )
    assert report["all_checks_pass"]
    assert report["features"]["rows_tau_in_reserved"] == 47
    assert report["validation_boundaries"]["V4"]["rows"] == 48
    assert report["validation_boundaries"]["V4"]["rows_tau_in_reserved"] == 0


@pytest.mark.parametrize(
    "expression,check",
    [
        (pl.lit(49).alias("horizon"), "exactly_48_horizons"),
        (pl.lit(None, dtype=pl.String).alias("id_ons"), "required_values_present"),
        (pl.lit(0.0).alias("history_age_hours"), "no_history_after_t0"),
        (pl.lit(float("nan")).alias("history_age_hours"), "no_history_after_t0"),
        (pl.col("t0").alias("target_available_at"), "labels_released_after_t0"),
        (pl.lit("PAR").alias("true_cause"), "no_par"),
        ((pl.col("tau") + timedelta(minutes=1)).alias("tau"), "tau_contract"),
        (pl.lit("fotovoltaica").alias("fonte"), "source_matches"),
    ],
)
def test_rejects_corrupt_feature_contracts(tmp_path, expression, check):
    frame = features(datetime(2023, 10, 2, 20))
    root = tmp_path / "dataset"
    write_day(root, frame.with_columns(expression), baselines(frame))
    report = verify(tmp_path, root, datetime(2023, 10, 1), datetime(2023, 10, 3))
    assert not report["all_checks_pass"]
    assert not report["checks"][check]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), None])
def test_rejects_invalid_baseline_probabilities(tmp_path, value):
    frame = features(datetime(2023, 10, 2, 20))
    root = tmp_path / "dataset"
    write_day(
        root,
        frame,
        baselines(frame).with_columns(pl.lit(value, dtype=pl.Float64).alias("prob_positive")),
    )
    report = verify(tmp_path, root, datetime(2023, 10, 1), datetime(2023, 10, 3))
    assert not report["checks"]["baseline_values_finite"]


def test_duplicate_horizon_and_missing_baseline_key_are_not_hidden_by_total_rows(tmp_path):
    frame = features(datetime(2023, 10, 2, 20))
    frame = pl.concat([frame.head(47), frame.head(1)])
    base = baselines(features(datetime(2023, 10, 2, 20)))
    base = pl.concat([base.head(191), base.head(1)])
    root = tmp_path / "dataset"
    write_day(root, frame, base)
    report = verify(tmp_path, root, datetime(2023, 10, 1), datetime(2023, 10, 3))
    assert not report["checks"]["exactly_48_horizons"]
    assert not report["checks"]["baselines_4_per_request"]


def test_failure_keeps_completed_partition_and_does_not_overwrite_output(tmp_path):
    root = tmp_path / "dataset"
    write_day(root, features(datetime(2023, 10, 2, 20)))
    bad = write_day(root, features(datetime(2023, 10, 3)))
    (bad / "features.parquet").write_bytes(b"corrupt parquet")
    report = verify(tmp_path, root, datetime(2023, 10, 1), datetime(2023, 10, 4))
    assert report["status"] == "error"
    assert report["completed_partitions"] == 1
    assert not report["all_checks_pass"]
    events = (tmp_path / "report.progress.jsonl").read_text()
    assert '"partition_completed"' in events and '"error"' in events
    with pytest.raises(FileExistsError):
        verify(tmp_path, root, datetime(2023, 10, 1), datetime(2023, 10, 4))


def test_missing_file_wrong_partition_and_schema_drift_fail(tmp_path):
    root = tmp_path / "dataset"
    frame = features(datetime(2023, 10, 2, 20))
    write_day(root, frame)
    second = write_day(root, frame.with_columns(pl.lit(0).alias("extra")), day=date(2023, 10, 3))
    report = verify(tmp_path, root, datetime(2023, 10, 1), datetime(2023, 10, 4))
    assert not report["checks"]["single_feature_schema"]
    assert not report["checks"]["partition_dates_match"]
    (second / "baselines.parquet").unlink()
    other = tmp_path / "second"
    other.mkdir()
    report = verify(other, root, datetime(2023, 10, 1), datetime(2023, 10, 4))
    assert not report["checks"]["all_partitions_present"]


def test_reads_one_daily_file_at_a_time_and_rejects_forged_release(tmp_path, monkeypatch):
    root = tmp_path / "dataset"
    write_day(root, features(datetime(2023, 10, 2, 20)))
    write_day(root, features(datetime(2023, 10, 3)))
    original = pl.read_parquet
    paths = []

    def single_file(path, *args, **kwargs):
        assert isinstance(path, Path) and path.is_file()
        assert path.parent.name.startswith("date=")
        paths.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(pl, "read_parquet", single_file)
    targets = tmp_path / "targets.parquet"
    pl.DataFrame(
        {
            "fonte": ["eolica"],
            "din_instante": [datetime(2023, 10, 1)],
            "disponivel_em": [datetime(2023, 10, 3, 19, 30)],
        }
    ).write_parquet(targets)
    report = verify_dataset(
        root,
        datetime(2023, 10, 1),
        datetime(2023, 10, 4),
        tmp_path / "report.json",
        targets_pattern=str(targets),
        calendar=CALENDAR,
        scenario=AvailabilityScenario.main(),
        source="eolica",
    )
    assert len(paths) == 4
    assert not report["checks"]["first_release_matches_calendar"]


def test_calendar_holiday_explains_only_days_before_first_release(tmp_path):
    calendar = BusinessCalendar(frozenset({date(2023, 10, 2)}), "synthetic-holiday")
    root = tmp_path / "dataset"
    write_day(root, features(datetime(2023, 10, 3, 20)))
    targets = tmp_path / "targets.parquet"
    pl.DataFrame(
        {
            "fonte": ["eolica"],
            "din_instante": [datetime(2023, 10, 1)],
            "disponivel_em": [datetime(2023, 10, 3, 19, 30)],
        }
    ).write_parquet(targets)
    report = verify_dataset(
        root,
        datetime(2023, 10, 1),
        datetime(2023, 10, 4),
        tmp_path / "report.json",
        targets_pattern=str(targets),
        calendar=calendar,
        scenario=AvailabilityScenario.main(),
        source="eolica",
    )
    assert report["all_checks_pass"]
    assert report["expected_empty_days"] == ["2023-10-01", "2023-10-02"]


def test_empty_dataset_and_negative_baseline_do_not_pass(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    report = verify(tmp_path, root, datetime(2023, 10, 1), datetime(2023, 10, 3))
    assert not report["all_checks_pass"]
    assert not report["checks"]["all_partitions_present"]
    other = tmp_path / "negative"
    other.mkdir()
    frame = features(datetime(2023, 10, 2, 20))
    write_day(root, frame, baselines(frame).with_columns(pl.lit(-1.0).alias("volume_expected")))
    report = verify(other, root, datetime(2023, 10, 1), datetime(2023, 10, 3))
    assert not report["checks"]["baseline_values_finite"]
