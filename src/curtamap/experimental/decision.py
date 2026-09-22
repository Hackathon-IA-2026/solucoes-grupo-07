from __future__ import annotations

from typing import Any

REQUIRED_ROUNDS = ("V1", "V2", "V3", "V4")
FATAL_FAILURES = {
    "vazamento",
    "falha_reproducao",
    "falha_convergencia",
    "previsao_invalida",
    "metricas_ausentes",
}


def assess_candidate(
    task: str,
    rounds: dict[str, dict[str, float]],
    *,
    weekly_interval: tuple[float, float] | None = None,
    failures: list[str] | None = None,
) -> dict[str, Any]:
    """Aplica critérios pré-definidos sem converter elegibilidade em seleção final."""
    failures = failures or []
    reasons: list[str] = []
    missing = [round_id for round_id in REQUIRED_ROUNDS if round_id not in rounds]
    if missing:
        return {
            "status": "inconclusivo",
            "reasons": ["rodadas_ausentes:" + ",".join(missing)],
            "final_selection": False,
        }
    if FATAL_FAILURES.intersection(failures):
        return {
            "status": "inelegivel",
            "reasons": sorted(FATAL_FAILURES.intersection(failures)),
            "final_selection": False,
        }

    ordered = [rounds[round_id] for round_id in REQUIRED_ROUNDS]
    candidate = [row["candidate_primary"] for row in ordered]
    baseline = [row["baseline_primary"] for row in ordered]
    if any(value is None for value in [*candidate, *baseline]):
        return {
            "status": "inconclusivo",
            "reasons": ["metrica_primaria_ausente"],
            "final_selection": False,
        }

    if task in {"occurrence", "cause"}:
        differences = [left - right for left, right in zip(candidate, baseline, strict=True)]
        average_improvement = sum(differences) / 4
        material = average_improvement >= 0.02
        improved_rounds = sum(value > 0 for value in differences)
        if any(value < -0.02 for value in differences):
            reasons.append("piora_primaria_em_rodada")
        if task == "occurrence":
            brier_differences = [row["candidate_brier"] - row["baseline_brier"] for row in ordered]
            if any(value > 0.01 for value in brier_differences):
                reasons.append("piora_brier")
    elif task == "volume":
        differences = [left - right for left, right in zip(candidate, baseline, strict=True)]
        baseline_average = sum(baseline) / 4
        average_improvement = (
            (baseline_average - sum(candidate) / 4) / baseline_average
            if baseline_average > 0
            else float("-inf")
        )
        wape_candidate = sum(row["candidate_wape"] for row in ordered) / 4
        wape_baseline = sum(row["baseline_wape"] for row in ordered) / 4
        material = average_improvement >= 0.05 and wape_candidate <= wape_baseline
        improved_rounds = sum(left < right for left, right in zip(candidate, baseline, strict=True))
        if any(left > right * 1.1 for left, right in zip(candidate, baseline, strict=True)):
            reasons.append("piora_primaria_em_rodada")
        if wape_candidate > wape_baseline:
            reasons.append("piora_wape")
    else:
        raise ValueError(f"tarefa desconhecida: {task}")

    if not material:
        reasons.append("margem_material_nao_atingida")
    if improved_rounds < 3:
        reasons.append("menos_de_tres_rodadas_melhores")
    if weekly_interval is None:
        reasons.append("incerteza_ausente")
    elif weekly_interval[0] <= 0 <= weekly_interval[1]:
        reasons.append("incerteza_inclui_zero")

    protections = {
        "piora_primaria_em_rodada",
        "piora_brier",
        "piora_wape",
        "incerteza_inclui_zero",
        "incerteza_ausente",
    }
    eligible = material and improved_rounds >= 3 and not protections.intersection(reasons)
    return {
        "status": "elegivel_para_decisao_2c" if eligible else "requer_analise",
        "task": task,
        "average_improvement": average_improvement,
        "material_margin_met": material,
        "improved_rounds": improved_rounds,
        "reasons": reasons,
        "final_selection": False,
    }
