from datetime import datetime
from pathlib import Path

import polars as pl

from curtamap.experimental.artifacts import RunStore
from curtamap.experimental.runner import run_technical_pilot


def feature_frame() -> pl.DataFrame:
    rows = 120
    causes = ["REL", "CNF", "ENE"] * 40
    positive = [index % 2 == 0 for index in range(rows)]
    return pl.DataFrame(
        {
            "fonte": ["eolica"] * rows,
            "id_ons": ["A" if index < 60 else "B" for index in range(rows)],
            "id_estado": ["RJ"] * rows,
            "id_subsistema": ["SE"] * rows,
            "ceg_level": ["conjunto"] * rows,
            "horizon": [(index % 48) + 1 for index in range(rows)],
            "history_age_hours": [24.0 + index % 12 for index in range(rows)],
            "history_coverage_28d": [1.0] * rows,
            "positive_frequency_7d": [0.5] * rows,
            "positive_frequency_28d": [0.5] * rows,
            "mean_volume_28d": [10.0] * rows,
            "tau_weekday": [index % 7 for index in range(rows)],
            "tau_month": [1] * rows,
            "t0": [datetime(2024, 1, 1)] * rows,
            "target_available_at": [datetime(2024, 1, 3)] * rows,
            "target_observed": [True] * rows,
            "true_positive": positive,
            "true_restriction": [index % 4 != 0 for index in range(rows)],
            "true_volume_mwmed": [10.0 if value else 0.0 for value in positive],
            "true_volume_valid": [True] * rows,
            "true_cause": causes,
        }
    )


def test_technical_pilot_fits_all_minimum_families_without_selection_metrics(
    tmp_path: Path,
) -> None:
    manifest = {
        "run_id": "pilot-001",
        "code_commit": "a" * 40,
        "data_hashes": {},
        "schema": {},
        "calendar": {},
        "resolved_config": {"seed": 42},
        "parameters": {},
        "seeds": [42],
        "host": {"system": "test"},
        "started_at": "2026-09-22T00:00:00Z",
        "status": "running",
    }
    store = RunStore.create(tmp_path, manifest)
    report = run_technical_pilot(feature_frame(), store, seed=42, max_examples=100)
    assert report["purpose"] == "contracts_and_resources_only"
    assert report["selection_metrics_emitted"] is False
    assert len(report["fits"]) == 8
    assert {fit["family"] for fit in report["fits"]} == {"linear", "lightgbm"}
    assert {fit["task"] for fit in report["fits"]} == {
        "corte_positivo",
        "restricao_registrada",
        "volume_condicional",
        "causa",
    }
    assert len(list((store.path / "models" / "pilot").glob("*.joblib"))) == 8
