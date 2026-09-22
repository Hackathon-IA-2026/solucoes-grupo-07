"""Subcomandos ``campaign-round`` e ``sensitivity-round`` ponta a ponta, com dados sintéticos."""

import json
import sys
from datetime import timedelta
from pathlib import Path

import polars as pl
import pytest
from campaign_fixtures import SEED, synthetic_dataset, write_partitions

from curtamap.experimental import cli

REPOSITORY = Path(__file__).resolve().parents[1]


def _run(monkeypatch: pytest.MonkeyPatch, *arguments: str) -> None:
    monkeypatch.setattr(sys, "argv", ["curtamap-experiment", *arguments])
    cli.main()


def test_campaign_and_sensitivity_rounds_scan_lazily_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "dados com espaço"
    main = write_partitions(
        data, "noturno_dia_util", *synthetic_dataset(seed=SEED, delay=timedelta(0), grid="12h")
    )
    delayed = write_partitions(
        data,
        "noturno_mais_24h",
        *synthetic_dataset(seed=SEED + 1, delay=timedelta(hours=24), grid="12h"),
    )
    config = json.loads(
        (REPOSITORY / "configs" / "experimental" / "stage2b.example.json").read_text("utf-8")
    )
    config["calendar"] = str(REPOSITORY / "configs" / "experimental" / "calendar-2023-2026.json")
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    directories = {name: tmp_path / name for name in ("data", "model", "experiment", "cache")}
    directories["temp"] = tmp_path / "temporário"
    for name, path in directories.items():
        monkeypatch.setenv(f"CURTAMAP_{name.upper()}_DIR", str(path))
    # A verificação de branch do preflight não se aplica a worktrees de teste.
    monkeypatch.setattr(cli, "_git", lambda *arguments: "0" * 40)
    monkeypatch.setattr(
        cli, "preflight", lambda config, settings: settings.ensure_directories() or {}
    )
    received = []
    for name in ("run_campaign_round", "run_sensitivity_round"):
        original = getattr(cli, name)

        def spy(features, baselines, *args, _original=original, **kwargs):
            received.append((type(features), type(baselines), kwargs["scratch_dir"]))
            return _original(features, baselines, *args, **kwargs)

        monkeypatch.setattr(cli, name, spy)

    common = ["--config", str(config_path)]
    _run(
        monkeypatch,
        *common,
        "campaign-round",
        "--run-id",
        "main-eolica-v1",
        "--source",
        "eolica",
        "--round",
        "V1",
        "--features",
        main[0],
        "--baselines",
        main[1],
        "--validation-chunk-days",
        "15",
    )
    run = directories["experiment"] / "main-eolica-v1"
    report = json.loads((run / "reports" / "eolica-V1.json").read_text("utf-8"))
    assert json.loads((run / "manifest.json").read_text("utf-8"))["status"] == "complete"
    assert report["failures"] == []
    assert len(report["models"]) == 8
    assert report["execution"]["validation_chunk_days"] == 15
    assert report["execution"]["validation_chunks"] > 1
    assert len(list((run / "predictions").glob("*.parquet"))) == 12
    assert (run / "checksums.json").exists()

    _run(
        monkeypatch,
        *common,
        "sensitivity-round",
        "--run-id",
        "delay-eolica-v1",
        "--source",
        "eolica",
        "--round",
        "V1",
        "--features",
        delayed[0],
        "--baselines",
        delayed[1],
        "--frozen-run",
        str(run),
    )
    sensitivity = directories["experiment"] / "delay-eolica-v1"
    report = json.loads((sensitivity / "reports" / "sensitivity-eolica-V1.json").read_text("utf-8"))
    assert json.loads((sensitivity / "manifest.json").read_text("utf-8"))["status"] == "complete"
    assert report["failures"] == [] and report["models_retrained"] is False
    assert len(list((sensitivity / "predictions").glob("sensitivity-*.parquet"))) == 12
    assert report["execution"]["validation_chunk_days"] == 7

    assert received == [(pl.LazyFrame, pl.LazyFrame, directories["temp"])] * 2
    # O Parquet temporário da validação é removido; nada sobra no diretório temporário.
    assert list(directories["temp"].iterdir()) == []
