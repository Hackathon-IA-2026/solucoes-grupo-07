"""Matriz de decisão da Etapa 2C a partir das métricas já gravadas pela Etapa 2B.

Somente leitura sobre `experiments/stage2b/experimentos`. Não lê previsões Parquet, não treina
e não toca no teste reservado. Os critérios do §11 vêm de `curtamap.experimental.decision`
(testado); este script só organiza rodadas, escolhe o comparador único e grava o resultado.

Uso: uv run python scripts/stage2c/analisar_matriz_2c.py [saida.json]
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

from curtamap.experimental.decision import assess_candidate

ROOT = Path(__file__).resolve().parents[2]
EXP = ROOT / "experiments" / "stage2b" / "experimentos"
DEFAULT_OUTPUT = ROOT / "docs" / "reports" / "stage2c" / "matriz-2c.json"
ROUNDS = ("V1", "V2", "V3", "V4")
MAIN = {
    ("eolica", "V1"): "main-eolica-v1-002",
    ("eolica", "V2"): "main-eolica-v2-004",
    ("eolica", "V3"): "main-eolica-v3-001",
    ("eolica", "V4"): "main-eolica-v4-001",
    **{("fotovoltaica", r): f"main-fotovoltaica-v{r[1]}-001" for r in ROUNDS},
}
DELAY = {(s, r): f"delay-{s}-v{r[1]}-001" for s in ("eolica", "fotovoltaica") for r in ROUNDS}
BASELINES = ("ultimo_valor", "mesmo_horario_dia_anterior", "mesmo_horario_recente", "historico")
# Regras de causa que não seguem o §7.2 (baselines.py usa a última causa da entidade sempre
# que a linha direta existe); ficam reportadas, mas fora da escolha do comparador.
NONCONFORMING_CAUSE_BASELINES = ("mesmo_horario_dia_anterior", "mesmo_horario_recente")
TASKS = {
    "corte_positivo": {
        "kind": "occurrence",
        "primary": "average_precision",
        "higher": True,
        "candidates": ("corte_positivo-linear", "corte_positivo-lightgbm"),
        "baseline_task": "corte_positivo",
    },
    "restricao_registrada": {
        "kind": "occurrence",
        "primary": "average_precision",
        "higher": True,
        "candidates": ("restricao_registrada-linear", "restricao_registrada-lightgbm"),
        "baseline_task": "restricao_registrada",
    },
    "volume": {
        "kind": "volume",
        "primary": "mae_full",
        "higher": False,
        "candidates": tuple(
            f"volume-{a}-{b}" for a in ("linear", "lightgbm") for b in ("linear", "lightgbm")
        ),
        "diagnostics": ("volume_condicional-linear", "volume_condicional-lightgbm"),
        "baseline_task": "volume_pipeline",
    },
    "causa": {
        "kind": "cause",
        "primary": "macro_f1",
        "higher": True,
        "candidates": ("causa-linear", "causa-lightgbm"),
        "baseline_task": "causa",
    },
}
DIAGNOSTIC_SLICES = (
    "faixa_horizonte:0_6h",
    "faixa_horizonte:6_12h",
    "faixa_horizonte:12_24h",
    "historico_insuficiente",
    "painel_fixo",
    "fim_semana_feriado",
    "idade:ate_48h",
    "idade:48_96h",
    "idade:acima_96h",
    "cauda_volume_p99_treino",
    "fora_cauda_volume",
)


def _value(metrics: dict, name: str) -> float | None:
    entry = metrics.get(name)
    if isinstance(entry, dict):
        return entry.get("value")
    return entry


def _slices(path: Path) -> dict[str, dict]:
    return {row["slice"]: row["metrics"] for row in json.loads(path.read_text(encoding="utf-8"))}


def _load(source: str, round_id: str, identity: str, *, delay: bool = False) -> dict | None:
    run = (DELAY if delay else MAIN)[(source, round_id)]
    prefix = "sensitivity-" if delay else ""
    path = EXP / run / "metrics" / f"{prefix}{source}-{round_id}-{identity}.json"
    return _slices(path) if path.exists() else None


def _summary(values: list[float | None]) -> dict:
    present = [v for v in values if v is not None]
    if len(present) != len(values):
        return {"per_round": values, "mean": None, "missing_rounds": len(values) - len(present)}
    return {
        "per_round": values,
        "mean": statistics.fmean(present),
        "sd_sample": statistics.stdev(present),
        "min": min(present),
        "max": max(present),
    }


def _extract(slices: dict | None, primary: str, slice_id: str = "global") -> dict:
    metrics = (slices or {}).get(slice_id)
    if metrics is None:
        return {"primary": None, "brier": None, "wape": None, "support": None}
    return {
        "primary": _value(metrics, primary),
        "brier": _value(metrics, "brier"),
        "wape": _value(metrics, "wape"),
        "support": metrics.get("support"),
    }


def _origin_rounds(source: str, task: dict, identity: str, *, delay: bool = False) -> dict:
    rounds = {}
    for round_id in ROUNDS:
        rounds[round_id] = _extract(_load(source, round_id, identity, delay=delay), task["primary"])
    return rounds


def _choose_comparator(baselines: dict, task: dict, allowed: tuple[str, ...]) -> str:
    means = {name: baselines[name]["primary"]["mean"] for name in allowed}
    pick = max if task["higher"] else min
    # Empate numérico exato: vale a ordem fixa de BASELINES (a mais simples primeiro).
    return pick(allowed, key=lambda name: (means[name], -allowed.index(name)))


def _paired(candidate: dict, comparator: dict, higher: bool) -> list[float]:
    differences = []
    for round_id in ROUNDS:
        left, right = candidate[round_id]["primary"], comparator[round_id]["primary"]
        differences.append(left - right if higher else (right - left) / right)
    return differences


def _decision_rows(candidate: dict, comparator: dict) -> dict:
    return {
        round_id: {
            "candidate_primary": candidate[round_id]["primary"],
            "baseline_primary": comparator[round_id]["primary"],
            "candidate_brier": candidate[round_id]["brier"],
            "baseline_brier": comparator[round_id]["brier"],
            "candidate_wape": candidate[round_id]["wape"],
            "baseline_wape": comparator[round_id]["wape"],
        }
        for round_id in ROUNDS
    }


def _slice_means(source: str, identity: str, primary: str) -> dict:
    result = {}
    for slice_id in DIAGNOSTIC_SLICES:
        values = [
            _extract(_load(source, r, identity), primary, slice_id)["primary"] for r in ROUNDS
        ]
        result[slice_id] = _summary(values)
    return result


def analyse_cell(source: str, task_id: str) -> dict:
    task = TASKS[task_id]
    baselines = {}
    for name in BASELINES:
        rounds = _origin_rounds(source, task, f"baseline-{name}-{task['baseline_task']}")
        baselines[name] = {
            "rounds": rounds,
            "primary": _summary([rounds[r]["primary"] for r in ROUNDS]),
            "brier": _summary([rounds[r]["brier"] for r in ROUNDS]),
            "wape": _summary([rounds[r]["wape"] for r in ROUNDS]),
        }
    comparator_all = _choose_comparator(baselines, task, BASELINES)
    allowed = (
        tuple(b for b in BASELINES if b not in NONCONFORMING_CAUSE_BASELINES)
        if task_id == "causa"
        else BASELINES
    )
    comparator = _choose_comparator(baselines, task, allowed)
    comparator_rounds = baselines[comparator]["rounds"]

    candidates = {}
    identities = (*task["candidates"], *task.get("diagnostics", ()))
    for identity in identities:
        rounds = _origin_rounds(source, task, identity)
        delayed = _origin_rounds(source, task, identity, delay=True)
        entry = {
            "role": "diagnostico" if identity in task.get("diagnostics", ()) else "candidato",
            "rounds": rounds,
            "primary": _summary([rounds[r]["primary"] for r in ROUNDS]),
            "brier": _summary([rounds[r]["brier"] for r in ROUNDS]),
            "wape": _summary([rounds[r]["wape"] for r in ROUNDS]),
            "delay_primary": _summary([delayed[r]["primary"] for r in ROUNDS]),
            "slices": _slice_means(source, identity, task["primary"]),
        }
        if entry["role"] == "candidato":
            entry["paired_vs_comparator"] = _paired(rounds, comparator_rounds, task["higher"])
            entry["criteria_2b_module"] = assess_candidate(
                task["kind"], _decision_rows(rounds, comparator_rounds), weekly_interval=None
            )
        candidates[identity] = entry
    return {
        "source": source,
        "task": task_id,
        "primary_metric": task["primary"],
        "comparator": comparator,
        "comparator_if_all_baselines_allowed": comparator_all,
        "comparator_slices": _slice_means(
            source, f"baseline-{comparator}-{task['baseline_task']}", task["primary"]
        ),
        "baselines": baselines,
        "candidates": candidates,
    }


def _costs() -> dict:
    costs = {}
    runs = [(key, run, "main") for key, run in MAIN.items()]
    runs += [(key, run, "delay") for key, run in DELAY.items()]
    for (source, round_id), run, kind in runs:
        name = f"sensitivity-{source}-{round_id}" if kind == "delay" else f"{source}-{round_id}"
        report_path = EXP / run / "reports" / f"{name}.json"
        if not report_path.exists():
            report_path = next((EXP / run / "reports").glob("*.json"))
        report = json.loads(report_path.read_text(encoding="utf-8"))
        manifest = json.loads((EXP / run / "manifest.json").read_text(encoding="utf-8"))
        models = report.get("models", {})
        costs[run] = {
            "status": manifest["status"],
            "code_commit": manifest["code_commit"][:7],
            "failures": report.get("failures"),
            "peak_rss_gib": report["execution"]["peak_rss_bytes"] / 2**30
            if report.get("execution", {}).get("peak_rss_bytes")
            else None,
            "fit_seconds": {k: v.get("fit_seconds") for k, v in models.items()},
            "selected_params": {k: v.get("selected_params") for k, v in models.items()},
            "training_rows": report.get("training_rows"),
            "validation_rows": report.get("execution", {}).get("validation_rows"),
        }
    return costs


def main(output: Path) -> int:
    result = {
        "note": (
            "Gerado por scripts/stage2c/analisar_matriz_2c.py a partir dos JSON de métricas da "
            "2B. Recorte global para o §11; recortes adicionais são diagnósticos. A incerteza "
            "semanal não foi calculada (weekly_interval=None), por isso todo candidato recebe "
            "o motivo incerteza_ausente do módulo de decisão."
        ),
        "cells": [
            analyse_cell(source, task_id)
            for source in ("eolica", "fotovoltaica")
            for task_id in TASKS
        ],
        "runs": _costs(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    for cell in result["cells"]:
        print(f"== {cell['source']} {cell['task']} comparador={cell['comparator']}")
        base = cell["baselines"][cell["comparator"]]["primary"]
        print(f"   comparador média={base['mean']:.4f} por rodada={base['per_round']}")
        for identity, entry in cell["candidates"].items():
            mean = entry["primary"]["mean"]
            criteria = entry.get("criteria_2b_module", {})
            print(
                f"   {identity:32s} média={mean:.4f} "
                f"dif={[round(d, 4) for d in entry.get('paired_vs_comparator', [])]} "
                f"{criteria.get('status', entry['role'])} {criteria.get('reasons', '')}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT))
