"""Frente 3 da v2: variantes do volume esperado da eólica (pré-registradas no diário 6/n).

B0 v1; B1 + tendências; B2 janela 180 d; B3 janela 90 d; B4 peso de recência com meia-vida
de 90 d; B5 meia-vida de 30 d; B6 = B1 combinada com a melhor de B2–B5 pelo WAPE diário médio.
Todas usam os hiperparâmetros e a perda Poisson da v1 e são comparadas nas mesmas linhas
com o `historico` (volume médio da usina no slot em 28 d), que é o componente servido.

Uso: `uv run python scripts/experimentos/volume_eolico.py`.
Saída em `docs/reports/nova-abordagem/v2/`.
"""

import json
import time
from pathlib import Path

import numpy as np
import polars as pl
from sklearn.ensemble import HistGradientBoostingRegressor
from v2_comum import folds, load, matrix, volume_metrics

from curtamap.previsao.features import VOLUME
from curtamap.previsao.modelo import PARAMS

OUT = Path("docs/reports/nova-abordagem/v2")
TRENDS = ["tend_hist", "tend_estado", "tend_usina", "tend_vol"]
VARIANTS = {
    "B0": {"features": VOLUME, "janela": 365, "meia_vida": None},
    "B1": {"features": [*VOLUME, *TRENDS], "janela": 365, "meia_vida": None},
    "B2": {"features": VOLUME, "janela": 180, "meia_vida": None},
    "B3": {"features": VOLUME, "janela": 90, "meia_vida": None},
    "B4": {"features": VOLUME, "janela": 365, "meia_vida": 90},
    "B5": {"features": VOLUME, "janela": 365, "meia_vida": 30},
    # Ruído do próprio modelo: a semente muda a amostra dos bins. Não concorrem ao B6.
    "B0_s1": {"features": VOLUME, "janela": 365, "meia_vida": None, "semente": 1},
    "B0_s2": {"features": VOLUME, "janela": 365, "meia_vida": None, "semente": 2},
}


def run(frame: pl.DataFrame, name: str, spec: dict) -> list[dict]:
    rows = []
    for month, last_label, train, test in folds(frame, spec["janela"]):
        weight = None
        if spec["meia_vida"]:
            age = (train["dia"].max() - train["dia"]).dt.total_days().to_numpy()
            age = age + (last_label - train["dia"].max()).days
            weight = 0.5 ** (age / spec["meia_vida"])
        model = HistGradientBoostingRegressor(
            loss="poisson",
            **{**PARAMS, "random_state": spec.get("semente", PARAMS["random_state"])},
        ).fit(matrix(train, spec["features"]), train["y_volume"].to_numpy(), sample_weight=weight)
        predicted = model.predict(matrix(test, spec["features"]))
        rows.append({"variante": name, "mes": month.isoformat(), **volume_metrics(test, predicted)})
        if name == "B0":
            historic = test["vol_hist_28d"].fill_null(0.0).to_numpy().astype(np.float64)
            rows.append(
                {
                    "variante": "historico",
                    "mes": month.isoformat(),
                    **volume_metrics(test, historic),
                }
            )
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    frame = load("eolica")
    rows = []
    for name, spec in VARIANTS.items():
        part = OUT / f"_volume_eolico_{name}.csv"
        if part.exists():
            rows += pl.read_csv(part).to_dicts()
            continue
        started = time.time()
        found = run(frame, name, spec)
        pl.DataFrame(found).write_csv(part)
        rows += found
        print(json.dumps({"variante": name, "segundos": round(time.time() - started)}), flush=True)
    table = pl.DataFrame(rows)
    means = table.group_by("variante").agg(pl.col("wape_diario").mean())
    best = means.filter(pl.col("variante").is_in(["B2", "B3", "B4", "B5"])).sort("wape_diario")[
        "variante"
    ][0]
    combined = {**VARIANTS[best], "features": VARIANTS["B1"]["features"]}
    print(json.dumps({"B6": f"B1 + {best}"}), flush=True)
    table = pl.concat([table, pl.DataFrame(run(frame, "B6", combined))])
    table.write_csv(OUT / "volume_eolico.csv")
    reference = table.filter(pl.col("variante") == "B0").select(
        "mes", pl.col("wape_diario").alias("b0")
    )
    historic = table.filter(pl.col("variante") == "historico").select(
        "mes", pl.col("wape_diario").alias("hist")
    )
    summary = (
        table.join(reference, on="mes")
        .join(historic, on="mes")
        .group_by("variante")
        .agg(
            pl.col("wape_diario").mean(),
            pl.col("wape").mean(),
            pl.col("rmse").mean(),
            pl.col("vies").mean(),
            (pl.col("wape_diario") < pl.col("b0")).sum().alias("meses_vence_b0"),
            (pl.col("wape_diario") < pl.col("hist")).sum().alias("meses_vence_hist"),
        )
        .sort("wape_diario")
    )
    summary.write_csv(OUT / "volume_eolico_resumo.csv")
    with pl.Config(tbl_rows=-1, tbl_width_chars=200, float_precision=4):
        print(summary)
        print(table.pivot("variante", index="mes", values="wape_diario"))


if __name__ == "__main__":
    main()
