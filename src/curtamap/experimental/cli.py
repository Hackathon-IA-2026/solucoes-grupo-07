from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from curtamap.experimental.artifacts import RunStore, configuration_digest
from curtamap.experimental.calendar import load_calendar_manifest
from curtamap.experimental.campaign import (
    DEFAULT_CHUNK_DAYS,
    run_campaign_round,
    run_sensitivity_round,
)
from curtamap.experimental.config import ExperimentalSettings
from curtamap.experimental.preparation import prepare_target_partitions, write_feature_partitions
from curtamap.experimental.runner import run_technical_pilot
from curtamap.experimental.temporal import (
    AvailabilityScenario,
    external_rounds,
    require_reserved_test_release,
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], check=True, capture_output=True, text=True
    ).stdout.strip()


def _scenario(identifier: str) -> AvailabilityScenario:
    if identifier == "noturno_dia_util":
        return AvailabilityScenario.main()
    if identifier == "noturno_mais_24h":
        return AvailabilityScenario.delayed_24h()
    raise ValueError(f"cenário desconhecido: {identifier}")


def _manifest(
    run_id: str,
    config: dict[str, Any],
    calendar_path: Path,
    calendar_sha: str,
    settings: ExperimentalSettings,
) -> dict[str, Any]:
    data_hashes = {}
    for source, relative in config["raw_files"].items():
        path = settings.data_dir / relative
        if path.exists():
            data_hashes[source] = _sha256(path)
    return {
        "run_id": run_id,
        "code_commit": _git("rev-parse", "HEAD"),
        "data_hashes": data_hashes,
        "schema": {},
        "calendar": {"path": str(calendar_path), "sha256": calendar_sha},
        "resolved_config": config
        | {
            "data_dir": str(settings.data_dir.resolve()),
            "model_dir": str(settings.model_dir.resolve()),
            "experiment_dir": str(settings.experiment_dir.resolve()),
            "cache_dir": str(settings.cache_dir.resolve()),
            "temp_dir": str(settings.temp_dir.resolve()),
        },
        "configuration_sha256": configuration_digest(config),
        "parameters": {"families": config["families"], "tasks": config["tasks"]},
        "seeds": [config["seed"]],
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "started_at": datetime.now(UTC).isoformat(),
        "status": "running",
    }


def _training_slots(config: dict[str, Any], source: str) -> dict[str, int] | None:
    """Meias-horas por dia de cada tarefa na contingência aprovada; ausente = treino completo."""
    sampling = config.get("training_sampling")
    if not sampling:
        return None
    if sampling.get("seed") != config["seed"]:
        raise ValueError("a semente da amostragem deve ser a semente principal")
    slots = dict(sampling["slots_per_day"][source])
    if set(slots) != set(config["tasks"]):
        raise ValueError("a amostragem deve definir todas as tarefas da fonte")
    return slots


