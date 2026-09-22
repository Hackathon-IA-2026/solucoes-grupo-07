from __future__ import annotations

import hashlib
import json
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import polars as pl

REQUIRED_MANIFEST_FIELDS = frozenset(
    {
        "run_id",
        "code_commit",
        "data_hashes",
        "schema",
        "calendar",
        "resolved_config",
        "parameters",
        "seeds",
        "host",
        "started_at",
        "status",
    }
)


def configuration_digest(configuration: dict[str, Any]) -> str:
    encoded = json.dumps(
        configuration,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=str,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


@dataclass
class RunStore:
    path: Path
    manifest: dict[str, Any]

    @classmethod
    def create(cls, root: Path, manifest: dict[str, Any]) -> RunStore:
        missing = REQUIRED_MANIFEST_FIELDS - manifest.keys()
        if missing:
            raise ValueError("manifesto incompleto: " + ", ".join(sorted(missing)))
        run_id = str(manifest["run_id"])
        if not run_id or Path(run_id).name != run_id:
            raise ValueError("run_id deve ser um nome simples e imutável")
        path = root / run_id
        path.mkdir(parents=True, exist_ok=False)
        store = cls(path=path, manifest=dict(manifest))
        store.write_json("manifest.json", store.manifest)
        return store

    def _target(self, relative: str | Path) -> Path:
        relative = Path(relative)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("artefato deve usar caminho relativo dentro do run")
        target = self.path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def write_json(self, relative: str | Path, value: Any) -> Path:
        target = self._target(relative)
        payload = json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            default=str,
        )
        target.write_text(payload + "\n", encoding="utf-8")
        return target

    def write_parquet(self, relative: str | Path, frame: pl.DataFrame) -> Path:
        target = self._target(relative)
        frame.write_parquet(target)
        return target

    def read_parquet(self, relative: str | Path) -> pl.DataFrame:
        return pl.read_parquet(self._target(relative))

    def write_model(self, relative: str | Path, model: Any) -> Path:
        target = self._target(relative)
        joblib.dump(model, target)
        return target

    def read_model(self, relative: str | Path) -> Any:
        return joblib.load(self._target(relative))

    def append_log(self, relative: str | Path, event: dict[str, Any]) -> Path:
        target = self._target(relative)
        payload = dict(event)
        payload.setdefault("timestamp", datetime.now(UTC).isoformat())
        line = json.dumps(payload, ensure_ascii=False, allow_nan=False, default=str)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        return target

    def record_failure(
        self, relative: str | Path, error: BaseException, *, resumable: bool
    ) -> Path:
        return self.write_json(
            Path("failures") / relative,
            {
                "error_type": type(error).__name__,
                "message": str(error),
                "traceback": "".join(traceback.format_exception(error)),
                "resumable": resumable,
                "recorded_at": datetime.now(UTC).isoformat(),
            },
        )

    def finalize(self, *, status: str, resume_command: str) -> None:
        consumed = sum(path.stat().st_size for path in self.path.rglob("*") if path.is_file())
        self.manifest.update(
            {
                "status": status,
                "finished_at": datetime.now(UTC).isoformat(),
                "bytes_consumed": consumed,
                "resume_command": resume_command,
            }
        )
        self.write_json("manifest.json", self.manifest)
        files = {
            path.relative_to(self.path).as_posix(): _sha256(path)
            for path in sorted(self.path.rglob("*"))
            if path.is_file() and path.name != "checksums.json"
        }
        self.write_json(
            "checksums.json",
            {
                "algorithm": "sha256",
                "generated_at": datetime.now(UTC).isoformat(),
                "files": files,
            },
        )
