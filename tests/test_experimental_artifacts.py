import json
from datetime import datetime
from pathlib import Path

import polars as pl
import pytest

from curtamap.experimental.artifacts import RunStore, configuration_digest


def manifest() -> dict:
    return {
        "run_id": "run-sintetico-001",
        "code_commit": "a" * 40,
        "data_hashes": {"eolica": "b" * 64, "fotovoltaica": "c" * 64},
        "schema": {"horizon": "Int64"},
        "calendar": {"version": "synthetic"},
        "resolved_config": {"seed": 42, "threads": 1},
        "parameters": {"family": "linear"},
        "seeds": [42],
        "host": {"system": "synthetic"},
        "started_at": "2026-09-22T00:00:00Z",
        "status": "running",
    }


def test_run_id_is_immutable_and_required_manifest_fields_are_validated(tmp_path: Path) -> None:
    root = tmp_path / "artefatos com espaços"
    store = RunStore.create(root, manifest())
    assert store.path.name == "run-sintetico-001"

    with pytest.raises(FileExistsError):
        RunStore.create(root, manifest())
    with pytest.raises(ValueError, match="manifesto"):
        RunStore.create(root, {"run_id": "incompleto"})


def test_models_parquet_json_logs_failures_and_checksums_round_trip(tmp_path: Path) -> None:
    store = RunStore.create(tmp_path / "raiz externa", manifest())
    predictions = pl.DataFrame(
        {"fonte": ["eolica"], "round": ["V1"], "horizon": [1], "probability": [0.25]}
    )
    store.write_parquet(
        "predictions/scenario=main/source=eolica/round=V1/part.parquet", predictions
    )
    store.write_json("metrics/occurrence.json", {"ap": {"value": 0.5}})
    store.write_model("models/model.joblib", {"coef": [1.0], "seed": 42})
    store.append_log("logs/run.jsonl", {"event": "started"})
    store.record_failure("fit/lightgbm.json", RuntimeError("falha sintética"), resumable=True)

    assert store.read_parquet(
        "predictions/scenario=main/source=eolica/round=V1/part.parquet"
    ).equals(predictions)
    assert store.read_model("models/model.joblib") == {"coef": [1.0], "seed": 42}
    store.finalize(status="technical_pilot_complete", resume_command="uv run curtamap pilot")

    index = json.loads((store.path / "checksums.json").read_text(encoding="utf-8"))
    assert "models/model.joblib" in index["files"]
    assert all("\\" not in relative for relative in index["files"])
    assert all(len(checksum) == 64 for checksum in index["files"].values())
    saved_manifest = json.loads((store.path / "manifest.json").read_text(encoding="utf-8"))
    assert saved_manifest["status"] == "technical_pilot_complete"
    assert saved_manifest["resume_command"] == "uv run curtamap pilot"
    assert saved_manifest["bytes_consumed"] > 0


def test_json_rejects_nan_instead_of_serializing_ambiguous_metric(tmp_path: Path) -> None:
    store = RunStore.create(tmp_path, manifest())
    with pytest.raises(ValueError):
        store.write_json("metrics/invalid.json", {"metric": float("nan")})


def test_configuration_and_seed_have_stable_digest_independent_of_key_order() -> None:
    left = {"seed": 42, "paths": {"cache": "/tmp/a b"}, "families": ["linear", "lightgbm"]}
    right = {"families": ["linear", "lightgbm"], "paths": {"cache": "/tmp/a b"}, "seed": 42}
    assert configuration_digest(left) == configuration_digest(right)
    assert configuration_digest(left) != configuration_digest(left | {"seed": 17})


def _stream_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "fonte": ["eolica", None, "eolica", "eolica"],
            "t0": [datetime(2025, 1, 1), None, datetime(2025, 1, 2), datetime(2025, 1, 3)],
            "flag": [True, None, False, True],
            "prediction": [0.25, None, 0.5, 0.75],
            "horizon": [1, 2, None, 48],
            "cause": pl.Series([None, None, None, None], dtype=pl.String),
        }
    )


def test_parquet_stream_in_parts_equals_single_write_and_preserves_order(
    tmp_path: Path,
) -> None:
    store = RunStore.create(tmp_path / "raiz com espaço", manifest())
    frame = _stream_frame()
    store.write_parquet("predictions/unico.parquet", frame)
    with store.open_parquet_stream("predictions/partes.parquet") as stream:
        stream.write(frame.head(1))
        stream.write(frame.slice(1, 2))
        stream.write(frame.clear())
        stream.write(frame.tail(1))
    assert stream.rows == frame.height
    single = store.read_parquet("predictions/unico.parquet")
    parts = store.read_parquet("predictions/partes.parquet")
    assert parts.schema == single.schema
    assert parts.equals(single)


def test_parquet_stream_aborts_on_error_and_rejects_schema_drift(tmp_path: Path) -> None:
    store = RunStore.create(tmp_path, manifest())
    target = store.path / "predictions" / "falha.parquet"
    with (
        pytest.raises(RuntimeError, match="interrompida"),
        store.open_parquet_stream("predictions/falha.parquet") as stream,
    ):
        stream.write(_stream_frame())
        raise RuntimeError("interrompida")
    assert not target.exists()

    stream = store.open_parquet_stream("predictions/deriva.parquet")
    stream.write(_stream_frame())
    with pytest.raises(ValueError, match="esquema"):
        stream.write(_stream_frame().with_columns(pl.col("horizon").cast(pl.String)))
    stream.abort()
    assert not (store.path / "predictions" / "deriva.parquet").exists()

    empty = store.open_parquet_stream("predictions/vazio.parquet")
    empty.write(_stream_frame().clear())
    empty.close()
    empty.abort()  # já concluído: não descarta
    assert store.read_parquet("predictions/vazio.parquet").schema == _stream_frame().schema
    with pytest.raises(ValueError, match="concluído"):
        empty.write(_stream_frame())
    with pytest.raises(ValueError, match="nenhuma parte"):
        store.open_parquet_stream("predictions/sem-partes.parquet").close()
    with pytest.raises(ValueError, match="relativo"):
        store.open_parquet_stream("../fora.parquet")
