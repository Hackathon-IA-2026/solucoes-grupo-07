"""Verificação somente leitura do contrato de um dataset de features/baselines da Etapa 2B.

Uso: uv run python check_dataset.py <dir round=development> <inicio ISO> <fim ISO> <saida.json>
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl

root = Path(sys.argv[1])
start = datetime.fromisoformat(sys.argv[2])
end = datetime.fromisoformat(sys.argv[3])
output = Path(sys.argv[4])
reserved_start = datetime(2026, 5, 1)

partitions = sorted(path for path in root.iterdir() if path.is_dir())
report: dict = {"dataset": str(root), "start": start.isoformat(), "end": end.isoformat()}
expected_days = (end.date() - start.date()).days
dates = [path.name.removeprefix("date=") for path in partitions]
report["partitions"] = len(partitions)
report["expected_days"] = expected_days
missing_files = [
    path.name
    for path in partitions
    if not (path / "features.parquet").exists() or not (path / "baselines.parquet").exists()
]
report["partitions_missing_files"] = missing_files
report["first_date"], report["last_date"] = (dates[0], dates[-1]) if dates else (None, None)
all_days = {(start.date() + timedelta(days=i)).isoformat() for i in range(expected_days)}
report["days_without_partition"] = sorted(all_days - set(dates))

for kind in ("features", "baselines"):
    schemas = {}
    for path in partitions:
        schema = pl.read_parquet_schema(path / f"{kind}.parquet")
        schemas.setdefault(json.dumps({k: str(v) for k, v in schema.items()}), []).append(path.name)
    report[f"{kind}_distinct_schemas"] = len(schemas)
    if len(schemas) > 1:
        report[f"{kind}_schema_groups"] = {k: v[:5] for k, v in schemas.items()}

features = pl.scan_parquet(str(root / "date=*" / "features.parquet"))
baselines = pl.scan_parquet(str(root / "date=*" / "baselines.parquet"))

summary = features.select(
    pl.len().alias("rows"),
    pl.col("t0").min().alias("t0_min"),
    pl.col("t0").max().alias("t0_max"),
    pl.col("tau").max().alias("tau_max"),
    pl.col("id_ons").n_unique().alias("entities"),
    pl.col("fonte").n_unique().alias("sources"),
    (pl.col("horizon") < 1).sum().alias("horizon_below_1"),
    (pl.col("horizon") > 48).sum().alias("horizon_above_48"),
    (pl.col("tau") != pl.col("t0") + pl.duration(minutes=(pl.col("horizon") - 1) * 30))
    .sum()
    .alias("tau_mismatch"),
    (pl.col("t0").dt.minute().is_in([0, 30]).not_() | (pl.col("t0").dt.second() != 0))
    .sum()
    .alias("t0_off_grid"),
    (pl.col("history_age_hours") < 0.5).sum().alias("history_age_below_30min"),
    (pl.col("target_observed") & (pl.col("target_available_at") <= pl.col("t0")))
    .sum()
    .alias("labels_available_at_or_before_t0"),
    pl.col("eligible_history").sum().alias("eligible_rows"),
    pl.col("target_observed").not_().sum().alias("target_not_observed"),
    (pl.col("target_observed") & pl.col("true_volume_valid").not_())
    .sum()
    .alias("indeterminate_volume_rows"),
    (pl.col("true_cause") == "PAR").sum().alias("par_rows"),
    pl.col("true_cause").drop_nulls().unique().sort().alias("causes"),
    (pl.col("tau") >= reserved_start).sum().alias("rows_tau_in_reserved"),
    (pl.col("t0") >= reserved_start).sum().alias("rows_t0_in_reserved"),
).collect()
row = summary.row(0, named=True)
row["causes"] = list(row["causes"])
report["features"] = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in row.items()}

per_emission = (
    features.group_by("fonte", "id_ons", "t0")
    .agg(pl.len().alias("n"), pl.col("horizon").n_unique().alias("distinct"))
    .select(
        pl.len().alias("emissions"),
        (pl.col("n") != 48).sum().alias("emissions_not_48_rows"),
        (pl.col("distinct") != 48).sum().alias("emissions_not_48_horizons"),
    )
    .collect()
)
report["emissions"] = per_emission.row(0, named=True)

indeterminate = (
    features.filter(pl.col("target_observed") & pl.col("true_volume_valid").not_())
    .select("fonte", "id_ons", "tau")
    .unique()
    .collect()
)
report["indeterminate_distinct_targets"] = indeterminate.height
report["indeterminate_target_months"] = (
    indeterminate.group_by(pl.col("tau").dt.strftime("%Y-%m").alias("month"))
    .len()
    .sort("month")
    .to_dicts()
)

base = baselines.select(
    pl.len().alias("rows"),
    pl.col("baseline_id").unique().sort().alias("baseline_ids"),
    pl.col("fallback_level").null_count().alias("fallback_level_nulls"),
    (pl.col("prob_positive").is_nan() | pl.col("prob_positive").is_infinite())
    .sum()
    .alias("prob_positive_nonfinite"),
    (pl.col("volume_expected") < 0).sum().alias("volume_expected_negative"),
).collect()
brow = base.row(0, named=True)
brow["baseline_ids"] = list(brow["baseline_ids"])
report["baselines"] = brow
report["baselines_rows_equal_4x_features"] = brow["rows"] == 4 * report["features"]["rows"]
report["fallback_levels"] = (
    baselines.group_by("baseline_id", "fallback_level").len().sort("baseline_id", "fallback_level")
    .collect()
    .to_dicts()
)

checks = {
    "all_partitions_present": not report["days_without_partition"] and not missing_files,
    "single_feature_schema": report["features_distinct_schemas"] == 1,
    "single_baseline_schema": report["baselines_distinct_schemas"] == 1,
    "t0_within_range": report["features"]["t0_min"] >= start.isoformat()
    and report["features"]["t0_max"] < end.isoformat(),
    "no_t0_in_reserved": report["features"]["rows_t0_in_reserved"] == 0,
    "exactly_48_horizons": report["emissions"]["emissions_not_48_rows"] == 0
    and report["emissions"]["emissions_not_48_horizons"] == 0,
    "tau_contract": report["features"]["tau_mismatch"] == 0
    and report["features"]["t0_off_grid"] == 0,
    "no_history_after_t0": report["features"]["history_age_below_30min"] == 0,
    "labels_released_after_t0": report["features"]["labels_available_at_or_before_t0"] == 0,
    "no_par": report["features"]["par_rows"] == 0,
    "baselines_4_per_request": report["baselines_rows_equal_4x_features"],
    "baseline_values_finite": report["baselines"]["prob_positive_nonfinite"] == 0
    and report["baselines"]["volume_expected_negative"] == 0,
}
report["checks"] = checks
report["all_checks_pass"] = all(checks.values())
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
print(json.dumps({"all_checks_pass": report["all_checks_pass"], "checks": checks}, indent=2))
