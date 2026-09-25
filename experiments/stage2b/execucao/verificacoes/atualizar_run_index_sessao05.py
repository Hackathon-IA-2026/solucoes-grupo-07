"""Atualiza execucao/run-index.json com os fatos da auditoria auditoria-runs-2b-001 (sessão 05)."""

import json
import shutil
from datetime import datetime
from pathlib import Path

EXE = Path("Y:/CurtaMap Etapa 2B/execucao")
INDEX = EXE / "run-index.json"
AUDIT = EXE / "verificacoes" / "auditoria-runs-2b-001.json"
BACKUP = EXE / "verificacoes" / "run-index.pre-sessao05.json"

idx = json.loads(INDEX.read_text(encoding="utf-8"))
audit = json.loads(AUDIT.read_text(encoding="utf-8"))
if not BACKUP.exists():
    shutil.copy2(INDEX, BACKUP)

AUDIT_REL = "execucao/verificacoes/auditoria-runs-2b-001.json"


def evidence(step, extra):
    base = {
        "step_id": extra.pop("step_id"),
        "exit_code": step["exit_code"],
        "duration_seconds": step["duration_seconds"],
        "started_at": step["started_at"],
        "finished_at": step["finished_at"],
        "peak_tree_working_set_bytes_sampled": step["peak_tree_working_set_bytes_sampled"],
        "peak_process_working_set_bytes": step["peak_process_working_set_bytes"],
        "git_status_short_empty": step["git_status_short"] == "",
        "stderr_bytes": step["stderr_bytes"],
        "audit": AUDIT_REL,
    }
    base.update(extra)
    return base


runs = {r["run_id"]: r for r in idx["runs"]}

for run_id, a in audit["main"].items():
    ex = a["execution"] or {}
    r = runs[run_id] if run_id in runs else {"run_id": run_id}
    r.update(
        {
            "kind": "campanha_principal",
            "source": a["source"],
            "scenario": "noturno_dia_util",
            "round": a["round"],
            "frozen_from": None,
            "status": "concluida",
            "reason": "exit 0; manifest complete; failures=[]; checksums 54/54 recalculados; validação completa",
            "code_commit": a["manifest_code_commit"],
            "step_id": run_id,
            "technical_evidence": evidence(
                a["step"],
                {
                    "step_id": run_id,
                    "report": f"experimentos/{run_id}/reports/{a['reports'][0]}",
                    "manifest_status": a["manifest_status"],
                    "failures": a["failures"],
                    "validation_rows": ex.get("validation_rows"),
                    "validation_rows_equal_measured_population": True,
                    "peak_rss_bytes_report": ex.get("peak_rss_bytes"),
                    "fit_seconds_total": round(a["fit_seconds_total"], 1),
                    "training_sampling": (a["training_sampling"] or {}).get("method"),
                    "tuning_calibration_rows_equal_measured": True,
                    "checksums_files": a["checksums"]["files_listed"],
                    "checksums_ok": a["checksums"]["ok"],
                    "bytes_listed": a["checksums"]["bytes_listed"],
                    "stderr_content": "8 avisos LGBMDeprecationWarning(eval_set) + marcadores de fase",
                },
            ),
        }
    )
    runs[run_id] = r

runs["main-eolica-v1-002"]["technical_evidence"]["stderr_content"] = (
    "8 avisos LGBMDeprecationWarning(eval_set); sem marcadores de fase (código 560ae70)"
)
runs["main-eolica-v1-002"]["reason"] += "; rodou em 560ae70, antes da otimização de métricas c73302e"

attempt_reasons = {
    "main-eolica-v1-001": (
        "interrompida_pelo_agente",
        "máscara de amostragem sem pushdown; 41-46 GB comprometidos e thrashing; corrigido em 560ae70",
    ),
    "main-eolica-v2-001": (
        "falha_preflight",
        "exit 1 em 30,4 s: worktree na branch execucao/fila-2b, preflight exige etapa-2-experimental; sem manifest",
    ),
    "main-eolica-v2-002": (
        "cancelada_pelo_responsavel",
        "cancelada às 02h22 de 24/09 para reinício com a otimização de métricas c73302e; artefatos parciais preservados",
    ),
    "main-eolica-v2-003": (
        "desaparecida_sem_end_json",
        "árvore encerrada ~02h27 de 24/09 junto com a atualização forçada do app Codex (hipótese fortemente sustentada); "
        "manifest permanece 'running' por não ser reescrito; INTERRUPCAO.txt no passo",
    ),
}
for run_id, (status, reason) in attempt_reasons.items():
    a = audit["attempts"][run_id]
    r = runs.get(run_id, {"run_id": run_id})
    r.update(
        {
            "kind": "campanha_principal",
            "source": "eolica",
            "scenario": "noturno_dia_util",
            "round": run_id.split("-")[2].upper(),
            "frozen_from": None,
            "status": status,
            "reason": reason,
            "code_commit": a["step"]["code_commit"],
            "step_id": run_id,
            "attempt_evidence": {
                "exit_code": a["step"]["exit_code"],
                "duration_seconds": a["step"]["duration_seconds"],
                "manifest_status_as_written": a["manifest_status_as_written"],
                "files_in_run_dir": a["files_in_run_dir"],
                "usable_as_result": False,
            },
        }
    )
    runs[run_id] = r

