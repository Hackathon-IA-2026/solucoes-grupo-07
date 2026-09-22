from __future__ import annotations

import hashlib
import os
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timedelta
from multiprocessing import get_context
from pathlib import Path
from time import perf_counter
from typing import Any

import duckdb
import polars as pl

from curtamap.audit import literal
from curtamap.experimental.baselines import generate_baselines
from curtamap.experimental.data import add_release_times
from curtamap.experimental.features import SOURCE_COLUMNS, build_feature_batch
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


def _write_feature_day(
    pattern: str,
    output_dir: Path,
    source: str,
    scenario_id: str,
    round_id: str,
    current: datetime,
    start: datetime,
    end: datetime,
) -> tuple[int, int, int]:
    """Gera a partição de um dia; dias são independentes e podem rodar em paralelo."""
    day_end = min(current + timedelta(days=1), end)
    window = (
        pl.scan_parquet(pattern, hive_partitioning=False)
        .filter(
            (pl.col("din_instante") >= current - timedelta(days=35))
            & (pl.col("din_instante") < day_end + timedelta(days=1))
        )
        .select(SOURCE_COLUMNS)
        .collect(engine="streaming")
    )
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
    if not feature_batches:
        return 0, 0, 0
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
    return feature_frame.height, baseline_frame.height, 2


def write_feature_partitions(
    targets_dir: Path,
    output_dir: Path,
    *,
    source: str,
    scenario_id: str,
    round_id: str,
    start: datetime,
    end: datetime,
    workers: int = 1,
) -> dict[str, Any]:
    """Gera features e baselines por dia, mantendo apenas uma janela de dados por processo.

    Cada dia lê sua própria janela e grava sua própria partição; com ``workers > 1`` os dias
    são distribuídos entre processos e o resultado é idêntico ao sequencial.
    """
    if workers < 1:
        raise ValueError("workers deve ser positivo")
    started = perf_counter()
    pattern = str(targets_dir / f"source={source}" / "year=*" / "month=*" / "*.parquet")
    days = []
    current = datetime.combine(start.date(), datetime.min.time())
    while current < end:
        days.append(current)
        current += timedelta(days=1)
    arguments = [
        (pattern, output_dir, source, scenario_id, round_id, day, start, end) for day in days
    ]
    if workers == 1:
        results = [_write_feature_day(*item) for item in arguments]
    else:
        # Limita as threads do Polars em cada processo filho para não sobrecarregar a CPU.
        threads = str(max(1, (os.cpu_count() or workers) // workers))
        previous = os.environ.get("POLARS_MAX_THREADS")
        os.environ["POLARS_MAX_THREADS"] = threads
        try:
            with ProcessPoolExecutor(
                max_workers=workers, mp_context=get_context("spawn")
            ) as executor:
                results = list(executor.map(_write_feature_day, *zip(*arguments, strict=True)))
        finally:
            if previous is None:
                os.environ.pop("POLARS_MAX_THREADS", None)
            else:
                os.environ["POLARS_MAX_THREADS"] = previous
    return {
        "source": source,
        "scenario": scenario_id,
        "round": round_id,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days": len(days),
        "workers": workers,
        "feature_rows": sum(item[0] for item in results),
        "baseline_rows": sum(item[1] for item in results),
        "files": sum(item[2] for item in results),
        "duration_seconds": perf_counter() - started,
        "peak_rss_bytes": peak_rss_bytes(),
    }
