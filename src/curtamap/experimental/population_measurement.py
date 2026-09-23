"""Mede populações da campanha, por dia, sem ajustar modelos nem alterar o dataset.

O cache contém somente uma partição diária projetada. A coleta devolve agregados,
nunca a matriz completa de treino. Contagens de validação são suportes potenciais
dos alvos: a finitude das previsões só pode ser verificada depois da inferência.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl

from curtamap.experimental.calendar import load_calendar_manifest
from curtamap.experimental.campaign import (
    OCCURRENCE_TASKS,
    TASK_IDS,
    _range,
    _task_filter,
    _validation_filter,
)
from curtamap.experimental.temporal import AvailabilityScenario, BusinessCalendar, external_rounds
from curtamap.experimental.training import InternalBoundaries, internal_boundaries

SEGMENTS = ("initial", "tuning", "refit", "calibration", "validation")
RESERVED = datetime(2026, 5, 1)
COLUMNS = (
    "fonte",
    "id_ons",
    "t0",
    "horizon",
    "target_available_at",
    "eligible_history",
    "target_observed",
    "true_positive",
    "true_restriction",
    "true_volume_valid",
    "true_volume_mwmed",
    "true_cause",
)
COUNTS = (
    "rows",
    "prediction_rows",
    "eligible_rows",
    "observed_rows",
    "positive_rows",
    "restriction_rows",
    "positive_volume_rows",
    "cause_REL",
    "cause_CNF",
    "cause_ENE",
)
FILTERS = {
    "training_common": "t0 >= start AND t0 + 24h <= end AND eligible_history "
    "AND target_available_at <= label_cutoff",
    "corte_positivo": "target_observed AND true_positive IS NOT NULL",
    "restricao_registrada": "target_observed AND true_restriction IS NOT NULL",
    "volume_condicional": "target_observed AND true_volume_valid AND true_positive "
    "AND true_volume_mwmed > 0",
    "causa": "target_observed AND true_restriction AND true_cause IN (REL,CNF,ENE)",
    "validation_common": "t0 >= round.start AND t0 + 24h <= round.end; painel aberto",
    "validation_occurrence": "alvo da tarefa IS NOT NULL; probabilidades devem ser finitas",
    "validation_cause": "true_cause IN (REL,CNF,ENE); sem filtro adicional de restrição",
    "validation_volume": "alvo finito; suporte realizado também exige previsão finita; "
    "mae_conditional acrescenta apenas alvo > 0",
}


def segment_limits(boundary: InternalBoundaries, first_t0: datetime) -> dict:
    return {
        "initial": (first_t0, boundary.tuning_start, boundary.tuning_start),
        "tuning": (boundary.tuning_start, boundary.calibration_start, boundary.calibration_start),
        "refit": (first_t0, boundary.calibration_start, boundary.calibration_start),
        "calibration": (boundary.calibration_start, boundary.cutoff, boundary.validation_start),
    }


def _count(expression: pl.Expr, name: str) -> pl.Expr:
    return expression.fill_null(False).cast(pl.UInt64).sum().alias(name)


def population_query(frame, round_, boundary, first_t0, segment, task) -> pl.LazyFrame:
    """Uma célula: ajuste elegível ou suporte potencial das métricas no painel aberto."""
    if round_.reserved:
        raise ValueError("teste reservado não pode ser medido")
    if segment not in SEGMENTS or task not in TASK_IDS:
        raise ValueError("segmento ou tarefa desconhecido")
    used = not (segment == "calibration" and task not in OCCURRENCE_TASKS)
    if not used:
        return pl.LazyFrame(
            {
                "round": [round_.round_id],
                "segment": [segment],
                "task": [task],
                "used": [False],
            }
        ).select(
            pl.all(),
            *[pl.lit(None, dtype=pl.UInt64).alias(name) for name in COUNTS],
            pl.lit(None, dtype=pl.Datetime("us")).alias("t0_min"),
            pl.lit(None, dtype=pl.Datetime("us")).alias("t0_max"),
        )
    if segment == "validation":
        selected = frame.filter(_validation_filter(round_))
        if task in OCCURRENCE_TASKS:
            target = "true_positive" if task == "corte_positivo" else "true_restriction"
            mask = pl.col(target).is_not_null()
        elif task == "causa":
            mask = pl.col("true_cause").is_in(["REL", "CNF", "ENE"])
        else:
            mask = pl.col("true_volume_mwmed").is_finite()
    else:
        start, end, label_cutoff = segment_limits(boundary, first_t0)[segment]
        selected = _range(frame, start, end, label_cutoff=label_cutoff)
        mask = _task_filter(task)
    selected = selected.with_columns(mask.fill_null(False).alias("_selected"))
    keep = pl.col("_selected")
    return selected.select(
        pl.lit(round_.round_id).alias("round"),
        pl.lit(segment).alias("segment"),
        pl.lit(task).alias("task"),
        pl.lit(True).alias("used"),
        _count(keep, "rows"),
        (pl.len().cast(pl.UInt64) if segment == "validation" else pl.lit(None, pl.UInt64)).alias(
            "prediction_rows"
        ),
        _count(keep & pl.col("eligible_history"), "eligible_rows"),
        _count(keep & pl.col("target_observed"), "observed_rows"),
        _count(keep & pl.col("true_positive"), "positive_rows"),
        _count(keep & pl.col("true_restriction"), "restriction_rows"),
        _count(
            keep & pl.col("true_volume_mwmed").is_finite() & (pl.col("true_volume_mwmed") > 0),
            "positive_volume_rows",
        ),
        *[
            _count(keep & (pl.col("true_cause") == cause), f"cause_{cause}")
            for cause in ("REL", "CNF", "ENE")
        ],
        pl.col("t0").filter(keep).min().alias("t0_min"),
        pl.col("t0").filter(keep).max().alias("t0_max"),
    )


def _event(handle, event, **values):
    handle.write(json.dumps({"event": event, **values}, ensure_ascii=False, default=str) + "\n")
    handle.flush()
    os.fsync(handle.fileno())


def _write_json(path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, default=str)
        handle.flush()
        os.fsync(handle.fileno())


def _merge_cell(total, part):
    for name in COUNTS:
        if part[name] is not None:
            total[name] = (total[name] or 0) + part[name]
    for name, combine in (("t0_min", min), ("t0_max", max)):
        if part[name] is not None:
            total[name] = combine(total[name], part[name]) if total[name] else part[name]


def measure_populations(
    root: Path,
    start: datetime,
    end: datetime,
    output: Path,
    *,
    calendar: BusinessCalendar,
    source: str,
    expected_partitions: int | None = None,
    dataset_commit: str | None = None,
    measurement_commit: str | None = None,
    calendar_sha256: str | None = None,
) -> dict:
    """Somente leitura de features; JSON e progresso novos, fora do diretório de dados."""
    if end > RESERVED:
        raise ValueError("intervalo invade o teste reservado")
    if start >= end or any(value.time() != datetime.min.time() for value in (start, end)):
        raise ValueError("intervalo deve conter dias inteiros, com início anterior ao fim")
    root, output = root.resolve(), output.resolve()
    if output.is_relative_to(root):
        raise ValueError("evidência deve ficar fora do dataset")
    progress = output.with_suffix(".progress.jsonl")
    for path in (output, progress):
        if path.exists():
            raise FileExistsError(f"evidência já existe: {path}")
    output.parent.mkdir(parents=True, exist_ok=True)
    rounds = tuple(r for r in external_rounds() if not r.reserved)
    boundaries = {
        r.round_id: internal_boundaries(r, AvailabilityScenario.main(), calendar) for r in rounds
    }
    report = {
        "status": "running",
        "dataset": str(root),
        "start": start,
        "end_exclusive": end,
        "source": source,
        "dataset_commit": dataset_commit,
        "measurement_commit": measurement_commit,
        "calendar_version": calendar.version,
        "calendar_sha256": calendar_sha256,
        "scenario": AvailabilityScenario.main().scenario_id,
        "filters": FILTERS,
        "projected_columns": COLUMNS,
        "progress": str(progress),
        "expected_partitions": expected_partitions,
        "completed_partitions": 0,
        "dataset_rows": 0,
        "boundaries": {
            r.round_id: {
                **asdict(boundaries[r.round_id]),
                "validation_end": r.end,
                "last_validation_emission_inclusive": r.last_emission,
            }
            for r in rounds
        },
        "limitations": [
            "Contagens são linhas fonte+id_ons+t0+horizonte, não alvos tau deduplicados.",
            "Refit sobrepõe initial/tuning; não somar segmentos como observações distintas.",
            "Calibração de volume/causa não é usada, portanto suas contagens são nulas.",
            "Validação rows é suporte potencial do alvo; suporte realizado exige previsões. "
            "Volume usa pares finitos; ocorrência rejeita probabilidades não finitas.",
            "Distribuições globais cobrem o dataset lido, não cada célula de treino.",
            "Metadados tamanho/mtime não comprovam integridade criptográfica dos dados.",
            "Uma partição projetada pode ficar em cache; não há matriz integral de treino.",
        ],
    }
    totals = {}
    entities, horizons, months = Counter(), Counter(), Counter()
    daily = []
    first_t0 = None
    with progress.open("x", encoding="utf-8") as log:
        _event(log, "started", **report)
        try:
            paths = []
            for day_index in range((end - start).days):
                day = start + timedelta(days=day_index)
                path = root / f"date={day.date()}" / "features.parquet"
                if path.is_file():
                    paths.append((day, path))
            if not paths or (expected_partitions is not None and len(paths) != expected_partitions):
                raise ValueError(
                    f"partições encontradas: {len(paths)}; esperadas: {expected_partitions}"
                )
            report["partitions"] = len(paths)
            report["requested_days"] = (end - start).days
            existing_days = {day for day, _ in paths}
            report["days_without_partition"] = [
                (start + timedelta(days=index)).date().isoformat()
                for index in range((end - start).days)
                if start + timedelta(days=index) not in existing_days
            ]
            _event(
                log,
                "inventory",
                partitions=len(paths),
                first=str(paths[0][1]),
                last=str(paths[-1][1]),
            )
            for day, path in paths:
                before = path.stat()
                _event(
                    log,
                    "partition_started",
                    partition=path.parent.name,
                    bytes=before.st_size,
                    mtime_ns=before.st_mtime_ns,
                )
                frame = pl.scan_parquet(path, hive_partitioning=False).select(COLUMNS).cache()
                overview = (
                    frame.select(
                        pl.len().alias("rows"),
                        pl.col("t0").min().alias("t0_min"),
                        pl.col("t0").max().alias("t0_max"),
                        pl.col("t0").n_unique().alias("t0_count"),
                        _count(
                            pl.col("t0").is_null()
                            | (pl.col("t0") < day)
                            | (pl.col("t0") >= day + timedelta(days=1)),
                            "wrong_day",
                        ),
                        _count(
                            pl.col("fonte").is_null() | (pl.col("fonte") != source), "wrong_source"
                        ),
                    )
                    .collect(engine="streaming")
                    .row(0, named=True)
                )
                if overview["wrong_day"] or overview["wrong_source"]:
                    raise ValueError(f"partição com dia ou fonte incompatível: {path.parent.name}")
                if first_t0 is None and overview["rows"]:
                    first_t0 = overview["t0_min"]
                queries = [
                    population_query(
                        frame, r, boundaries[r.round_id], first_t0 or start, segment, task
                    )
                    for r in rounds
                    for segment in SEGMENTS
                    for task in TASK_IDS
                ]
                cells = pl.concat(queries, parallel=False).collect(engine="streaming").to_dicts()
                # Cada distribuição é marginal; não fazemos produto entidade x tempo x horizonte.
                entity = frame.group_by("fonte", "id_ons").len().collect(engine="streaming")
                horizon = frame.group_by("horizon").len().collect(engine="streaming")
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ValueError(f"partição mudou durante a medição: {path.parent.name}")
                _event(
                    log,
                    "partition_completed",
                    partition=path.parent.name,
                    **overview,
                    populations=cells,
                )
                for cell in cells:
                    key = (cell["round"], cell["segment"], cell["task"])
                    if key not in totals:
                        totals[key] = dict(cell)
                    else:
                        _merge_cell(totals[key], cell)
                for row in entity.iter_rows(named=True):
                    entities[(row["fonte"], row["id_ons"])] += row["len"]
                for row in horizon.iter_rows(named=True):
                    horizons[row["horizon"]] += row["len"]
                months[day.strftime("%Y-%m")] += overview["rows"]
                daily.append({"day": day.date().isoformat(), **overview})
                report["dataset_rows"] += overview["rows"]
                report["completed_partitions"] += 1
                if report["completed_partitions"] % 25 == 0:
                    print(
                        f"{report['completed_partitions']}/{len(paths)} partições medidas",
                        flush=True,
                    )
            report.update(
                status="complete",
                first_t0=first_t0,
                populations=list(totals.values()),
                segment_limits={
                    name: segment_limits(b, first_t0 or start) for name, b in boundaries.items()
                },
                distributions={
                    "day": daily,
                    "month": [
                        {"month": key, "rows": value} for key, value in sorted(months.items())
                    ],
                    "entity": [
                        {"fonte": key[0], "id_ons": key[1], "rows": value}
                        for key, value in sorted(entities.items(), key=lambda x: str(x[0]))
                    ],
                    "horizon": [
                        {"horizon": key, "rows": value}
                        for key, value in sorted(horizons.items(), key=lambda x: str(x[0]))
                    ],
                },
            )
            _write_json(output, report)
            _event(log, "completed", output=str(output), dataset_rows=report["dataset_rows"])
        except BaseException as error:
            report.update(status="failed", error=f"{type(error).__name__}: {error}")
            _event(
                log,
                "failed",
                error=report["error"],
                completed_partitions=report["completed_partitions"],
            )
            if not output.exists():
                _write_json(output, report)
            raise
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--start", type=datetime.fromisoformat, required=True)
    parser.add_argument("--end", type=datetime.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--calendar", type=Path, required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument(
        "--scenario", choices=[AvailabilityScenario.main().scenario_id], required=True
    )
    parser.add_argument("--expected-partitions", type=int)
    parser.add_argument("--dataset-commit", required=True)
    args = parser.parse_args()
    calendar = load_calendar_manifest(args.calendar)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    measure_populations(
        args.dataset_root,
        args.start,
        args.end,
        args.output,
        calendar=calendar.calendar,
        source=args.source,
        expected_partitions=args.expected_partitions,
        dataset_commit=args.dataset_commit,
        measurement_commit=commit,
        calendar_sha256=calendar.sha256,
    )


if __name__ == "__main__":
    main()