for run_id, a in audit["sensitivity"].items():
    ex = a["execution"] or {}
    r = runs[run_id]
    r.update(
        {
            "frozen_from": a["expected_frozen_run"],
            "status": "concluida",
            "reason": "exit 0; manifest complete; failures=[]; 8 modelos congelados com SHA-256 e limiares iguais aos da run principal; sem retreino",
            "code_commit": a["manifest_code_commit"],
            "step_id": run_id,
            "technical_evidence": evidence(
                a["step"],
                {
                    "step_id": run_id,
                    "report": f"experimentos/{run_id}/reports/{a['reports'][0]}",
                    "manifest_status": a["manifest_status"],
                    "failures": a["failures"],
                    "validation_rows": ex.get("validation_rows"),
                    "frozen_models_ok": a["frozen_all_ok"],
                    "models_dir_in_run": a["has_models_dir"],
                    "checksums_files": a["checksums"]["files_listed"],
                    "checksums_ok": a["checksums"]["ok"],
                    "bytes_listed": a["checksums"]["bytes_listed"],
                },
            ),
        }
    )

pilot = runs["pilot-fotovoltaica-001"]
pilot.update(
    {
        "status": "dispensada",
        "reason": "dispensada pela decisão de contingência de 23/09: a primeira campanha solar exerce o mesmo caminho técnico com a população real",
    }
)

order = [
    "pilot-eolica-001",
    "pilot-fotovoltaica-001",
    "main-eolica-v1-001",
    "main-eolica-v1-002",
    "main-eolica-v2-001",
    "main-eolica-v2-002",
    "main-eolica-v2-003",
    "main-eolica-v2-004",
    "main-eolica-v3-001",
    "main-eolica-v4-001",
    "main-fotovoltaica-v1-001",
    "main-fotovoltaica-v2-001",
    "main-fotovoltaica-v3-001",
    "main-fotovoltaica-v4-001",
    "delay-eolica-v1-001",
    "delay-eolica-v2-001",
    "delay-eolica-v3-001",
    "delay-eolica-v4-001",
    "delay-fotovoltaica-v1-001",
    "delay-fotovoltaica-v2-001",
    "delay-fotovoltaica-v3-001",
    "delay-fotovoltaica-v4-001",
]
assert set(order) == set(runs), set(runs) ^ set(order)
idx["runs"] = [runs[k] for k in order]

ds = audit["datasets"]
for source, parts, emissions, first in (
    ("eolica", 941, 7069236, "2023-10-03"),
    ("fotovoltaica", 758, 2379042, "2024-04-03"),
):
    gen = ds[f"features-noturno_mais_24h-{source}-development-001"]
    chk = ds[f"check-noturno_mais_24h-{source}-001"]
    entry = {
        "source": source,
        "scenario": "noturno_mais_24h",
        "round": "development",
        "generation_code_commit": "88634ed",
        "generation_step": f"features-noturno_mais_24h-{source}-development-001",
        "generation_status": "concluida",
        "generation_seconds": gen["duration_seconds"],
        "contract_status": "aprovado",
        "partitions": parts,
        "first_partition": first,
        "emissions": emissions,
        "verification_step": f"check-noturno_mais_24h-{source}-001",
        "verification_code_commit": "88634ed64b228e67aef3a3a187d9123a223b975f",
        "verification_report": f"execucao/verificacoes/dataset-noturno_mais_24h-{source}-001.json",
        "verification_seconds": chk["duration_seconds"],
        "checks_passed": "18/18",
    }
    idx["datasets"] = [
        d for d in idx["datasets"] if not (d["source"] == source and d["scenario"] == "noturno_mais_24h")
    ] + [entry]

idx["queue"] = {
    "script": "execucao/fila/fila-2b.ps1",
    "log": "execucao/fila/fila.log",
    "final_event": "2026-09-24T20:11:47 fila concluída com sucesso",
    "executor_worktree": "removido na sessão 05 após a fila; recriar antes de relançar (ver handoff)",
    "scheduled_task": "CurtaMap-Fila-2B (Agendador de Tarefas, sem gatilho automático)",
}
idx["audit_sessao05"] = {
    "step_id": "auditoria-runs-2b-001",
    "report": AUDIT_REL,
    "script": "execucao/verificacoes/auditar_runs_2b.py",
    "result": "8/8 principais e 8/8 sensibilidades com checksums íntegros; 8/8 sensibilidades congeladas sem retreino",
}
idx["updated_at"] = datetime.now().astimezone().isoformat()
INDEX.write_text(json.dumps(idx, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("run-index atualizado:", len(idx["runs"]), "runs")
