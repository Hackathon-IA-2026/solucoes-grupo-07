"""Contrato somente leitura: uma partição diária por vez, com evidência incremental."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl

from curtamap.experimental.calendar import load_calendar_manifest
from curtamap.experimental.campaign import _validation_filter
from curtamap.experimental.temporal import AvailabilityScenario, BusinessCalendar, external_rounds
from curtamap.experimental.training import internal_boundaries

RESERVED = datetime(2026, 5, 1)
KEY = ["fonte", "id_ons", "t0", "horizon"]
FEATURE_COLUMNS = [
    *KEY,
    "tau",
    "history_age_hours",
    "target_observed",
    "target_available_at",
    "eligible_history",
    "true_volume_valid",
    "true_cause",
]
BASE_COLUMNS = [*KEY, "tau", "baseline_id", "fallback_level", "prob_positive", "volume_expected"]


def _write_json(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, default=str)
        handle.flush()
        os.fsync(handle.fileno())


def _event(handle, event: str, **values) -> None:
    handle.write(json.dumps({"event": event, **values}, ensure_ascii=False, default=str) + "\n")
    handle.flush()
    os.fsync(handle.fileno())


def _count(expr: pl.Expr, name: str) -> pl.Expr:
    return expr.fill_null(False).cast(pl.UInt64).sum().alias(name)


def _feature_summary(frame: pl.DataFrame, day, source: str, start, end, first_release) -> dict:
    required = [*KEY, "tau", "history_age_hours", "target_observed", "eligible_history"]
    return frame.select(
        pl.len().alias("rows"),
        pl.col("t0").min().alias("t0_min"),
        pl.col("t0").max().alias("t0_max"),
        pl.col("tau").max().alias("tau_max"),
        _count(pl.any_horizontal(pl.col(c).is_null() for c in required), "required_null_rows"),
        _count(
            pl.col("target_observed")
            & (pl.col("target_available_at").is_null() | pl.col("true_volume_valid").is_null()),
            "observed_target_null_rows",
        ),
        _count(pl.col("horizon") < 1, "horizon_below_1"),
        _count(pl.col("horizon") > 48, "horizon_above_48"),
        _count(
            pl.col("tau") != pl.col("t0") + pl.duration(minutes=(pl.col("horizon") - 1) * 30),
            "tau_mismatch",
        ),
        _count(
            ~pl.col("t0").dt.minute().is_in([0, 30])
            | (pl.col("t0").dt.second() != 0)
            | (pl.col("t0").dt.microsecond() != 0),
            "t0_off_grid",
        ),
        _count(pl.col("t0").dt.date() != day, "wrong_partition_rows"),
        _count((pl.col("t0") < start) | (pl.col("t0") >= end), "out_of_range_rows"),
        _count(pl.col("t0") < first_release, "before_first_release_rows"),
        _count(pl.col("fonte") != source, "wrong_source_rows"),
        _count(
            (pl.col("history_age_hours") < 0.5) | ~pl.col("history_age_hours").is_finite(),
            "history_age_below_30min",
        ),
        _count(
            pl.col("target_observed") & (pl.col("target_available_at") <= pl.col("t0")),
            "labels_available_at_or_before_t0",
        ),
        _count(pl.col("eligible_history"), "eligible_rows"),
        _count(~pl.col("target_observed"), "target_not_observed"),
        _count(
            pl.col("target_observed") & ~pl.col("true_volume_valid"), "indeterminate_volume_rows"
        ),
        _count(pl.col("true_cause") == "PAR", "par_rows"),
        _count(pl.col("tau") >= RESERVED, "rows_tau_in_reserved"),
        _count(pl.col("t0") >= RESERVED, "rows_t0_in_reserved"),
    ).row(0, named=True)


def _inspect_partition(path, start, end, source, first_release, connection) -> dict:
    day = datetime.fromisoformat(path.name.removeprefix("date=")).date()
    schemas = {
        kind: {
            key: str(value)
            for key, value in pl.read_parquet_schema(path / f"{kind}.parquet").items()
        }
        for kind in ("features", "baselines")
    }
    frame = pl.read_parquet(
        path / "features.parquet", columns=FEATURE_COLUMNS, hive_partitioning=False
    )
    summary = _feature_summary(frame, day, source, start, end, first_release)
    emissions = (
        frame.group_by("fonte", "id_ons", "t0")
        .agg(pl.len().alias("n"), pl.col("horizon").n_unique().alias("distinct"))
        .select(
            pl.len().alias("emissions"),
            _count(pl.col("n") != 48, "emissions_not_48_rows"),
            _count(pl.col("distinct") != 48, "emissions_not_48_horizons"),
        )
        .row(0, named=True)
    )
    invalid = (
        frame.filter(pl.col("target_observed") & ~pl.col("true_volume_valid"))
        .select("fonte", "id_ons", "tau")
        .drop_nulls()
        .unique()
    )
    connection.executemany(
        "INSERT OR IGNORE INTO invalid_targets VALUES (?, ?, ?)",
        ((source_, entity, tau.isoformat()) for source_, entity, tau in invalid.iter_rows()),
    )
    connection.commit()
    rounds = {
        r.round_id: frame.lazy()
        .filter(_validation_filter(r))
        .select(pl.len().alias("rows"), _count(pl.col("tau") >= RESERVED, "rows_tau_in_reserved"))
        .collect()
        .row(0, named=True)
        for r in external_rounds()
        if not r.reserved
    }
    entities = frame.select("fonte", "id_ons").drop_nulls().unique().rows()
    causes = frame["true_cause"].drop_nulls().unique().sort().to_list()
    feature_keys = frame.select(*KEY, "tau")
    del frame, invalid
    base = pl.read_parquet(
        path / "baselines.parquet", columns=BASE_COLUMNS, hive_partitioning=False
    )
    base_summary = base.select(
        pl.len().alias("rows"),
        pl.col("fallback_level").null_count().alias("fallback_level_nulls"),
        _count(
            pl.col("prob_positive").is_null() | ~pl.col("prob_positive").is_finite(),
            "prob_positive_nonfinite",
        ),
        _count(pl.col("volume_expected") < 0, "volume_expected_negative"),
        _count(
            pl.col("volume_expected").is_null() | ~pl.col("volume_expected").is_finite(),
            "volume_expected_nonfinite",
        ),
        _count(
            pl.any_horizontal(pl.col(c).is_null() for c in [*KEY, "tau", "baseline_id"]),
            "required_null_rows",
        ),
    ).row(0, named=True)
    counts = base.group_by(*KEY, "tau").agg(
        pl.len().alias("n"), pl.col("baseline_id").n_unique().alias("distinct")
    )
    bad_counts = counts.filter((pl.col("n") != 4) | (pl.col("distinct") != 4)).height
    unique_keys = feature_keys.unique()
    bad_keys = (
        counts.join(unique_keys, on=[*KEY, "tau"], how="anti").height
        + unique_keys.join(counts, on=[*KEY, "tau"], how="anti").height
    )
    base_summary["requests_not_4_baselines"] = bad_counts + bad_keys
    return {
        "partition": path.name,
        "schemas": schemas,
        "features": summary,
        "emissions": emissions,
        "baselines": base_summary,
        "entities": entities,
        "causes": causes,
        "baseline_ids": base["baseline_id"].drop_nulls().unique().sort().to_list(),
        "fallback_levels": base.group_by("baseline_id", "fallback_level")
        .len()
        .sort("baseline_id", "fallback_level")
        .to_dicts(),
        "validation": rounds,
    }


def verify_dataset(
    root: Path,
    start: datetime,
    end: datetime,
    output: Path,
    *,
    targets_pattern: str,
    calendar: BusinessCalendar,
    scenario: AvailabilityScenario,
    source: str,
    dataset_commit: str | None = None,
    calendar_sha256: str | None = None,
    verification_commit: str | None = None,
) -> dict:
    """Persiste cada dia antes do próximo; SQLite deduplica alvos entre dias sem RAM global."""
    if (
        start >= end
        or start.minute
        or start.hour
        or start.second
        or start.microsecond
        or end.hour
        or end.minute
        or end.second
        or end.microsecond
    ):
        raise ValueError("intervalo deve conter dias inteiros, com início anterior ao fim")
    progress = output.with_suffix(".progress.jsonl")
    ledger = output.with_suffix(".targets.sqlite")
    for path in (output, progress, ledger):
        if path.exists():
            raise FileExistsError(f"evidência já existe: {path}")
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "dataset": str(root),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "source": source,
        "scenario": scenario.scenario_id,
        "dataset_commit": dataset_commit,
        "verification_commit": verification_commit,
        "calendar_version": calendar.version,
        "calendar_sha256": calendar_sha256,
        "status": "running",
        "all_checks_pass": False,
        "completed_partitions": 0,
        "progress": str(progress),
        "targets_ledger": str(ledger),
    }
    totals = {"features": Counter(), "baselines": Counter(), "emissions": Counter()}
    schemas = {"features": {}, "baselines": {}}
    entities, causes, baseline_ids = set(), set(), set()
    fallbacks = Counter()
    extremes = {}
    validation = {}
    for r in external_rounds():
        if r.reserved:
            continue
        boundary = internal_boundaries(r, AvailabilityScenario.main(), calendar)
        validation[r.round_id] = {
            "start": r.start.isoformat(),
            "end_exclusive": r.end.isoformat(),
            "last_emission": r.last_emission.isoformat(),
            "maximum_tau_by_contract": (r.end - timedelta(minutes=30)).isoformat(),
            "internal_tuning_start": boundary.tuning_start.isoformat(),
            "internal_calibration_start": boundary.calibration_start.isoformat(),
            "internal_cutoff": boundary.cutoff.isoformat(),
            "rows": 0,
            "rows_tau_in_reserved": 0,
        }
    report["validation_boundaries"] = validation
    with progress.open("x", encoding="utf-8") as log, sqlite3.connect(ledger) as connection:
        connection.execute("PRAGMA cache_size=-2048")
        connection.execute(
            "CREATE TABLE invalid_targets (source TEXT, entity TEXT, tau TEXT, "
            "PRIMARY KEY(source,entity,tau)) WITHOUT ROWID"
        )
        _event(log, "started", **report)
        try:
            origin = (
                pl.scan_parquet(targets_pattern, hive_partitioning=False)
                .filter(pl.col("fonte") == source)
                .select(
                    pl.col("din_instante").min().alias("first_observed"),
                    pl.col("disponivel_em").min().alias("first_cached_release"),
                )
                .collect(engine="streaming")
                .row(0, named=True)
            )
            if any(value is None for value in origin.values()):
                raise ValueError("cache sem observações da fonte solicitada")
            first_release = scenario.release_for(origin["first_observed"].date(), calendar)
            report["availability_evidence"] = {
                **origin,
                "first_release_by_calendar": first_release,
                "targets_pattern": targets_pattern,
            }
            days = [
                (start + timedelta(days=i)).date().isoformat() for i in range((end - start).days)
            ]
            empty = [
                day
                for day in days
                if datetime.fromisoformat(day) + timedelta(days=1) <= first_release
            ]
            partitions = sorted(p for p in root.iterdir() if p.is_dir())
            dates = [p.name.removeprefix("date=") for p in partitions]
            missing_files = [
                p.name
                for p in partitions
                if any(not (p / f"{kind}.parquet").exists() for kind in schemas)
            ]
            report.update(
                partitions=len(partitions),
                expected_days=len(days),
                first_date=dates[0] if dates else None,
                last_date=dates[-1] if dates else None,
                expected_empty_days=empty,
                days_without_partition=sorted(set(days) - set(dates)),
                unexpected_missing_days=sorted(set(days) - set(empty) - set(dates)),
                unexpected_partitions=sorted(set(dates) - set(days)),
                partitions_missing_files=missing_files,
            )
            _event(log, "inventory", **report)
            for path in partitions:
                if path.name in missing_files:
                    _event(log, "missing_files", partition=path.name)
                    continue
                _event(log, "partition_started", partition=path.name)
                part = _inspect_partition(path, start, end, source, first_release, connection)
                _event(log, "partition_completed", **part)
                for group in totals:
                    for key, value in part[group].items():
                        if key in ("t0_min", "t0_max", "tau_max"):
                            if value is not None:
                                combine = min if key.endswith("min") else max
                                extremes[key] = combine(extremes.get(key, value), value)
                        else:
                            totals[group][key] += value
                for kind in schemas:
                    signature = json.dumps(part["schemas"][kind], sort_keys=True)
                    schemas[kind].setdefault(signature, []).append(path.name)
                entities.update(tuple(pair) for pair in part["entities"])
                causes.update(part["causes"])
                baseline_ids.update(part["baseline_ids"])
                for item in part["fallback_levels"]:
                    fallbacks[(item["baseline_id"], item["fallback_level"])] += item["len"]
                for name, counts in part["validation"].items():
                    for key, count in counts.items():
                        validation[name][key] += count
                report["completed_partitions"] += 1
                if report["completed_partitions"] % 25 == 0:
                    print(
                        f"{report['completed_partitions']}/{len(partitions)} partições verificadas",
                        flush=True,
                    )
            f, b, e = (totals[key] for key in ("features", "baselines", "emissions"))
            report["checks"] = {
                "all_partitions_present": not report["unexpected_missing_days"]
                and not missing_files
                and not report["unexpected_partitions"],
                "single_feature_schema": len(schemas["features"]) == 1,
                "single_baseline_schema": len(schemas["baselines"]) == 1,
                "t0_within_range": f["rows"] > 0 and f["out_of_range_rows"] == 0,
                "no_t0_in_reserved": f["rows_t0_in_reserved"] == 0,
                "exactly_48_horizons": e["emissions_not_48_rows"]
                == e["emissions_not_48_horizons"]
                == f["horizon_below_1"]
                == f["horizon_above_48"]
                == 0,
                "tau_contract": f["tau_mismatch"] == f["t0_off_grid"] == 0,
                "no_history_after_t0": f["history_age_below_30min"] == 0,
                "labels_released_after_t0": f["labels_available_at_or_before_t0"] == 0,
                "no_par": f["par_rows"] == 0,
                "baselines_4_per_request": b["rows"] == 4 * f["rows"]
                and b["requests_not_4_baselines"] == 0
                and len(baseline_ids) == 4,
                "baseline_values_finite": b["prob_positive_nonfinite"]
                == b["volume_expected_negative"]
                == b["volume_expected_nonfinite"]
                == 0,
                "required_values_present": f["required_null_rows"]
                == f["observed_target_null_rows"]
                == b["required_null_rows"]
                == b["fallback_level_nulls"]
                == 0,
                "partition_dates_match": f["wrong_partition_rows"] == 0,
                "source_matches": f["wrong_source_rows"] == 0
                and {s for s, _ in entities} == {source},
                "first_release_matches_calendar": origin["first_cached_release"] == first_release,
                "no_emission_before_first_release": f["before_first_release_rows"] == 0,
                "validation_excludes_reserved_tau": all(
                    v["rows_tau_in_reserved"] == 0 for v in validation.values()
                ),
            }
            report["all_checks_pass"] = all(report["checks"].values())
            report["status"] = "passed" if report["all_checks_pass"] else "failed"
        except Exception as error:
            report.update(status="error", error=f"{type(error).__name__}: {error}")
            _event(log, "error", **report)
        report.update({key: dict(value) for key, value in totals.items()})
        report["features"].update(
            extremes,
            entities=len(entities),
            sources=len({s for s, _ in entities}),
            causes=sorted(causes),
        )
        report["baselines"]["baseline_ids"] = sorted(baseline_ids)
        report["baselines_rows_equal_4x_features"] = (
            totals["baselines"]["rows"] == 4 * totals["features"]["rows"]
        )
        report["fallback_levels"] = [
            {"baseline_id": key[0], "fallback_level": key[1], "len": count}
            for key, count in sorted(fallbacks.items(), key=lambda item: str(item[0]))
        ]
        for kind in schemas:
            report[f"{kind}_distinct_schemas"] = len(schemas[kind])
            report[f"{kind}_schema_groups"] = schemas[kind]
        report["indeterminate_distinct_targets"] = connection.execute(
            "SELECT count(*) FROM invalid_targets"
        ).fetchone()[0]
        report["indeterminate_target_months"] = [
            {"month": month, "len": count}
            for month, count in connection.execute(
                "SELECT substr(tau,1,7),count(*) FROM invalid_targets GROUP BY 1 ORDER BY 1"
            )
        ]
        _write_json(output, report)
        _event(
            log,
            "finished",
            status=report["status"],
            completed_partitions=report["completed_partitions"],
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("start", type=datetime.fromisoformat)
    parser.add_argument("end", type=datetime.fromisoformat)
    parser.add_argument("output", type=Path)
    parser.add_argument("--targets", required=True)
    parser.add_argument("--calendar", type=Path, required=True)
    parser.add_argument("--source", required=True, choices=["eolica", "fotovoltaica"])
    parser.add_argument(
        "--scenario", required=True, choices=["noturno_dia_util", "noturno_mais_24h"]
    )
    parser.add_argument("--dataset-commit", required=True)
    args = parser.parse_args()
    calendar = load_calendar_manifest(args.calendar)
    scenario = (
        AvailabilityScenario.main()
        if args.scenario == "noturno_dia_util"
        else AvailabilityScenario.delayed_24h()
    )
    report = verify_dataset(
        args.root,
        args.start,
        args.end,
        args.output,
        targets_pattern=args.targets,
        calendar=calendar.calendar,
        scenario=scenario,
        source=args.source,
        dataset_commit=args.dataset_commit,
        calendar_sha256=calendar.sha256,
        verification_commit=subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip(),
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "checks": report.get("checks"),
                "error": report.get("error"),
            },
            indent=2,
        )
    )
    return 0 if report["all_checks_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
