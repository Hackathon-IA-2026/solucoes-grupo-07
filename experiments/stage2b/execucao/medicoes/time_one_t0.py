"""Cronometra o custo de UM t0 de features e de uma amostra de baselines (somente leitura)."""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter

import polars as pl

from curtamap.experimental.baselines import generate_baselines
from curtamap.experimental.features import build_feature_batch

cache = Path(sys.argv[1])
source = sys.argv[2]
t0 = datetime.fromisoformat(sys.argv[3])
sample_requests = int(sys.argv[4])

scan = pl.scan_parquet(str(cache / f"source={source}" / "year=*" / "month=*" / "*.parquet"))
window = scan.filter(
    (pl.col("din_instante") >= t0 - timedelta(days=35))
    & (pl.col("din_instante") < t0 + timedelta(days=2))
).collect()
result = {"source": source, "t0": t0.isoformat(), "window_rows": window.height}

started = perf_counter()
features = build_feature_batch(window, t0)
result["features_seconds_one_t0"] = perf_counter() - started
result["feature_rows_one_t0"] = features.height
result["entities"] = features["id_ons"].n_unique()

requests = features.select("fonte", "id_ons", "id_estado", "t0", "tau", "horizon")
subset = requests.head(sample_requests)
started = perf_counter()
generate_baselines(window, subset)
elapsed = perf_counter() - started
result["baseline_sample_requests"] = subset.height
result["baseline_seconds_sample"] = elapsed
result["baseline_seconds_per_request"] = elapsed / subset.height
result["baseline_seconds_one_t0_projected"] = elapsed / subset.height * requests.height
print(json.dumps(result, indent=2))
