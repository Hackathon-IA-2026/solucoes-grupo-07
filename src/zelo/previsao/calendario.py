"""Calendário de publicação do ONS e de carga baixa.

Cenário adotado: os dados de um dia civil são liberados às 19h30 do dia útil seguinte. Dia
útil exclui fins de semana e todos os feriados e pontos facultativos do calendário (inclusive
os do Rio de Janeiro, sede do ONS, e dias parciais, tratados como dias inteiros). Já a
feature de carga baixa usa só feriados nacionais: um feriado municipal do Rio não derruba a
carga do Nordeste.
"""

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

from zelo.config import Settings

RELEASE_TIME = time(19, 30)
EMISSION_TIME = time(20, 0)
DEFAULT_PATH = Path(__file__).resolve().parents[3] / "configs" / "calendario-2023-2026.json"


@dataclass(frozen=True)
class Calendar:
    non_business: frozenset[date]
    national: frozenset[date]
    first: date
    last: date

    def _check(self, day: date) -> None:
        if not self.first <= day <= self.last:
            raise ValueError(f"{day} fora da cobertura do calendário ({self.first}–{self.last})")

    def is_business_day(self, day: date) -> bool:
        self._check(day)
        return day.weekday() < 5 and day not in self.non_business

    def is_national_holiday(self, day: date) -> bool:
        self._check(day)
        return day in self.national

    def next_business_day(self, day: date) -> date:
        day += timedelta(days=1)
        while not self.is_business_day(day):
            day += timedelta(days=1)
        return day


def load_calendar(path: Path | None = None) -> Calendar:
    """Lê o calendário de `path`, de `ZELO_CALENDAR_PATH` ou de `configs/` do repositório."""
    path = path or Settings().calendar_path or DEFAULT_PATH
    content = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = [(date.fromisoformat(e["date"]), e["kind"]) for e in content["entries"]]
    years = sorted({day.year for day, _ in entries})
    return Calendar(
        non_business=frozenset(day for day, _ in entries),
        national=frozenset(day for day, kind in entries if kind == "nacional"),
        first=date(years[0], 1, 1),
        last=date(years[-1], 12, 31),
    )


def release_cutoff(moment: datetime, calendar: Calendar) -> datetime:
    """Fim do último dia civil liberado até `moment` (limite exclusivo dos dados conhecidos)."""
    day = moment.date()
    while datetime.combine(calendar.next_business_day(day), RELEASE_TIME) > moment:
        day -= timedelta(days=1)
    return datetime.combine(day + timedelta(days=1), time())


def emission_cutoff(target: date, calendar: Calendar) -> datetime:
    """Corte da emissão das 20h da véspera, que prevê o dia civil `target`."""
    return release_cutoff(datetime.combine(target - timedelta(days=1), EMISSION_TIME), calendar)
