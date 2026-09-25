"""Auditoria única das runs da Etapa 2B após a fila (sessão 05).

Somente leitura sobre `experimentos/` e `execucao/passos/`. Grava um JSON com:
passo (exit, duração, picos, commit), manifest, relatório (falhas, execução, amostragem,
linhas de treino), checksums recalculados, congelamento das sensibilidades e comparação
das linhas/prevalências de treino contra as populações medidas.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path("Y:/CurtaMap Etapa 2B")
EXP = ROOT / "experimentos"
STEPS = ROOT / "execucao" / "passos"
MEAS = ROOT / "execucao" / "medicoes"

MAIN = {
    ("eolica", "V1"): "main-eolica-v1-002",
    ("eolica", "V2"): "main-eolica-v2-004",
    ("eolica", "V3"): "main-eolica-v3-001",
    ("eolica", "V4"): "main-eolica-v4-001",
    ("fotovoltaica", "V1"): "main-fotovoltaica-v1-001",
    ("fotovoltaica", "V2"): "main-fotovoltaica-v2-001",
    ("fotovoltaica", "V3"): "main-fotovoltaica-v3-001",
    ("fotovoltaica", "V4"): "main-fotovoltaica-v4-001",
}
ATTEMPTS = ["main-eolica-v1-001", "main-eolica-v2-001", "main-eolica-v2-002", "main-eolica-v2-003"]
SLOTS = {
    "eolica": {"corte_positivo": 4, "restricao_registrada": 4, "volume_condicional": 14, "causa": 14},
    "fotovoltaica": {
        "corte_positivo": 16,
        "restricao_registrada": 16,
        "volume_condicional": 48,
        "causa": 48,
    },
}


def load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return None


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()


def step_info(step_id):
    d = STEPS / step_id
    start, end = load(d / "start.json"), load(d / "end.json")
    stderr = d / "stderr.log"
    lines = []
    if stderr.exists():
        lines = [x.strip() for x in stderr.read_text(encoding="utf-8", errors="replace").splitlines()]
    phases = [x for x in lines if x.startswith("[curtamap-fase]")]
    other = [x for x in lines if x and not x.startswith("[curtamap-fase]")]
    uniq = {}
    for x in other:
        key = x[:160]
        uniq[key] = uniq.get(key, 0) + 1
    return {
        "exists": d.exists(),
        "code_commit": start and start.get("code_commit"),
        "git_status_short": start and start.get("git_status_short"),
        "cwd": start and start.get("cwd"),
        "started_at": (end or start or {}).get("started_at"),
        "finished_at": end and end.get("finished_at"),
        "exit_code": end and end.get("exit_code"),
        "duration_seconds": end and end.get("duration_seconds"),
        "peak_tree_working_set_bytes_sampled": end and end.get("peak_tree_working_set_bytes_sampled"),
        "peak_process_working_set_bytes": end and end.get("peak_process_working_set_bytes"),
        "interrupted": (d / "INTERRUPCAO.txt").exists() or bool(end and end.get("interrupted_by_user")),
        "stderr_bytes": stderr.stat().st_size if stderr.exists() else None,
        "stderr_phase_markers": phases,
        "stderr_other_lines": len(other),
        "stderr_unique_other": [{"line": k, "count": v} for k, v in list(uniq.items())[:15]],
    }


def verify_checksums(run_dir):
    cs = load(run_dir / "checksums.json")
    if cs is None:
        return {"present": False}
    files = cs["files"]
    mismatched, missing = [], []
    total_bytes = 0
    for rel, expected in files.items():
        p = run_dir / rel
        if not p.exists():
            missing.append(rel)
            continue
        total_bytes += p.stat().st_size
        if sha256(p) != expected:
            mismatched.append(rel)
    on_disk = {
        p.relative_to(run_dir).as_posix()
        for p in run_dir.rglob("*")
        if p.is_file()
    }
    extra = sorted(on_disk - set(files) - {"checksums.json"})
    return {
        "present": True,
        "files_listed": len(files),
        "bytes_listed": total_bytes,
        "mismatched": mismatched,
        "missing": missing,
        "unlisted_on_disk": extra,
        "ok": not mismatched and not missing,
    }


def run_info(run_id, report_glob):
    d = EXP / run_id
    manifest = load(d / "manifest.json")
    reports = sorted((d / "reports").glob(report_glob)) if (d / "reports").exists() else []
    report = load(reports[0]) if reports else None
    return d, manifest, report, [p.name for p in reports]


def population_index(source):
    p = load(MEAS / f"populacoes-noturno_dia_util-{source}-001.json")
    return {(r["round"], r["segment"], r["task"]): r for r in p["populations"]}


def measured_mean(row, task):
    if not row or not row["rows"]:
        return None
    if task == "corte_positivo":
        return row["positive_rows"] / row["rows"]
    if task == "restricao_registrada":
        return row["restriction_rows"] / row["rows"]
    return None


def compare_training(source, rnd, training_rows, pops):
    out = []
    for task, segs in (training_rows or {}).items():
        for seg, val in segs.items():
            m = pops.get((rnd, seg, task))
            rows = val.get("rows")
            mrows = m and m["rows"]
            entry = {
                "task": task,
                "segment": seg,
                "rows_run": rows,
                "rows_measured": mrows,
                "ratio": (rows / mrows) if rows is not None and mrows else None,
                "expected_ratio": (SLOTS[source][task] / 48) if seg in ("initial", "refit") else 1.0,
                "target_mean_run": val.get("target_mean"),
                "target_mean_measured_full": measured_mean(m, task),
            }
            out.append(entry)
    return out


def main(out_path):
    result = {"main": {}, "sensitivity": {}, "attempts": {}}
    pops = {s: population_index(s) for s in ("eolica", "fotovoltaica")}
    main_reports = {}
    for (source, rnd), run_id in MAIN.items():
        d, manifest, report, names = run_info(run_id, f"{source}-{rnd}.json")
        main_reports[run_id] = report
        models = (report or {}).get("models", {})
        result["main"][run_id] = {
            "source": source,
            "round": rnd,
            "step": step_info(run_id),
            "manifest_status": manifest and manifest.get("status"),
            "manifest_code_commit": manifest and manifest.get("code_commit"),
            "data_hashes": manifest and manifest.get("data_hashes"),
            "configuration_sha256": manifest and manifest.get("configuration_sha256"),
            "bytes_consumed": manifest and manifest.get("bytes_consumed"),
            "reports": names,
            "failures": (report or {}).get("failures"),
            "execution": (report or {}).get("execution"),
            "boundaries": (report or {}).get("boundaries"),
            "training_sampling": (report or {}).get("training_sampling"),
            "fit_seconds_total": sum(m.get("fit_seconds") or 0 for m in models.values()),
            "models": {
                k: {
                    "fit_seconds": v.get("fit_seconds"),
                    "calibration_status": v.get("calibration_status"),
                    "threshold": v.get("threshold"),
                    "selected_params": v.get("selected_params"),
                }
                for k, v in models.items()
            },
            "training_vs_population": compare_training(
                source, rnd, (report or {}).get("training_rows"), pops[source]
            ),
            "checksums": verify_checksums(d),
        }
        print("main", run_id, result["main"][run_id]["checksums"].get("ok"), flush=True)

    for (source, rnd), main_id in MAIN.items():
        run_id = f"delay-{source}-{rnd.lower()}-001"
        d, manifest, report, names = run_info(run_id, f"sensitivity-{source}-{rnd}.json")
        main_cs = (load(EXP / main_id / "checksums.json") or {}).get("files", {})
        main_models = (main_reports.get(main_id) or {}).get("models", {})
        frozen = []
        for name, m in ((report or {}).get("models") or {}).items():
            fm = Path(m.get("frozen_model", ""))
            rel = f"models/{fm.name}"
            actual = sha256(fm) if fm.exists() else None
            ref = main_models.get(name, {})
            frozen.append(
                {
                    "model": name,
                    "frozen_model_in_main_run": fm.parent.parent.name == main_id,
                    "sha256_matches_main_checksums": actual is not None and actual == main_cs.get(rel),
                    "threshold_equal": m.get("threshold") == ref.get("threshold"),
                    "calibration_equal": m.get("calibration_status") == ref.get("calibration_status"),
                    "has_fit_seconds": "fit_seconds" in m,
                }
            )
        result["sensitivity"][run_id] = {
            "source": source,
            "round": rnd,
            "expected_frozen_run": main_id,
            "frozen_run": (report or {}).get("frozen_run"),
            "frozen_run_ok": Path((report or {}).get("frozen_run", "")).name == main_id,
            "step": step_info(run_id),
            "manifest_status": manifest and manifest.get("status"),
            "manifest_code_commit": manifest and manifest.get("code_commit"),
            "reports": names,
            "failures": (report or {}).get("failures"),
            "execution": (report or {}).get("execution"),
            "has_models_dir": (d / "models").exists(),
            "frozen_models": frozen,
            "frozen_all_ok": bool(frozen)
            and all(
                f["frozen_model_in_main_run"]
                and f["sha256_matches_main_checksums"]
                and f["threshold_equal"]
                and f["calibration_equal"]
                and not f["has_fit_seconds"]
                for f in frozen
            ),
            "checksums": verify_checksums(d),
        }
        print("delay", run_id, result["sensitivity"][run_id]["frozen_all_ok"], flush=True)

    for run_id in ATTEMPTS:
        d = EXP / run_id
        manifest = load(d / "manifest.json")
        result["attempts"][run_id] = {
            "step": step_info(run_id),
            "run_dir_exists": d.exists(),
            "manifest_status_as_written": manifest and manifest.get("status"),
            "manifest_code_commit": manifest and manifest.get("code_commit"),
            "files_in_run_dir": sum(1 for p in d.rglob("*") if p.is_file()) if d.exists() else 0,
        }

    for step_id in [
        "features-noturno_mais_24h-eolica-development-001",
        "check-noturno_mais_24h-eolica-001",
        "features-noturno_mais_24h-fotovoltaica-development-001",
        "check-noturno_mais_24h-fotovoltaica-001",
    ]:
        result.setdefault("datasets", {})[step_id] = step_info(step_id)

    Path(out_path).write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    print("gravado", out_path)


if __name__ == "__main__":
    main(sys.argv[1])
