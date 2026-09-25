"""Perfil do custo por t0 do código vetorizado (somente leitura)."""

import cProfile
import pstats
import sys
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl

from curtamap.experimental.baselines import generate_baselines
from curtamap.experimental.features import build_feature_batch

cache = Path(sys.argv[1])
day = datetime.fromisoformat(sys.argv[2])
scan = pl.scan_parquet(str(cache / "source=eolica" / "year=*" / "month=*" / "*.parquet"))
window = scan.filter(
    (pl.col("din_instante") >= day - timedelta(days=35))
    & (pl.col("din_instante") < day + timedelta(days=2))
).collect()


def run() -> None:
    for step in range(8):
        t0 = day + timedelta(hours=3 * step)
        features = build_feature_batch(window, t0)
        generate_baselines(
            window, features.select("fonte", "id_ons", "id_estado", "t0", "tau", "horizon")
        )


profiler = cProfile.Profile()
profiler.enable()
run()
profiler.disable()
pstats.Stats(profiler).sort_stats("cumulative").print_stats(25)
