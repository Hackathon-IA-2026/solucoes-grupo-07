"""Contingência aprovada em 23/09/2026: subconjunto sistemático de emissões ``t0``.

Cada dia civil mantém ``slots`` das 48 meias-horas, igualmente espaçadas e deslocadas
por SHA-256 de ``semente|data``. Uma emissão escolhida mantém todas as entidades e os
48 horizontes. A seleção depende só da data e da meia-hora de ``t0``: é a mesma entre
rodadas, famílias e candidatos, e o initial selecionado continua contido no refit.
Aplica-se apenas aos ajustes initial e refit; tuning, calibração e validação são completos.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta

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


def emission_mask(slots: int, seed: int) -> pl.Expr:
    positions = selected_positions(slots)
    if slots == SLOTS_PER_DAY:
        return pl.lit(True)
    days = [FIRST_DAY + timedelta(days=d) for d in range((LAST_DAY - FIRST_DAY).days + 1)]
    offsets = pl.Series([day_offset(day, seed) for day in days], dtype=pl.Int64)
    offset = pl.col("t0").dt.date().replace_strict(pl.Series(days), offsets, default=None)
    slot = pl.col("t0").dt.hour().cast(pl.Int64) * 2 + pl.col("t0").dt.minute().cast(pl.Int64) // 30
    position = (slot - offset + SLOTS_PER_DAY) % SLOTS_PER_DAY
    return position.is_in(sorted(positions)).fill_null(False)
