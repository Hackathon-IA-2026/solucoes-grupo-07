"""Contingência aprovada em 23/09/2026: subconjunto sistemático de emissões ``t0``.

Cada dia civil mantém ``slots`` das 48 meias-horas, igualmente espaçadas e deslocadas
por SHA-256 de ``semente|data``. Uma emissão escolhida mantém todas as entidades e os
48 horizontes. A seleção depende só da data e da meia-hora de ``t0``: é a mesma entre
rodadas, famílias e candidatos, e o initial selecionado continua contido no refit.
Aplica-se apenas aos ajustes initial e refit; tuning, calibração e validação são completos.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta

import polars as pl

METHOD = "t0_sistematico_diario_v1"
SLOTS_PER_DAY = 48
# Datas cobertas pelo mapeamento de deslocamentos; o desenvolvimento termina em 2026-05-01.
FIRST_DAY, LAST_DAY = date(2023, 1, 1), date(2026, 12, 31)


def selected_positions(slots: int) -> frozenset[int]:
    if not 1 <= slots <= SLOTS_PER_DAY:
        raise ValueError("slots deve estar entre 1 e 48")
    return frozenset(j * SLOTS_PER_DAY // slots for j in range(slots))


def day_offset(day: date, seed: int) -> int:
    digest = hashlib.sha256(f"{seed}|{day.isoformat()}".encode()).hexdigest()
    return int(digest, 16) % SLOTS_PER_DAY


def selected_emissions(slots: int, seed: int) -> list[datetime]:
    """Todos os ``t0`` escolhidos no intervalo coberto, em ordem crescente."""
    positions = sorted(selected_positions(slots))
    chosen = []
    for index in range((LAST_DAY - FIRST_DAY).days + 1):
        day = FIRST_DAY + timedelta(days=index)
        midnight = datetime.combine(day, datetime.min.time())
        offset = day_offset(day, seed)
        chosen.extend(
            midnight + timedelta(minutes=30 * ((position + offset) % SLOTS_PER_DAY))
            for position in positions
        )
    return sorted(chosen)


def emission_mask(slots: int, seed: int) -> pl.Expr:
    """Pertinência a uma lista literal: desce ao scan do Parquet (predicate pushdown).

    Uma expressão derivada por ``replace_strict`` ficava acima do scan e fazia a campanha
    materializar o refit inteiro antes de amostrar (``main-eolica-v1-001``, 23/09/2026).
    """
    if slots == SLOTS_PER_DAY:
        selected_positions(slots)
        return pl.lit(True)
    values = pl.Series(selected_emissions(slots, seed), dtype=pl.Datetime("us"))
    return pl.col("t0").is_in(values.implode())
