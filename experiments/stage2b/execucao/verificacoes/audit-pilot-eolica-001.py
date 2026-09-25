import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import polars as pl

root = Path(r"Y:\CurtaMap Etapa 2B")
run = root / "experimentos/pilot-eolica-001"
output = root / "execucao/verificacoes/audit-pilot-eolica-001.json"
if output.exists():
    raise FileExistsError(output)
checksums = json.loads((run / "checksums.json").read_text(encoding="utf-8"))["files"]
checks = {}
for relative, digest in checksums.items():
    with (run / relative).open("rb") as handle:
        checks[relative] = hashlib.file_digest(handle, "sha256").hexdigest() == digest
frame = pl.scan_parquet(str(root / "experimentos/stage2b-datasets/scenario=noturno_dia_util/source=eolica/round=development/date=*/features.parquet")).head(2_000_000)
coverage = frame.select(pl.len().alias("rows"), pl.col("t0").min().alias("first_t0"), pl.col("t0").max().alias("last_t0"), pl.col("eligible_history").sum().alias("eligible_rows")).collect(engine="streaming").to_dicts()[0]
sample = frame.head(256).collect(engine="streaming")
models = []
for path in sorted((run / "models/pilot").glob("*.joblib")):
    model = joblib.load(path)
    pred = model.predict_proba(sample) if model.task == "occurrence" else model.predict(sample)
    valid = bool(np.isfinite(pred).all()) if model.task != "cause" else bool(np.isin(pred, ["REL", "CNF", "ENE"]).all())
    if model.task == "occurrence":
        valid = valid and bool(((pred >= 0) & (pred <= 1)).all())
    if model.task == "volume":
        valid = valid and bool((pred >= 0).all())
    if model.task == "cause":
        probabilities = model.predict_cause_proba(sample)
        valid = valid and bool(np.isfinite(probabilities).all()) and bool(np.allclose(probabilities.sum(axis=1), 1))
    models.append({"model": path.name, "deserialized": True, "prediction_contract": valid, "rows": len(pred), "effective_params": model.estimator.get_params(), "iterations": np.asarray(getattr(model.estimator, "n_iter_", [])).tolist()})
result = {"checksums": checks, "coverage": coverage, "models": models, "bytes_on_disk": sum(p.stat().st_size for p in run.rglob("*") if p.is_file()), "selection_metrics_emitted": False, "all_checks_pass": all(checks.values()) and len(models) == 8 and all(m["prediction_contract"] for m in models)}
with output.open("x", encoding="utf-8") as handle:
    json.dump(result, handle, indent=2, ensure_ascii=False, default=str)
print(json.dumps({k: v for k,v in result.items() if k != "models"}, default=str, ensure_ascii=False))
raise SystemExit(0 if result["all_checks_pass"] else 1)
