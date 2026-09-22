"""Paridade da campanha executada por partes com o oráculo materializado (commit f3cca8b).

O oráculo recebe features e baselines já coletados; a implementação nova recebe
``pl.scan_parquet`` e divide a validação em partes de ``t0``. Os artefatos precisam ser
idênticos, exceto ``fit_seconds`` (tempo de parede), o campo novo ``execution`` do relatório
e o último bit das somas em ``diagnostics/`` (não determinístico no próprio oráculo; ver
``_assert_same_diagnostics``). O pico de memória não é comparável: oráculo e versão nova
rodam no mesmo processo e ``peak_rss_bytes`` é o pico de toda a vida do processo.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import joblib
import numpy as np
import polars as pl
import pytest
import reference_campaign_stage2b as oracle
from campaign_fixtures import CALENDAR, SEED, V1, manifest, synthetic_dataset, write_partitions

from curtamap.experimental.artifacts import RunStore
from curtamap.experimental.campaign import run_campaign_round, run_sensitivity_round

CHUNK_DAYS = 10


def _files(root: Path) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())


def _model_signature(trained) -> dict:
    model = trained.model
    estimator = model.estimator
    signature = {
        "selected_params": trained.selected_params,
        "internal_scores": trained.internal_scores,
        "threshold": trained.threshold,
        "calibration_status": trained.calibration_status,
        "classes": model.classes_,
        "medians": model.preprocessor.numeric_medians_,
        "means": model.preprocessor.numeric_means_,
        "scales": model.preprocessor.numeric_scales_,
        "categories": model.preprocessor.categories_,
    }
    if hasattr(estimator, "booster_"):
        signature["booster"] = estimator.booster_.model_to_string()
    else:
        signature["coef"] = np.asarray(estimator.coef_).tolist()
        signature["intercept"] = np.asarray(estimator.intercept_).tolist()
    if trained.calibrator is not None:
        signature["calibrator"] = (
            trained.calibrator.estimator.coef_.tolist(),
            trained.calibrator.estimator.intercept_.tolist(),
        )
    return signature


def _as_json(payload: dict) -> dict:
    """Mesma serialização do ``RunStore`` (datas viram texto, tuplas viram listas)."""
    return json.loads(json.dumps(payload, sort_keys=True, default=str))


def _normalized_report(payload: dict) -> dict:
    payload = dict(payload)
    payload.pop("execution", None)
    payload["models"] = {
        identity: {key: value for key, value in entry.items() if key != "fit_seconds"}
        for identity, entry in payload["models"].items()
    }
    return payload


def _assert_same_diagnostics(expected: dict, actual: dict, relative: str) -> None:
    """Divergência documentada: no oráculo, ``group_by().agg(sum)`` sem ``maintain_order``
    soma em paralelo e varia no último bit entre execuções do próprio oráculo (medido: 46
    resultados distintos em 50 repetições sobre o mesmo frame). A versão nova soma na ordem
    das linhas; exige-se mesmas entidades/episódios, na mesma ordem, e erro igual até 1e-12.
    """
    assert actual.keys() == expected.keys(), relative
    for key, rows in expected.items():
        assert len(actual[key]) == len(rows), relative
        for left, right in zip(rows, actual[key], strict=True):
            assert {k: v for k, v in right.items() if k != "absolute_error"} == {
                k: v for k, v in left.items() if k != "absolute_error"
            }, relative
            assert right["absolute_error"] == pytest.approx(left["absolute_error"], rel=1e-12)


def assert_same_artifacts(expected_root: Path, actual_root: Path) -> None:
    assert _files(actual_root) == _files(expected_root)
    for relative in _files(expected_root):
        expected, actual = expected_root / relative, actual_root / relative
        if relative.endswith(".parquet"):
            left, right = pl.read_parquet(expected), pl.read_parquet(actual)
            assert right.schema == left.schema, relative
            assert right.equals(left), relative
        elif relative.endswith(".joblib"):
            assert _model_signature(joblib.load(actual)) == _model_signature(
                joblib.load(expected)
            ), relative
        elif relative.endswith(".json"):
            left = json.loads(expected.read_text(encoding="utf-8"))
            right = json.loads(actual.read_text(encoding="utf-8"))
            if relative.startswith("reports/"):
                left, right = _normalized_report(left), _normalized_report(right)
            if relative.startswith("failures/"):
                for payload in (left, right):
                    payload.pop("traceback")
                    payload.pop("recorded_at")
            if relative.startswith("diagnostics/"):
                _assert_same_diagnostics(left, right, relative)
                continue
            assert right == left, relative
        else:  # pragma: no cover - nenhum outro tipo de artefato é gerado
            raise AssertionError(f"artefato inesperado: {relative}")


@pytest.fixture(scope="module")
def campaign_runs(tmp_path_factory: pytest.TempPathFactory) -> dict:
    root = tmp_path_factory.mktemp("campanha com espaços")
    features, baselines = synthetic_dataset(seed=SEED, delay=timedelta(0))
    features_glob, baselines_glob = write_partitions(
        root / "dados sintéticos", "noturno_dia_util", features, baselines
    )
    expected = RunStore.create(root / "oráculo", manifest("main-eolica-v1"))
    oracle_report = oracle.run_campaign_round(
        pl.scan_parquet(features_glob).collect(),
        pl.scan_parquet(baselines_glob).collect(),
        expected,
        source="eolica",
        round_=V1,
        calendar=CALENDAR,
        seed=SEED,
    )
    actual = RunStore.create(root / "novo", manifest("main-eolica-v1"))
    scratch = root / "temporário local"
    scratch.mkdir()
    report = run_campaign_round(
        pl.scan_parquet(features_glob),
        pl.scan_parquet(baselines_glob),
        actual,
        source="eolica",
        round_=V1,
        calendar=CALENDAR,
        seed=SEED,
        chunk_days=CHUNK_DAYS,
        scratch_dir=scratch,
    )
    return {
        "root": root,
        "expected": expected,
        "actual": actual,
        "oracle_report": oracle_report,
        "report": report,
        "scratch": scratch,
    }


def test_campaign_round_in_parts_reproduces_oracle_artifacts(campaign_runs: dict) -> None:
    oracle_report, report = campaign_runs["oracle_report"], campaign_runs["report"]
    # Não vacuidade: todos os modelos, pipelines e comparadores existem nas duas execuções.
    assert oracle_report["failures"] == []
    assert len(oracle_report["models"]) == 8
    assert {
        entry["calibration_status"]
        for identity, entry in oracle_report["models"].items()
        if "corte_positivo" in identity or "restricao_registrada" in identity
    } == {"sigmoide"}
    assert len(oracle_report["baselines"]) == 16
    assert oracle_report["volume_tail_p99_training"] is not None
    expected_root = campaign_runs["expected"].path
    assert len(list((expected_root / "predictions").glob("*-volume-*.parquet"))) == 4
    episodes = pl.read_parquet(
        expected_root / "predictions" / "eolica-V1-corte_positivo-linear.parquet"
    )
    assert episodes["episode_start"].any() and episodes["post_episode_zero"].any()
    assert episodes["entity_new"].any() and not episodes["panel_fixed"].all()
    assert episodes["volume_tail"].any() and (~episodes["eligible_history"]).any()

    assert report["execution"]["validation_chunks"] > 1
    assert report["execution"]["validation_chunk_days"] == CHUNK_DAYS
    assert report["execution"]["peak_rss_bytes"] > 0
    assert _as_json(_normalized_report(report)) == _as_json(_normalized_report(oracle_report))
    assert_same_artifacts(expected_root, campaign_runs["actual"].path)
    # O arquivo temporário de validação fica fora do run e é removido ao final.
    assert list(campaign_runs["scratch"].iterdir()) == []


def test_sensitivity_round_in_parts_reproduces_oracle_artifacts(campaign_runs: dict) -> None:
    root = campaign_runs["root"]
    frozen = campaign_runs["expected"].path
    features, baselines = synthetic_dataset(seed=SEED + 1, delay=timedelta(hours=24))
    features_glob, baselines_glob = write_partitions(
        root / "dados atrasados", "noturno_mais_24h", features, baselines
    )
    expected = RunStore.create(root / "oráculo sensibilidade", manifest("delay-eolica-v1"))
    oracle_report = oracle.run_sensitivity_round(
        pl.scan_parquet(features_glob).collect(),
        pl.scan_parquet(baselines_glob).collect(),
        expected,
        frozen_run=frozen,
        source="eolica",
        round_=V1,
        calendar=CALENDAR,
    )
    actual = RunStore.create(root / "novo sensibilidade", manifest("delay-eolica-v1"))
    report = run_sensitivity_round(
        pl.scan_parquet(features_glob),
        pl.scan_parquet(baselines_glob),
        actual,
        frozen_run=frozen,
        source="eolica",
        round_=V1,
        calendar=CALENDAR,
        chunk_days=CHUNK_DAYS,
        scratch_dir=campaign_runs["scratch"],
    )
    assert oracle_report["failures"] == []
    assert len(oracle_report["models"]) == 8
    assert len(list((expected.path / "predictions").glob("sensitivity-*-volume-*.parquet"))) == 4
    assert report["execution"]["validation_chunks"] > 1
    assert _as_json(_normalized_report(report)) == _as_json(_normalized_report(oracle_report))
    assert_same_artifacts(expected.path, actual.path)
    assert list(campaign_runs["scratch"].iterdir()) == []


def test_campaign_accepts_dataframes_like_the_oracle(campaign_runs: dict) -> None:
    """Entrada eager (``DataFrame``) segue o mesmo caminho via ``.lazy()``."""
    root = campaign_runs["root"]
    features_glob = str(
        root
        / "dados sintéticos"
        / "scenario=noturno_dia_util"
        / "source=eolica"
        / "round=development"
        / "date=*"
    )
    actual = RunStore.create(root / "novo eager", manifest("main-eolica-v1"))
    run_campaign_round(
        pl.scan_parquet(features_glob + "/features.parquet").collect(),
        pl.scan_parquet(features_glob + "/baselines.parquet").collect(),
        actual,
        source="eolica",
        round_=V1,
        calendar=CALENDAR,
        seed=SEED,
        chunk_days=45,
        scratch_dir=campaign_runs["scratch"],
    )
    assert_same_artifacts(campaign_runs["expected"].path, actual.path)
