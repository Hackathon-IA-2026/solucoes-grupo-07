"""Frente B da v3: regime nacional e grupo de restrição no AP de ocorrência (diário 8/n).

B0 = v1 de ocorrência (sementes 0, 1 e 2, que medem o ruído); B1 = B0 + `sin_ene_*`;
B2 = B1 + `grupo_*`. Mesmos `PARAMS` da v1, mesmas linhas e dobras. A semente 0 da B0
precisa reproduzir o `ap_modelo` de `metricas_backtest.csv` (âncora), e as previsões dela são
gravadas (todas as variantes) para servir de k₀ na frente A.

Uso: `uv run python scripts/experimentos/frente_b.py`.
Saída: `docs/reports/nova-abordagem/v3/frente_b*.csv` e
`data/interim/previsao/v3/pred_b_<fonte>.parquet`.
"""

import json
import time

import polars as pl
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score
from v3_comum import CACHE, REPORT, SEEDS, decide, folds, load, matrix, noise

from curtamap.previsao.features import OCCURRENCE
from curtamap.previsao.modelo import PARAMS

SIN = ["sin_ene_ultimo", "sin_ene_7d", "sin_ene_ultimo_total", "sin_ene_7d_total"]
GRUPO = ["grupo_nivel_ultimo", "grupo_nivel_7d", "grupo_tamanho"]
VARIANTS = {
    **{f"B0_s{s}": (OCCURRENCE, s) for s in SEEDS},
    "B1": ([*OCCURRENCE, *SIN], 0),
    "B2": ([*OCCURRENCE, *SIN, *GRUPO], 0),
}
AGES = {"idade_2": (2, 2), "idade_3": (3, 3), "idade_4_7": (4, 7)}


def _ap(y, p):
    return float(average_precision_score(y, p)) if 0 < y.sum() < len(y) else float("nan")


def run(source: str) -> list[dict]:
    frame = load(source)
    rows, predictions = [], []
    for month, _, train, test in folds(frame):
        fold = test.select("fonte", "id_ons", "dia", "slot")
        y = test["y_corte"].to_numpy()
        age = test["idade"].to_numpy()
        rows.append(
            {
                "fonte": source,
                "mes": month.isoformat(),
                "variante": "historico",
                "ap": _ap(y, test["hist_28d"].fill_null(0.0).to_numpy()),
            }
        )
        for name, (features, seed) in VARIANTS.items():
            started = time.time()
            model = HistGradientBoostingClassifier(**{**PARAMS, "random_state": seed}).fit(
                matrix(train, features), train["y_corte"].to_numpy()
            )
            p = model.predict_proba(matrix(test, features))[:, 1]
            row = {"fonte": source, "mes": month.isoformat(), "variante": name, "ap": _ap(y, p)}
            for label, (low, high) in AGES.items():
                mask = (age >= low) & (age <= high)
                row[f"ap_{label}"] = _ap(y[mask], p[mask])
                row[f"n_{label}"] = int(mask.sum())
            rows.append(row)
            fold = fold.with_columns(pl.Series(f"p_{name}", p, dtype=pl.Float64))
            print(json.dumps({**row, "segundos": round(time.time() - started)}), flush=True)
        predictions.append(fold)
    pl.concat(predictions).write_parquet(CACHE / f"pred_b_{source}.parquet")
    return rows


def main() -> None:
    REPORT.mkdir(parents=True, exist_ok=True)
    reference = pl.read_csv("docs/reports/nova-abordagem/metricas_backtest.csv")
    tables, decisions = [], []
    for source in ("eolica", "fotovoltaica"):
        part = REPORT / f"_frente_b_{source}.csv"
        if part.exists():
            table = pl.read_csv(part)
        else:
            table = pl.DataFrame(run(source))
            table.write_csv(part)
        anchor = table.filter(pl.col("variante") == "B0_s0").join(
            reference.filter(pl.col("fonte") == source).select(
                pl.col("periodo").alias("mes"), "ap_modelo"
            ),
            on="mes",
        )
        drift = float((anchor["ap"] - anchor["ap_modelo"]).abs().max())
        print(json.dumps({"fonte": source, "ancora_max_dif_ap": drift}), flush=True)
        values = table.with_columns(
            pl.when(pl.col("variante") == "B0_s0")
            .then(pl.lit("B0"))
            .otherwise(pl.col("variante"))
            .alias("variante")
        )
        seeds = noise(table, "ap", [f"B0_s{s}" for s in SEEDS])
        for candidate, ref in (("B1", "B0"), ("B2", "B0"), ("B2", "B1"), ("B0", "historico")):
            decisions.append(
                {
                    "fonte": source,
                    "ancora_max_dif_ap": drift,
                    **decide(values, "ap", candidate, ref, seeds),
                }
            )
        tables.append(table.join(seeds, on="mes"))
    pl.concat(tables, how="diagonal_relaxed").write_csv(REPORT / "frente_b.csv")
    summary = pl.DataFrame(decisions)
    summary.write_csv(REPORT / "frente_b_resumo.csv")
    with pl.Config(tbl_rows=-1, tbl_cols=-1, tbl_width_chars=250, float_precision=4):
        print(summary)
        full = pl.concat(tables, how="diagonal_relaxed")
        print(full.pivot("variante", index=["fonte", "mes", "ruido"], values="ap"))
        ages = full.group_by("fonte", "variante").agg(
            pl.col("ap_idade_2", "ap_idade_3", "ap_idade_4_7").mean()
        )
        print(ages.sort("fonte", "variante"))


if __name__ == "__main__":
    main()
