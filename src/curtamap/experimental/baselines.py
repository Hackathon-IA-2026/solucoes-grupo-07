from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import polars as pl

CAUSE_ORDER = ("CNF", "ENE", "REL")
MINIMUM_GROUP_SUPPORT = 7


def _known_cause(value: Any) -> bool:
    return value in CAUSE_ORDER


def _majority(rows: list[dict[str, Any]]) -> tuple[str, dict[str, float]] | None:
    counts = {cause: 0 for cause in CAUSE_ORDER}
    for row in rows:
        if row["restricao_registrada"] and _known_cause(row["causa"]):
            counts[row["causa"]] += 1
    support = sum(counts.values())
    if support < MINIMUM_GROUP_SUPPORT:
        return None
    probabilities = {cause: counts[cause] / support for cause in CAUSE_ORDER}
    prediction = max(CAUSE_ORDER, key=lambda cause: (counts[cause], -CAUSE_ORDER.index(cause)))
    return prediction, probabilities


def _statistics(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    positive_valid = [r for r in rows if r["corte_positivo"] is not None]
    volume_valid = [r for r in rows if r["volume_valido"] and r["volume_mwmed"] is not None]
    if len(positive_valid) < MINIMUM_GROUP_SUPPORT or len(volume_valid) < MINIMUM_GROUP_SUPPORT:
        return None
    positives = [r for r in volume_valid if r["volume_mwmed"] > 0]
    positive_mean = (
        sum(r["volume_mwmed"] for r in positives) / len(positives)
        if len(positives) >= MINIMUM_GROUP_SUPPORT
        else None
    )
    probability = sum(bool(r["corte_positivo"]) for r in positive_valid) / len(positive_valid)
    cause = _majority(rows)
    return {
        "prob_positive": probability,
        "prob_restriction": sum(bool(r["restricao_registrada"]) for r in rows) / len(rows),
        "volume_positive_mean": positive_mean,
        "volume_expected": probability * positive_mean if positive_mean is not None else 0.0,
        "cause_prediction": cause[0] if cause else "CNF",
        "cause_probabilities": cause[1]
        if cause
        else {cause_name: 1 / 3 for cause_name in CAUSE_ORDER},
    }


def _uninformed() -> dict[str, Any]:
    return {
        "prob_positive": 0.5,
        "prob_restriction": 0.5,
        "volume_positive_mean": None,
        "volume_expected": 0.0,
        "cause_prediction": "CNF",
        "cause_probabilities": {cause: 1 / 3 for cause in CAUSE_ORDER},
    }


def _fallback(
    history: list[dict[str, Any]], request: dict[str, Any]
) -> tuple[dict[str, Any], str, datetime | None]:
    tau = request["tau"]
    hierarchy = (
        (
            "entidade_mesmo_horario",
            lambda r: r["id_ons"] == request["id_ons"] and r["din_instante"].time() == tau.time(),
        ),
        ("entidade_todos_horarios", lambda r: r["id_ons"] == request["id_ons"]),
        (
            "fonte_uf_mesmo_horario",
            lambda r: (
                r["id_estado"] == request["id_estado"] and r["din_instante"].time() == tau.time()
            ),
        ),
        ("fonte_mesmo_horario", lambda r: r["din_instante"].time() == tau.time()),
        ("fonte_todos_horarios", lambda _r: True),
    )
    for level, predicate in hierarchy:
        subset = [row for row in history if predicate(row)]
        stats = _statistics(subset)
        if stats is not None:
            return stats, level, max(row["din_instante"] for row in subset)
    return _uninformed(), "sem_evidencia", max((r["din_instante"] for r in history), default=None)


def _direct_values(row: dict[str, Any], cause_rows: list[dict[str, Any]]) -> dict[str, Any]:
    known_causes = [r for r in cause_rows if r["restricao_registrada"] and _known_cause(r["causa"])]
    cause = known_causes[-1]["causa"] if known_causes else "CNF"
    return {
        "prob_positive": float(row["corte_positivo"]) if row["corte_positivo"] is not None else 0.5,
        "prob_restriction": float(row["restricao_registrada"]),
        "volume_positive_mean": row["volume_mwmed"] if row["volume_mwmed"] > 0 else None,
        "volume_expected": row["volume_mwmed"] if row["volume_valido"] else 0.0,
        "cause_prediction": cause,
        "cause_probabilities": {name: float(name == cause) for name in CAUSE_ORDER},
    }


def generate_baselines(history: pl.DataFrame, requests: pl.DataFrame) -> pl.DataFrame:
    """Gera os quatro comparadores sem acessar observações não liberadas em ``t0``."""
    outputs: list[dict[str, Any]] = []
    all_history = history.sort("din_instante").to_dicts()
    for request in requests.to_dicts():
        t0, tau = request["t0"], request["tau"]
        lower = t0 - timedelta(days=28)
        available = [
            row
            for row in all_history
            if row["fonte"] == request["fonte"]
            and row["disponivel_em"] <= t0
            and row["din_instante"] + timedelta(minutes=30) <= t0
            and row["din_instante"] >= lower
        ]
        entity = [row for row in available if row["id_ons"] == request["id_ons"]]
        fallback, fallback_level, fallback_time = _fallback(available, request)

        choices: list[tuple[str, dict[str, Any] | None]] = [
            ("ultimo_valor", entity[-1] if entity else None),
            (
                "mesmo_horario_dia_anterior",
                next(
                    (r for r in reversed(entity) if r["din_instante"] == tau - timedelta(days=1)),
                    None,
                ),
            ),
            (
                "mesmo_horario_recente",
                next(
                    (
                        r
                        for r in reversed(entity)
                        if r["din_instante"].time() == tau.time() and r["din_instante"] < tau
                    ),
                    None,
                ),
            ),
            ("historico", None),
        ]
        for baseline_id, direct in choices:
            native = direct is not None or (
                baseline_id == "historico" and fallback_level != "sem_evidencia"
            )
            if baseline_id == "historico":
                values, source_time = fallback, fallback_time
                level = fallback_level
            elif direct is not None:
                values = _direct_values(direct, entity)
                source_time = direct["din_instante"]
                level = "nativo"
            else:
                values, source_time = fallback, fallback_time
                level = fallback_level
            outputs.append(
                request
                | {
                    "baseline_id": baseline_id,
                    "native_available": native,
                    "fallback_level": level,
                    "source_time": source_time,
                    "history_age_hours": (
                        (t0 - source_time).total_seconds() / 3600 if source_time else None
                    ),
                }
                | values
            )
    return pl.DataFrame(outputs, infer_schema_length=None)
