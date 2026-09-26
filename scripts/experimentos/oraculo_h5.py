"""H5: quanto valeria uma previsão meteorológica? Experimento oráculo, fora do produto.

O clima **verificado** do dia-alvo (vento ou irradiância médios do estado, a partir dos
`*_detail`) entra como se fosse uma previsão perfeita. Mede um teto; nunca é feature D+1.
Compara também o clima já liberado em L, que é legítimo.

Pré-requisito: `data/interim/clima_estado.parquet`, agregado por DuckDB a partir dos
`*_detail` (médias por fonte × estado × dia × slot, só leituras válidas e não negativas).

Uso: `uv run python scripts/experimentos/oraculo_h5.py`.
"""

import json
from datetime import date, datetime, timedelta

import polars as pl
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import average_precision_score

from curtamap.config import settings
from curtamap.previsao.avaliacao import load_base, wape
from curtamap.previsao.calendario import load_calendar
from curtamap.previsao.features import (
    OCCURRENCE,
    VOLUME,
    attach_targets,
    build_features,
    release_map,
)
from curtamap.previsao.modelo import PARAMS, TRAIN_DAYS

VARIANTS = {
    "produto": [],
    "+clima_L (legítimo)": ["clima_dia_L"],
    "+clima_T (oráculo)": ["clima_T", "clima_dia_T"],
}


def _climate() -> tuple[pl.DataFrame, pl.DataFrame]:
    slots = pl.read_parquet(settings.data_dir / "interim" / "clima_estado.parquet").with_columns(
        pl.col("slot").cast(pl.Int8)
    )
    daily = slots.group_by("fonte", "id_estado", "dia").agg(
        pl.col("clima").mean().alias("clima_dia")
    )
    target = slots.rename({"clima": "clima_T"}).join(
        daily.rename({"clima_dia": "clima_dia_T"}), on=["fonte", "id_estado", "dia"]
    )
    last = daily.rename({"dia": "ultimo_dia", "clima_dia": "clima_dia_L"})
    return target, last


def _matrix(frame: pl.DataFrame, columns: list[str]):
    return frame.select(pl.col(columns).cast(pl.Float32)).to_numpy()


def main() -> None:
    calendar = load_calendar()
    base = load_base(settings.data_dir, datetime(2026, 9, 1))
    target, last = _climate()

    def rows(days: list[date]) -> pl.DataFrame:
        labelled = attach_targets(build_features(base, release_map(days, calendar)), base)
        return (
            labelled.filter(pl.col("y_corte").is_not_null())
            .join(target, on=["fonte", "id_estado", "dia", "slot"], how="left")
            .join(last, on=["fonte", "id_estado", "ultimo_dia"], how="left")
        )

    results = []
    for month in range(5, 9):
        start, end = date(2026, month, 1), date(2026, month + 1, 1)
        last_label = release_map([start], calendar)["ultimo_dia"].item()
        train = rows(
            pl.date_range(
                last_label - timedelta(days=TRAIN_DAYS - 1), last_label, eager=True
            ).to_list()
        )
        test = rows(pl.date_range(start, end - timedelta(days=1), eager=True).to_list())
        for source in ("eolica", "fotovoltaica"):
            a = train.filter(pl.col("fonte") == source)
            z = test.filter(pl.col("fonte") == source)
            y = z["y_corte"].to_numpy()
            result = {
                "fonte": source,
                "mes": month,
                "ap_historico": average_precision_score(y, z["hist_28d"].fill_null(0)),
            }
            for name, extra in VARIANTS.items():
                occurrence = HistGradientBoostingClassifier(**PARAMS).fit(
                    _matrix(a, OCCURRENCE + extra), a["y_corte"].to_numpy()
                )
                result[f"ap_{name}"] = average_precision_score(
                    y, occurrence.predict_proba(_matrix(z, OCCURRENCE + extra))[:, 1]
                )
                volume = HistGradientBoostingRegressor(loss="poisson", **PARAMS).fit(
                    _matrix(a, VOLUME + extra), a["y_volume"].to_numpy()
                )
                scored = z.with_columns(pl.Series("p", volume.predict(_matrix(z, VOLUME + extra))))
                daily = scored.group_by("id_ons", "dia").agg(
                    pl.col("y_volume").sum(), pl.col("p").sum()
                )
                result[f"wape_{name}"] = wape(scored["y_volume"].to_numpy(), scored["p"].to_numpy())
                result[f"wape_diario_{name}"] = wape(
                    daily["y_volume"].to_numpy(), daily["p"].to_numpy()
                )
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    table = pl.DataFrame(results)
    table.write_csv(settings.data_dir / "interim" / "oraculo_h5.csv")
    with pl.Config(tbl_cols=-1, tbl_width_chars=250, float_precision=3):
        print(table.drop("mes").group_by("fonte").mean())


if __name__ == "__main__":
    main()
