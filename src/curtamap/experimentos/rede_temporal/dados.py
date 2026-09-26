"""Base, dobras mensais e linhas avaliadas, reaproveitando `curtamap.previsao`.

- A base é o snapshot (até 31/08/2026) mais a publicação de setembro baixada para
  `data/interim/experimento_rede/setembro`.
- 25/09/2026 é o dia reservado do protocolo: fica fora da base usada na seleção e na
  avaliação, até ser liberado de propósito.
- Cada dobra mensal M treina com rótulos até `fold_cutoff(M)`, o último dia liberado na
  emissão das 20h da véspera do dia 1º de M, como `previsao.avaliacao.backtest_month`.
"""

from datetime import date, datetime, timedelta
from pathlib import Path

import polars as pl

from curtamap.config import settings
from curtamap.previsao.avaliacao import load_base
from curtamap.previsao.calendario import Calendar
from curtamap.previsao.features import (
    attach_targets,
    base_from_history,
    build_features,
    release_map,
)
from curtamap.previsao.setembro import read_september

OUTPUT = Path("data/interim/experimento_rede")
SEPTEMBER = date(2026, 9, 1)
HOLDOUT_DAY = date(2026, 9, 25)
SELECTION_MONTHS = [date(2026, m, 1) for m in range(1, 5)]
EVALUATION_MONTHS = [date(2026, m, 1) for m in range(5, 9)]


def month_days(month: date, last: date | None = None) -> list[date]:
    following = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
    end = min(following - timedelta(days=1), last) if last else following - timedelta(days=1)
    return pl.date_range(month, end, eager=True).to_list()


def without_holdout(days: list[date]) -> list[date]:
    return [d for d in days if d < HOLDOUT_DAY]


def fold_cutoff(month: date, calendar: Calendar) -> date:
    """Último dia com rótulo liberado na emissão da véspera do dia 1º de `month`."""
    return release_map([month], calendar)["ultimo_dia"].item()


def build_base(output: Path = OUTPUT, *, include_holdout: bool = False) -> pl.DataFrame:
    """Snapshot + setembro, sem o dia reservado; em cache em `output/base*.parquet`."""
    name = "base_com_reserva.parquet" if include_holdout else "base.parquet"
    path = output / name
    if path.exists():
        return pl.read_parquet(path)
    snapshot = load_base(settings.data_dir, datetime.combine(SEPTEMBER, datetime.min.time()))
    september = base_from_history(read_september(output / "setembro"))
    if not include_holdout:
        september = september.filter(pl.col("dia") < HOLDOUT_DAY)
    base = pl.concat([snapshot, september]).sort(["fonte", "id_ons", "dia", "slot"])
    output.mkdir(parents=True, exist_ok=True)
    base.write_parquet(path)
    return base


def evaluation_rows(base: pl.DataFrame, days: list[date], calendar: Calendar) -> pl.DataFrame:
    """Linhas avaliadas: features da emissão das 20h e rótulo válido do dia-alvo."""
    rows = attach_targets(build_features(base, release_map(days, calendar)), base)
    return rows.filter(pl.col("y_corte").is_not_null())
