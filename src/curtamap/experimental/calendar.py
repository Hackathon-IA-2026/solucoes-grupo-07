from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from curtamap.experimental.temporal import BusinessCalendar


@dataclass(frozen=True)
class LoadedCalendar:
    calendar: BusinessCalendar
    sha256: str
    years: tuple[int, ...]
    sources: tuple[dict[str, Any], ...]
    entries: tuple[dict[str, Any], ...]


def load_calendar_manifest(path: Path) -> LoadedCalendar:
    payload = path.read_bytes()
    document = json.loads(payload)
    entries = tuple(document["entries"])
    days = frozenset(date.fromisoformat(entry["date"]) for entry in entries)
    years = tuple(sorted({day.year for day in days}))
    if years != (2023, 2024, 2025, 2026):
        raise ValueError("calendário deve cobrir exatamente 2023–2026")
    sources = tuple(document["sources"])
    if any(not source.get("url") or not source.get("consulted_at") for source in sources):
        raise ValueError("toda fonte do calendário requer URL e data de consulta")
    return LoadedCalendar(
        calendar=BusinessCalendar(days, document["version"]),
        sha256=hashlib.sha256(payload).hexdigest(),
        years=years,
        sources=sources,
        entries=entries,
    )
