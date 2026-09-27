"""Instantes de emissão `t0` que o painel pode oferecer.

O limite superior protege o teste reservado: as 48 janelas de `t0` precisam terminar até
`RESERVED_TEST_START`. Também não há por que emitir depois do dia seguinte ao último dado
local. O limite inferior deixa a janela de histórico do preditor inteira dentro dos dados.
"""

from datetime import date, datetime, time, timedelta

from curtamap.contracts import HORIZONS, RESERVED_TEST_START, STEP

Bounds = tuple[datetime, datetime]
_DAY = timedelta(days=1)


def _floor_day(moment: datetime) -> datetime:
    return datetime.combine(moment.date(), time())


def _ceil_day(moment: datetime) -> datetime:
    floor = _floor_day(moment)
    return floor if floor == moment else floor + _DAY


def emission_bounds(data_start: datetime, data_end: datetime, *, history_days: int) -> Bounds:
    """Primeira e última emissão permitidas; `data_end` é o último `din_instante` local."""
    latest = min(RESERVED_TEST_START - HORIZONS * STEP, _floor_day(data_end) + _DAY)
    earliest = _ceil_day(data_start) + timedelta(days=history_days + 1)
    if earliest > latest:
        raise ValueError(
            f"histórico insuficiente: a primeira emissão possível ({earliest:%d/%m/%Y}) "
            f"é posterior à última ({latest:%d/%m/%Y})"
        )
    return earliest, latest


def check_emission(t0: datetime, bounds: Bounds) -> datetime:
    earliest, latest = bounds
    if t0.minute % 30 or t0.second or t0.microsecond:
        raise ValueError("t0 precisa estar na grade de 30 minutos")
    if t0 + HORIZONS * STEP > RESERVED_TEST_START:
        raise ValueError(
            f"as 24 h a partir de t0 invadiriam o teste reservado "
            f"(a partir de {RESERVED_TEST_START:%d/%m/%Y})"
        )
    if t0 > latest:
        raise ValueError(f"t0 posterior à última emissão com dados ({latest:%d/%m/%Y %H:%M})")
    if t0 < earliest:
        raise ValueError(f"t0 anterior à primeira emissão com histórico ({earliest:%d/%m/%Y})")
    return t0


def slots_for_day(day: date, bounds: Bounds) -> list[time]:
    """Horários da grade de 30 minutos de `day` que caem dentro dos limites."""
    earliest, latest = bounds
    start = datetime.combine(day, time())
    slots = (start + i * STEP for i in range(48))
    return [moment.time() for moment in slots if earliest <= moment <= latest]
