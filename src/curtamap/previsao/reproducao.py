"""Reprodução histórica leve para o dashboard: emissões diárias às 20h com a verdade ao lado.

Para cada dia D do recorte, emite às 20h a previsão do dia D + 1 (`t0` = 00h de D + 1), com
os dados liberados até então, no `FORECAST_SCHEMA` e com colunas extras `observado_*`. O
modelo é treinado só com rótulos anteriores ao recorte, como teria estado em produção.
O arquivo fica fora do Git e é regenerável por este script.

Uso: `uv run python -m curtamap.previsao.reproducao 2026-08-03 2026-08-30`.
"""

import argparse
import json
from datetime import date, datetime, time, timedelta
from pathlib import Path

import polars as pl

from curtamap.config import settings
from curtamap.contracts import validate_forecast
from curtamap.forecasting import load_history
from curtamap.previsao.avaliacao import FIRST_DAY, load_base
from curtamap.previsao.calendario import EMISSION_TIME, emission_cutoff, load_calendar
from curtamap.previsao.features import ENTITY_LOOKBACK_DAYS, release_map
from curtamap.previsao.modelo import DailyForecaster, DailyModel, fit

TRUTH = {
    "corte_positivo": "observado_corte",
    "volume_mwmed": "observado_volume_mwmed",
    "causa": "observado_causa",
}


def attach_truth(forecast: pl.DataFrame, history: pl.DataFrame) -> pl.DataFrame:
    observed = history.select(
        "fonte",
        "id_ons",
        pl.col("din_instante").alias("tau"),
        *(pl.col(k).alias(v) for k, v in TRUTH.items()),
    )
    return forecast.join(observed, on=["fonte", "id_ons", "tau"], how="left")


def replay(
    model: DailyModel, history: pl.DataFrame, first: date, last: date, calendar
) -> pl.DataFrame:
    """Emissões às 20h de `first − 1` a `last − 1`, prevendo os dias `first` a `last`."""
    forecaster = DailyForecaster(model, calendar)
    frames = []
    day = first
    while day <= last:
        t0 = datetime.combine(day, time())
        emitted = datetime.combine(day - timedelta(days=1), EMISSION_TIME)
        forecast = forecaster.predict(
            history,
            t0,
            emission_cutoff(day, calendar),
            generated_at=emitted,
            emitted_at=emitted,
        )
        frames.append(forecast)
        day += timedelta(days=1)
    forecasts = validate_forecast(pl.concat(frames))
    return attach_truth(forecasts, history).sort(["t0", "fonte", "id_ons", "horizonte"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inicio", type=date.fromisoformat)
    parser.add_argument("fim", type=date.fromisoformat)
    parser.add_argument("--limiares", type=Path)
    parser.add_argument("--saida", type=Path, default=settings.data_dir / "interim" / "previsao")
    args = parser.parse_args()
    calendar = load_calendar()
    last_label = release_map([args.inicio], calendar)["ultimo_dia"].item()
    base = load_base(settings.data_dir, datetime.combine(last_label + timedelta(days=1), time()))
    days = pl.date_range(FIRST_DAY, last_label, eager=True).to_list()
    model = fit(base, release_map(days, calendar), last_label, uso="reproducao_historica")
    del base
    if args.limiares:
        for source, value in json.loads(args.limiares.read_text(encoding="utf-8")).items():
            model.sources[source].threshold = float(value)
    model.save(settings.model_dir / "previsao")
    start = datetime.combine(last_label - timedelta(days=ENTITY_LOOKBACK_DAYS + 2), time())
    end = datetime.combine(args.fim + timedelta(days=1), time())
    history = load_history(settings.data_dir, start, end)
    result = replay(model, history, args.inicio, args.fim, calendar)
    args.saida.mkdir(parents=True, exist_ok=True)
    path = args.saida / f"reproducao_{args.inicio}_{args.fim}.parquet"
    result.write_parquet(path)
    print(path, result.height, result["t0"].n_unique(), "emissões")


if __name__ == "__main__":
    main()
