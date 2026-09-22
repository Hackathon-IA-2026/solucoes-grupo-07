from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta


@dataclass(frozen=True)
class HorizonWindow:
    horizon: int
    start: datetime
    end: datetime


def build_horizons(t0: datetime) -> tuple[HorizonWindow, ...]:
    if t0.second or t0.microsecond or t0.minute not in (0, 30):
        raise ValueError("t0 deve pertencer à grade de 30 minutos")
    step = timedelta(minutes=30)
    return tuple(
        HorizonWindow(horizon=h, start=t0 + (h - 1) * step, end=t0 + h * step) for h in range(1, 49)
    )


@dataclass(frozen=True)
class BusinessCalendar:
    non_business_days: frozenset[date]
    version: str

    def is_business_day(self, day: date) -> bool:
        return day.weekday() < 5 and day not in self.non_business_days

    def next_business_day(self, day: date) -> date:
        candidate = day + timedelta(days=1)
        while not self.is_business_day(candidate):
            candidate += timedelta(days=1)
        return candidate


@dataclass(frozen=True)
class AvailabilityScenario:
    scenario_id: str
    delay: timedelta = timedelta(0)

    @classmethod
    def main(cls) -> AvailabilityScenario:
        return cls("noturno_dia_util")

    @classmethod
    def delayed_24h(cls) -> AvailabilityScenario:
        return cls("noturno_mais_24h", timedelta(hours=24))

    def release_for(self, observed_day: date, calendar: BusinessCalendar) -> datetime:
        release_day = calendar.next_business_day(observed_day)
        return datetime.combine(release_day, time(19, 30)) + self.delay

    def last_fully_released_day(self, cutoff: datetime, calendar: BusinessCalendar) -> date:
        candidate = cutoff.date() - timedelta(days=1)
        while self.release_for(candidate, calendar) > cutoff:
            candidate -= timedelta(days=1)
        return candidate

    def is_available(
        self, observed_at: datetime, cutoff: datetime, calendar: BusinessCalendar
    ) -> bool:
        return (
            observed_at + timedelta(minutes=30) <= cutoff
            and self.release_for(observed_at.date(), calendar) <= cutoff
        )


@dataclass(frozen=True)
class ExternalRound:
    round_id: str
    start: datetime
    end: datetime
    reserved: bool = False

    @property
    def last_emission(self) -> datetime:
        return self.end - timedelta(hours=24)


def external_rounds() -> tuple[ExternalRound, ...]:
    return (
        ExternalRound("V1", datetime(2025, 1, 1), datetime(2025, 5, 1)),
        ExternalRound("V2", datetime(2025, 5, 1), datetime(2025, 9, 1)),
        ExternalRound("V3", datetime(2025, 9, 1), datetime(2026, 1, 1)),
        ExternalRound("V4", datetime(2026, 1, 1), datetime(2026, 5, 1)),
        ExternalRound(
            "TESTE_RESERVADO",
            datetime(2026, 5, 1),
            datetime(2026, 9, 1),
            reserved=True,
        ),
    )


class ReservedTestLocked(RuntimeError):
    pass


def require_reserved_test_release(
    *, real_data: bool, allow_reserved_test: bool, decision_ref: str | None
) -> None:
    if real_data and (not allow_reserved_test or not decision_ref or not decision_ref.strip()):
        raise ReservedTestLocked(
            "teste reservado real bloqueado: informe --allow-reserved-test e a referência "
            "da decisão congelada da Etapa 2C"
        )
