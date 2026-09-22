"""Implementação original (commit e389332) de features e baselines, preservada como oráculo.

Cópia literal de ``curtamap.experimental.features`` e ``curtamap.experimental.baselines``
antes da vetorização. Serve apenas para testes de igualdade semântica; é lenta demais
para gerar os datasets reais. Não altere: qualquer divergência intencional deve ser
documentada no teste que a exerce.
"""

from __future__ import annotations

import math
import statistics
from datetime import datetime, timedelta
from typing import Any

import polars as pl

from curtamap.experimental.data import history_eligibility
from curtamap.experimental.temporal import build_horizons


def _mean(values: list[float | int | bool | None]) -> float | None:
    valid = [float(value) for value in values if value is not None]
    return sum(valid) / len(valid) if valid else None


def _window(rows: list[dict[str, Any]], t0: datetime, days: int) -> list[dict[str, Any]]:
    start = t0 - timedelta(days=days)
    return [row for row in rows if start <= row["din_instante"] < t0]


def _episode_length(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    length = 0
    expected = rows[-1]["din_instante"]
    for row in reversed(rows):
        if row["din_instante"] != expected or row["corte_positivo"] is not True:
            break
        length += 1
        expected -= timedelta(minutes=30)
    return length


def _regional_frequency(
    history: list[dict[str, Any]], field: str, value: Any, t0: datetime
) -> float | None:
    rows = [row for row in _window(history, t0, 28) if row[field] == value]
    return _mean([row["corte_positivo"] for row in rows])


def _last_time(rows: list[dict[str, Any]], field: str) -> datetime | None:
    return next((row["din_instante"] for row in reversed(rows) if row[field] is True), None)


def build_feature_batch(source: pl.DataFrame, t0: datetime) -> pl.DataFrame:
    """Constrói um lote de emissão sem materializar o snapshot inteiro em pandas.

    ``source`` contém história e verdade posterior. Somente linhas com ``disponivel_em <= t0``
    alimentam features/cadastro; a verdade futura é consultada exclusivamente para os alvos.
    """
    if not source["fonte"].n_unique() == 1:
        raise ValueError("cada lote deve conter uma única fonte")
    available = source.filter(
        (pl.col("disponivel_em") <= t0) & (pl.col("din_instante") + timedelta(minutes=30) <= t0)
    ).sort("id_ons", "din_instante")
    if available.is_empty():
        return pl.DataFrame()
    history = available.to_dicts()
    full_lookup = {
        (row["fonte"], row["id_ons"], row["din_instante"]): row for row in source.to_dicts()
    }
    by_entity: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in history:
        by_entity.setdefault((row["fonte"], row["id_ons"]), []).append(row)
    eligibility = {
        (row["fonte"], row["id_ons"]): row for row in history_eligibility(available, t0).to_dicts()
    }
    records: list[dict[str, Any]] = []
    for (fonte, id_ons), entity_history in sorted(by_entity.items()):
        metadata = entity_history[-1]
        eligible = eligibility.get((fonte, id_ons), {})
        by_time = {row["din_instante"]: row for row in entity_history}
        last = entity_history[-1]
        windows = {days: _window(entity_history, t0, days) for days in (1, 7, 28)}
        positives_28d = [
            row["volume_mwmed"]
            for row in windows[28]
            if row["volume_valido"] and row["volume_mwmed"] is not None
        ]
        last_positive_time = _last_time(entity_history, "corte_positivo")
        last_restriction_time = _last_time(entity_history, "restricao_registrada")
        for horizon in build_horizons(t0):
            tau = horizon.start
            target = full_lookup.get((fonte, id_ons, tau))
            row: dict[str, Any] = {
                "fonte": fonte,
                "id_ons": id_ons,
                "id_estado": metadata["id_estado"],
                "id_subsistema": metadata["id_subsistema"],
                "ceg_level": "conjunto" if metadata["ceg"] == "-" else "individual",
                "t0": t0,
                "tau": tau,
                "horizon": horizon.horizon,
                "t0_hour_sin": math.sin(2 * math.pi * (t0.hour * 2 + t0.minute // 30) / 48),
                "t0_hour_cos": math.cos(2 * math.pi * (t0.hour * 2 + t0.minute // 30) / 48),
                "tau_hour_sin": math.sin(2 * math.pi * (tau.hour * 2 + tau.minute // 30) / 48),
                "tau_hour_cos": math.cos(2 * math.pi * (tau.hour * 2 + tau.minute // 30) / 48),
                "tau_weekday": tau.weekday(),
                "tau_month": tau.month,
                "tau_day_of_year": tau.timetuple().tm_yday,
                "t0_weekday": t0.weekday(),
                "t0_month": t0.month,
                "t0_day_of_year": t0.timetuple().tm_yday,
                "last_positive": last["corte_positivo"],
                "last_restriction": last["restricao_registrada"],
                "last_volume_mwmed": last["volume_mwmed"] if last["volume_valido"] else None,
                "last_cause": last["causa"],
                "observed_episode_length": _episode_length(entity_history),
                "history_coverage_28d": eligible.get("coverage", 0.0),
                "eligible_history": eligible.get("eligible", False),
                "history_age_hours": (t0 - last["din_instante"]).total_seconds() / 3600,
                "hours_since_positive": (
                    (t0 - last_positive_time).total_seconds() / 3600 if last_positive_time else None
                ),
                "hours_since_restriction": (
                    (t0 - last_restriction_time).total_seconds() / 3600
                    if last_restriction_time
                    else None
                ),
                "positive_frequency_24h": _mean([item["corte_positivo"] for item in windows[1]]),
                "positive_frequency_7d": _mean([item["corte_positivo"] for item in windows[7]]),
                "positive_frequency_28d": _mean([item["corte_positivo"] for item in windows[28]]),
                "mean_volume_28d": _mean(positives_28d),
                "std_volume_28d": (
                    statistics.pstdev(positives_28d) if len(positives_28d) >= 2 else None
                ),
                "max_volume_28d": max(positives_28d) if positives_28d else None,
                "restriction_frequency_28d": _mean(
                    [item["restricao_registrada"] for item in windows[28]]
                ),
                "state_positive_frequency_28d": _regional_frequency(
                    history, "id_estado", metadata["id_estado"], t0
                ),
                "subsystem_positive_frequency_28d": _regional_frequency(
                    history, "id_subsistema", metadata["id_subsistema"], t0
                ),
                "target_observed": target is not None,
                "true_restriction": target["restricao_registrada"] if target else None,
                "true_positive": target["corte_positivo"] if target else None,
                "true_volume_mwmed": target["volume_mwmed"] if target else None,
                "true_volume_valid": target["volume_valido"] if target else None,
                "true_cause": target["causa"] if target else None,
                "target_available_at": target["disponivel_em"] if target else None,
            }
            known_causes = [
                item["causa"] for item in windows[28] if item["causa"] in ("REL", "CNF", "ENE")
            ]
            for cause in ("REL", "CNF", "ENE"):
                row[f"cause_{cause.lower()}_share_28d"] = (
                    known_causes.count(cause) / len(known_causes) if known_causes else None
                )
            for days in (1, 7):
                volumes = [
                    item["volume_mwmed"]
                    for item in windows[days]
                    if item["volume_valido"] and item["volume_mwmed"] is not None
                ]
                row[f"mean_volume_{'24h' if days == 1 else '7d'}"] = _mean(volumes)
                row[f"std_volume_{'24h' if days == 1 else '7d'}"] = (
                    statistics.pstdev(volumes) if len(volumes) >= 2 else None
                )
                row[f"max_volume_{'24h' if days == 1 else '7d'}"] = (
                    max(volumes) if volumes else None
                )
            for days in (1, 2, 3, 7):
                past = by_time.get(tau - timedelta(days=days))
                row[f"same_hour_{days}d_positive"] = (
                    past["corte_positivo"] if past is not None else None
                )
                row[f"same_hour_{days}d_volume"] = (
                    past["volume_mwmed"] if past is not None and past["volume_valido"] else None
                )
            for label, offset in {
                "30m": timedelta(minutes=30),
                "1h": timedelta(hours=1),
                "24h": timedelta(hours=24),
                "48h": timedelta(hours=48),
                "7d": timedelta(days=7),
            }.items():
                past = by_time.get(last["din_instante"] - offset)
                row[f"history_{label}_positive"] = (
                    past["corte_positivo"] if past is not None else None
                )
                row[f"history_{label}_volume"] = (
                    past["volume_mwmed"] if past is not None and past["volume_valido"] else None
                )
            records.append(row)
    return pl.DataFrame(records, infer_schema_length=None).sort("fonte", "id_ons", "t0", "horizon")


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
