"""Cache das features por dia-alvo para os experimentos da v2 (fora do produto).

As features de um dia-alvo T dependem só dos dados até o último dia liberado L(T), nunca da
dobra. Por isso são calculadas uma vez e cada dobra do backtest vira um filtro de linhas:
treino com dias-alvo em (L_M − janela, L_M] e teste com os dias do mês M, como em
`curtamap.previsao.avaliacao.backtest_month`.

Acrescenta as quatro tendências pré-registradas no diário (6/n).

Uso: `uv run python scripts/experimentos/cache_features_v2.py`.
Saída: `data/interim/previsao/v2/features_<fonte>.parquet`.
"""

from datetime import date, datetime, timedelta

import polars as pl

from curtamap.config import settings
from curtamap.previsao.avaliacao import load_base
from curtamap.previsao.calendario import load_calendar
from curtamap.previsao.features import attach_targets, build_features, release_map

FIRST_TARGET = date(2024, 12, 1)
LAST_TARGET = date(2026, 8, 31)
OUT = settings.data_dir / "interim" / "previsao" / "v2"
TRENDS = {
    "tend_hist": pl.col("hist_7d") - pl.col("hist_28d"),
    "tend_estado": pl.col("estado_nivel_7d") - pl.col("estado_nivel_28d"),
    "tend_usina": pl.col("usina_nivel_ultimo") - pl.col("usina_nivel_7d"),
    "tend_vol": pl.col("vol_hist_7d") - pl.col("vol_hist_28d"),
}


def main() -> None:
    calendar = load_calendar()
    base = load_base(settings.data_dir, datetime(2026, 9, 1))
    OUT.mkdir(parents=True, exist_ok=True)
    parts: dict[str, list[pl.DataFrame]] = {}
    start = FIRST_TARGET
    while start <= LAST_TARGET:
        end = min(
            (start.replace(day=28) + timedelta(days=4)).replace(day=1),
            LAST_TARGET + timedelta(days=1),
        )
        days = pl.date_range(start, end - timedelta(days=1), eager=True).to_list()
        rows = (
            attach_targets(build_features(base, release_map(days, calendar)), base)
            .filter(pl.col("y_corte").is_not_null())
            .with_columns(v.cast(pl.Float32).alias(k) for k, v in TRENDS.items())
        )
        for (source,), frame in rows.partition_by("fonte", as_dict=True).items():
            parts.setdefault(source, []).append(frame)
        print(start, rows.height, flush=True)
        start = end
    for source, frames in parts.items():
        pl.concat(frames, how="diagonal_relaxed").write_parquet(OUT / f"features_{source}.parquet")


if __name__ == "__main__":
    main()
