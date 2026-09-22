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
