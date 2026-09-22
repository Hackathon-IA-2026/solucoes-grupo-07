from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import Any

import duckdb
import polars as pl

from curtamap.audit import literal
from curtamap.experimental.baselines import generate_baselines
from curtamap.experimental.data import add_release_times
from curtamap.experimental.features import build_feature_batch
from curtamap.experimental.resources import peak_rss_bytes
from curtamap.experimental.temporal import AvailabilityScenario, BusinessCalendar
from curtamap.targets import target_sql


def _sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def prepare_target_partitions(
    raw_path: Path,
    output_dir: Path,
    scenario: AvailabilityScenario,
    calendar: BusinessCalendar,
    *,
    temp_dir: Path,
    memory_limit: str,
    threads: int,
) -> dict[str, Any]:
    """Deriva alvos mensalmente; nunca reescreve nem concatena os Parquet originais."""
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(config={"memory_limit": memory_limit, "threads": threads})
    try:
        con.execute("SET preserve_insertion_order=false")
        con.execute(f"SET temp_directory={literal(temp_dir)}")
        con.execute(f"CREATE VIEW raw AS SELECT * FROM read_parquet({literal(raw_path)})")
        partitions = con.execute(
            """SELECT fonte,year(din_instante) AS year,month(din_instante) AS month,
            count(*) AS row_count
            FROM raw GROUP BY ALL ORDER BY 1,2,3"""
        ).fetchall()
        total = 0
        schema: dict[str, str] = {}
        for source, year, month, rows in partitions:
            arrow = con.execute(
                "SELECT *, "
                + target_sql()
                + " FROM raw WHERE fonte=? AND year(din_instante)=? AND month(din_instante)=? "
                "ORDER BY id_ons,din_instante",
                [source, year, month],
            ).to_arrow_table()
            frame = add_release_times(pl.from_arrow(arrow), scenario, calendar)
            destination = (
                output_dir
                / f"source={source}"
                / f"year={year}"
                / f"month={month:02d}"
                / "targets.parquet"
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            frame.write_parquet(destination, compression="zstd", statistics=True)
            total += rows
            schema = {name: str(dtype) for name, dtype in frame.schema.items()}
        return {
            "input": str(raw_path),
            "input_sha256": _sha256(raw_path),
            "scenario": scenario.scenario_id,
            "calendar_version": calendar.version,
            "rows": total,
            "partitions": len(partitions),
            "schema": schema,
        }
    finally:
        con.close()


def write_feature_partitions(
    targets_dir: Path,
    output_dir: Path,
    *,
    source: str,
    scenario_id: str,
    round_id: str,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    """Gera features e baselines por dia, mantendo apenas uma janela de dados em memória."""
    started = perf_counter()
    pattern = str(targets_dir / f"source={source}" / "year=*" / "month=*" / "*.parquet")
    scan = pl.scan_parquet(pattern, hive_partitioning=False)
    current = datetime.combine(start.date(), datetime.min.time())
    files = 0
    feature_rows = 0
    baseline_rows = 0
    while current < end:
        day_end = min(current + timedelta(days=1), end)
        window = scan.filter(
            (pl.col("din_instante") >= current - timedelta(days=35))
            & (pl.col("din_instante") < day_end + timedelta(days=1))
        ).collect(engine="streaming")
        feature_batches = []
        baseline_batches = []
        t0 = max(current, start)
        while t0 < day_end:
            features = build_feature_batch(window, t0)
            if not features.is_empty():
                feature_batches.append(features)
                requests = features.select("fonte", "id_ons", "id_estado", "t0", "tau", "horizon")
                baseline_batches.append(generate_baselines(window, requests))
            t0 += timedelta(minutes=30)
        if feature_batches:
            feature_frame = pl.concat(feature_batches, how="diagonal_relaxed")
            baseline_frame = pl.concat(baseline_batches, how="diagonal_relaxed")
            partition = (
                output_dir
                / f"scenario={scenario_id}"
                / f"source={source}"
                / f"round={round_id}"
                / f"date={current.date().isoformat()}"
            )
            partition.mkdir(parents=True, exist_ok=True)
            feature_frame.write_parquet(partition / "features.parquet", compression="zstd")
            baseline_frame.write_parquet(partition / "baselines.parquet", compression="zstd")
            files += 2
            feature_rows += feature_frame.height
            baseline_rows += baseline_frame.height
        current += timedelta(days=1)
    return {
        "source": source,
        "scenario": scenario_id,
        "round": round_id,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "feature_rows": feature_rows,
        "baseline_rows": baseline_rows,
        "files": files,
        "duration_seconds": perf_counter() - started,
        "peak_rss_bytes": peak_rss_bytes(),
    }