def preflight(config: dict[str, Any], settings: ExperimentalSettings) -> dict[str, Any]:
    branch = _git("branch", "--show-current")
    if branch != "etapa-2-experimental":
        raise RuntimeError(f"branch obrigatória ausente: atual={branch}")
    paths = [
        settings.data_dir,
        settings.model_dir,
        settings.experiment_dir,
        settings.cache_dir,
        settings.temp_dir,
    ]
    settings.ensure_directories()
    usage = shutil.disk_usage(settings.experiment_dir)
    raw = {
        source: {
            "path": str(settings.data_dir / relative),
            "exists": (settings.data_dir / relative).exists(),
        }
        for source, relative in config["raw_files"].items()
    }
    return {
        "branch": branch,
        "commit": _git("rev-parse", "HEAD"),
        "paths": [str(path.resolve()) for path in paths],
        "free_bytes": usage.free,
        "warning_threshold_bytes": config["initial_artifact_warning_gib"] * 1024**3,
        "raw_files": raw,
        "ready": all(item["exists"] for item in raw.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Execução reproduzível da Etapa 2B")
    parser.add_argument(
        "--config", type=Path, default=Path("configs/experimental/stage2b.example.json")
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("preflight")
    prepare = subparsers.add_parser("prepare-targets")
    prepare.add_argument(
        "--scenario", choices=["noturno_dia_util", "noturno_mais_24h"], required=True
    )
    features = subparsers.add_parser("build-features")
    features.add_argument(
        "--scenario", choices=["noturno_dia_util", "noturno_mais_24h"], required=True
    )
    features.add_argument("--source", choices=["eolica", "fotovoltaica"], required=True)
    features.add_argument("--round", required=True)
    features.add_argument("--start", type=datetime.fromisoformat, required=True)
    features.add_argument("--end", type=datetime.fromisoformat, required=True)
    features.add_argument(
        "--workers",
        type=int,
        default=None,
        help="processos paralelos por dia (padrão: feature_workers da configuração)",
    )
    pilot = subparsers.add_parser("pilot")
    pilot.add_argument("--run-id", required=True)
    pilot.add_argument("--features", type=Path, required=True)
    campaign = subparsers.add_parser("campaign-round")
    campaign.add_argument("--run-id", required=True)
    campaign.add_argument("--source", choices=["eolica", "fotovoltaica"], required=True)
    campaign.add_argument("--round", choices=["V1", "V2", "V3", "V4"], required=True)
    campaign.add_argument("--features", type=Path, required=True)
    campaign.add_argument("--baselines", type=Path, required=True)
    sensitivity = subparsers.add_parser("sensitivity-round")
    sensitivity.add_argument("--run-id", required=True)
    sensitivity.add_argument("--source", choices=["eolica", "fotovoltaica"], required=True)
    sensitivity.add_argument("--round", choices=["V1", "V2", "V3", "V4"], required=True)
    sensitivity.add_argument("--features", type=Path, required=True)
    sensitivity.add_argument("--baselines", type=Path, required=True)
    sensitivity.add_argument("--frozen-run", type=Path, required=True)
    for command in (campaign, sensitivity):
        command.add_argument(
            "--validation-chunk-days",
            type=int,
            default=DEFAULT_CHUNK_DAYS,
            help="dias de emissões por parte da validação em memória (não altera resultados)",
        )
    reserved = subparsers.add_parser("reserved-test")
    reserved.add_argument("--allow-reserved-test", action="store_true")
    reserved.add_argument("--decision-ref")
    args = parser.parse_args()

    config = _load(args.config)
    settings = ExperimentalSettings(
        seed=config["seed"],
        threads=config["threads"],
        duckdb_memory_limit=config["duckdb_memory_limit"],
    )
    calendar_path = Path(config["calendar"])
    loaded_calendar = load_calendar_manifest(calendar_path)
    if args.command == "preflight":
        print(json.dumps(preflight(config, settings), indent=2, ensure_ascii=False))
        return
    if args.command == "prepare-targets":
        reports = []
        for _source, relative in config["raw_files"].items():
            reports.append(
                prepare_target_partitions(
                    settings.data_dir / relative,
                    settings.cache_dir / "stage2b" / "targets" / args.scenario,
                    _scenario(args.scenario),
                    loaded_calendar.calendar,
                    temp_dir=settings.temp_dir,
                    memory_limit=settings.duckdb_memory_limit,
                    threads=settings.threads,
                )
            )
        print(json.dumps(reports, indent=2, ensure_ascii=False, default=str))
        return
    if args.command == "build-features":
        report = write_feature_partitions(
            settings.cache_dir / "stage2b" / "targets" / args.scenario,
            settings.experiment_dir / "stage2b-datasets",
            source=args.source,
            scenario_id=args.scenario,
            round_id=args.round,
            start=args.start,
            end=args.end,
            workers=args.workers or config.get("feature_workers", 1),
        )
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return
    if args.command == "reserved-test":
        require_reserved_test_release(
            real_data=True,
            allow_reserved_test=args.allow_reserved_test,
            decision_ref=args.decision_ref,
        )
        raise SystemExit(
            "liberação validada; a receita congelada da Etapa 2C ainda precisa ser fornecida"
        )

    preflight(config, settings)
    store = RunStore.create(
        settings.experiment_dir,
        _manifest(
            args.run_id,
            config,
            calendar_path,
            loaded_calendar.sha256,
            settings,
        ),
    )
    try:
        if args.command == "pilot":
            frame = (
                pl.scan_parquet(str(args.features))
                .head(config["pilot_max_examples_per_task_source"] * 4)
                .collect(engine="streaming")
            )
            run_technical_pilot(
                frame,
                store,
                seed=config["seed"],
                max_examples=config["pilot_max_examples_per_task_source"],
            )
            store.finalize(
                status="technical_pilot_complete",
                resume_command=f"curtamap-experiment --config {args.config} pilot ...",
            )
        elif args.command == "campaign-round":
            # Leitura preguiçosa: a campanha coleta por partes, só as colunas necessárias.
            frame = pl.scan_parquet(str(args.features))
            baselines = pl.scan_parquet(str(args.baselines))
            round_ = next(item for item in external_rounds() if item.round_id == args.round)
            report = run_campaign_round(
                frame,
                baselines,
                store,
                source=args.source,
                round_=round_,
                calendar=loaded_calendar.calendar,
                seed=config["seed"],
                chunk_days=args.validation_chunk_days,
                scratch_dir=settings.temp_dir,
                training_slots=_training_slots(config, args.source),
            )
            status = "complete" if not report["failures"] else "incomplete"
            store.finalize(
                status=status,
                resume_command=f"curtamap-experiment --config {args.config} campaign-round ...",
            )
        else:
            frame = pl.scan_parquet(str(args.features))
            baselines = pl.scan_parquet(str(args.baselines))
            round_ = next(item for item in external_rounds() if item.round_id == args.round)
            report = run_sensitivity_round(
                frame,
                baselines,
                store,
                frozen_run=args.frozen_run,
                source=args.source,
                round_=round_,
                calendar=loaded_calendar.calendar,
                chunk_days=args.validation_chunk_days,
                scratch_dir=settings.temp_dir,
            )
            status = "complete" if not report["failures"] else "incomplete"
            store.finalize(
                status=status,
                resume_command=f"curtamap-experiment --config {args.config} sensitivity-round ...",
            )
    except Exception as error:
        store.record_failure("run.json", error, resumable=True)
        store.finalize(status="failed", resume_command="repita o comando após corrigir a causa")
        raise


if __name__ == "__main__":
    main()
