"""Treina e congela o modelo diário do produto com todo o snapshot do hackathon.

O rótulo mais recente usado é o último dia liberado na emissão que prevê 01/09/2026, para
que nenhuma previsão de setembro use no treino um rótulo ainda não publicado. O limiar de
alerta por fonte vem das previsões fora da amostra do backtest (`avaliacao`), nunca do treino.

Uso: `uv run python -m curtamap.previsao.treinar --limiares data/interim/previsao/limiares.json`.
"""

import argparse
import json
from datetime import date, datetime
from pathlib import Path

import polars as pl

from curtamap.config import settings
from curtamap.previsao.avaliacao import FIRST_DAY, load_base
from curtamap.previsao.calendario import load_calendar
from curtamap.previsao.features import release_map
from curtamap.previsao.modelo import fit

FIRST_FORECAST_DAY = date(2026, 9, 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limiares", type=Path, required=True)
    parser.add_argument("--saida", type=Path, default=settings.model_dir / "previsao")
    args = parser.parse_args()
    calendar = load_calendar()
    last_label = release_map([FIRST_FORECAST_DAY], calendar)["ultimo_dia"].item()
    thresholds = json.loads(args.limiares.read_text(encoding="utf-8"))
    base = load_base(settings.data_dir, datetime.combine(FIRST_FORECAST_DAY, datetime.min.time()))
    base = base.filter(pl.col("dia") <= last_label)
    days = pl.date_range(FIRST_DAY, last_label, eager=True).to_list()
    model = fit(
        base,
        release_map(days, calendar),
        last_label,
        dados="data/raw (snapshot do hackathon)",
        limiares_alerta=thresholds,
        treinado_em=datetime.now().isoformat(timespec="seconds"),
    )
    for source, threshold in thresholds.items():
        model.sources[source].threshold = float(threshold)
    path = model.save(args.saida)
    print(path)


if __name__ == "__main__":
    main()
