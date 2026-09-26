"""Frente A da v3: faixas relativas de volume por excedência cumulativa (diário 8/n).

Para cada nível (meia-hora e usina × dia), fonte e limiar k ∈ {k₀, k₁, k₂} de `faixas.json`,
um HGB binário estima P(fração > k), com as features A0 (v1 de ocorrência; agregadas no
diário) e os `PARAMS` da v1, sementes 0, 1 e 2. Na meia-hora, k₀ reusa as previsões da B0
da frente B. As excedências são monotonizadas e as faixas saem por diferença.

Baselines nas mesmas linhas: `historico` (frequência de fração > k em 28 d) e `ultimo_dia`
(indicador em L). Métricas: AP por limiar (principal), Brier, confiabilidade, RPS e skill do
RPS sobre o `historico`, e o alerta de "severo" com limiar escolhido em jan–abr.

Uso: `uv run python scripts/experimentos/frente_a.py [--extra B1|B2]` (A1 = A0 + features
adotadas na frente B).
"""

import argparse
import json
import time

import numpy as np
import polars as pl
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, brier_score_loss
from v3_comum import (
    CACHE,
    REPORT,
    SEEDS,
    decide,
    folds,
    load,
    load_daily,
    matrix,
    noise,
    reliability,
    thresholds,
)

from curtamap.previsao.avaliacao import choose_threshold
from curtamap.previsao.faixas import faixa, monotonizar, probabilidades_faixas, rps
from curtamap.previsao.features import OCCURRENCE
from curtamap.previsao.modelo import PARAMS

SIN = ["sin_ene_ultimo", "sin_ene_7d", "sin_ene_ultimo_total", "sin_ene_7d_total"]
GRUPO = ["grupo_nivel_ultimo", "grupo_nivel_7d", "grupo_tamanho"]
EXTRA = {"B1": SIN, "B2": [*SIN, *GRUPO]}
POR_SLOT = ["hist_7d", "hist_28d", "hist_91d", "ultimo_slot", "vol_hist_7d", "vol_hist_28d"]
DAILY = [
    *(f"{c}_{s}" for c in POR_SLOT for s in ("media", "max")),
    "usina_nivel_ultimo",
    "usina_nivel_7d",
    "estado_nivel_ultimo",
    "estado_nivel_7d",
    "estado_nivel_28d",
    "estado_ene_7d",
    "idade",
    "dia_semana",
    "feriado",
]
ALERT_FIT = {1, 2, 3, 4}


def _ap(y, p):
    return float(average_precision_score(y, p)) if 0 < y.sum() < len(y) else float("nan")


def _fit(train, features, target, seed):
    model = HistGradientBoostingClassifier(**{**PARAMS, "random_state": seed})
    return model.fit(matrix(train, features), target)


def run(level: str, source: str, variant: str, features: list[str]) -> tuple[list, pl.DataFrame]:
    ks = thresholds()[level][source]
    ks = [ks["k0"], ks["k1"], ks["k2"]]
    if level == "meia_hora":
        frame = load(source)
        label, key = "y_fracao", ["fonte", "id_ons", "dia", "slot"]
        reuse = pl.read_parquet(CACHE / f"pred_b_{source}.parquet")
        k0_column = {"A0": "p_B0_s{s}", "A1_B1": "p_B1", "A1_B2": "p_B2"}[variant]
    else:
        frame = load_daily(source)
        label, key, reuse, k0_column = "fracao_dia", ["fonte", "id_ons", "dia"], None, None
    rows, predictions = [], []
    seeds = SEEDS if variant == "A0" else (0,)
    for month, _, train, test in folds(frame):
        train = train.filter(pl.col(label).is_not_null())
        test = test.filter(pl.col(label).is_not_null())
        if reuse is not None:
            test = test.join(reuse, on=key, how="left")
        fraction_train = train[label].to_numpy()
        fraction = test[label].to_numpy()
        base_row = {"nivel": level, "fonte": source, "mes": month.isoformat()}
        exceed = {}
        for seed in seeds:
            columns = []
            for j, k in enumerate(ks):
                started = time.time()
                if j == 0 and reuse is not None:
                    name = k0_column.format(s=seed) if "{s}" in k0_column else k0_column
                    p = test[name].to_numpy()
                else:
                    p = _fit(train, features, (fraction_train > k).astype(int), seed)
                    p = p.predict_proba(matrix(test, features))[:, 1]
                columns.append(p)
                y = (fraction > k).astype(int)
                rows.append(
                    {
                        **base_row,
                        "variante": f"{variant}_s{seed}",
                        "k": j,
                        "ap": _ap(y, p),
                        "brier": float(brier_score_loss(y, np.clip(p, 0, 1))),
                        "prevalencia": float(y.mean()),
                        "n": len(y),
                    }
                )
                print(
                    json.dumps({**rows[-1], "segundos": round(time.time() - started)}), flush=True
                )
            exceed[seed] = monotonizar(np.column_stack(columns))
        for j, k in enumerate(ks):
            y = (fraction > k).astype(int)
            for name, column in (("historico", f"exc_hist_k{j}"), ("ultimo_dia", f"exc_ult_k{j}")):
                score = test[column].fill_null(0.0).to_numpy()
                rows.append(
                    {
                        **base_row,
                        "variante": name,
                        "k": j,
                        "ap": _ap(y, score),
                        "brier": float(brier_score_loss(y, np.clip(score, 0, 1))),
                        "prevalencia": float(y.mean()),
                        "n": len(y),
                    }
                )
        band = test.select(faixa(pl.col(label), ks[1], ks[2])).to_series().to_numpy()
        historic = monotonizar(
            np.column_stack([test[f"exc_hist_k{j}"].fill_null(0.0).to_numpy() for j in range(3)])
        )
        rps_hist = rps(probabilidades_faixas(historic), band)
        for seed, matrix_p in exceed.items():
            value = rps(probabilidades_faixas(matrix_p), band)
            rows.append(
                {
                    **base_row,
                    "variante": f"{variant}_s{seed}",
                    "k": -1,
                    "rps": value,
                    "rps_historico": rps_hist,
                    "skill_rps": 1 - value / rps_hist,
                }
            )
        probabilities = probabilidades_faixas(exceed[0])
        predictions.append(
            test.select(*key, "idade", label, *(f"exc_hist_k{j}" for j in range(3))).with_columns(
                pl.Series("faixa_real", band, dtype=pl.Int8),
                *(pl.Series(f"p_exc_k{j}", exceed[0][:, j], dtype=pl.Float64) for j in range(3)),
                *(
                    pl.Series(f"p_faixa_{n}", probabilities[:, i], dtype=pl.Float64)
                    for i, n in enumerate(("sem_corte", "leve", "moderada", "severa"))
                ),
                pl.lit(month).alias("mes"),
            )
        )
    return rows, pl.concat(predictions, how="diagonal_relaxed")


def operational(predictions: pl.DataFrame, level: str, source: str, variant: str) -> dict:
    """Alerta de "severo": limiar F1-ótimo em jan–abr (fora da amostra), aplicado a mai–ago."""
    frame = predictions.with_columns((pl.col("faixa_real") == 3).cast(pl.Int8).alias("_y"))
    fit = frame.filter(pl.col("mes").dt.month().is_in(ALERT_FIT))
    test = frame.filter(~pl.col("mes").dt.month().is_in(ALERT_FIT))
    out = {"nivel": level, "fonte": source, "variante": variant}
    for name, column in (("modelo", "p_exc_k2"), ("historico", "exc_hist_k2")):
        score_fit = fit[column].fill_null(0.0).to_numpy()
        threshold = choose_threshold(fit["_y"].to_numpy(), score_fit)
        alert = test[column].fill_null(0.0).to_numpy() >= threshold
        y = test["_y"].to_numpy() == 1
        out[f"limiar_{name}"] = threshold
        out[f"recall_{name}"] = float((alert & y).sum() / max(y.sum(), 1))
        out[f"precisao_{name}"] = float((alert & y).sum() / max(alert.sum(), 1))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extra", choices=sorted(EXTRA), help="A1 = A0 + features da frente B")
    parser.add_argument("--nivel", choices=["diario", "meia_hora"], action="append")
    args = parser.parse_args()
    variant = f"A1_{args.extra}" if args.extra else "A0"
    tables, alerts, curves = [], [], []
    for level in args.nivel or ("diario", "meia_hora"):
        base_features = DAILY if level == "diario" else OCCURRENCE
        features = [*base_features, *EXTRA.get(args.extra, [])]
        for source in ("eolica", "fotovoltaica"):
            part = REPORT / f"_frente_a_{variant}_{level}_{source}.csv"
            path = CACHE / f"pred_faixas_{variant}_{level}_{source}.parquet"
            if part.exists() and path.exists():
                table, predictions = pl.read_csv(part), pl.read_parquet(path)
            else:
                found, predictions = run(level, source, variant, features)
                table = pl.DataFrame(found)
                table.write_csv(part)
                predictions.write_parquet(path)
            tables.append(table)
            alerts.append(operational(predictions, level, source, variant))
            for j in range(3):
                y = (predictions["faixa_real"].to_numpy() > j).astype(int)
                for name, column in (("modelo", f"p_exc_k{j}"), ("historico", f"exc_hist_k{j}")):
                    for row in reliability(y, predictions[column].fill_null(0.0).to_numpy()):
                        curves.append(
                            {"nivel": level, "fonte": source, "k": j, "preditor": name, **row}
                        )
    table = pl.concat(tables, how="diagonal_relaxed")
    table.write_csv(REPORT / f"frente_a_{variant}.csv")
    pl.DataFrame(alerts).write_csv(REPORT / f"frente_a_{variant}_alerta_severo.csv")
    pl.DataFrame(curves).write_csv(REPORT / f"frente_a_{variant}_confiabilidade.csv")
    decisions = []
    per_k = table.filter(pl.col("k") >= 0)
    for (level, source, k), group in sorted(
        per_k.partition_by(["nivel", "fonte", "k"], as_dict=True).items()
    ):
        seeds = [f"{variant}_s{s}" for s in (SEEDS if variant == "A0" else (0,))]
        values = group.with_columns(
            pl.when(pl.col("variante") == f"{variant}_s0")
            .then(pl.lit(variant))
            .otherwise(pl.col("variante"))
            .alias("variante")
        )
        if variant == "A0":
            spread = noise(group, "ap", seeds)
            decisions.append(
                {
                    "nivel": level,
                    "fonte": source,
                    "k": k,
                    **decide(values, "ap", "A0", "historico", spread),
                }
            )
            decisions.append(
                {
                    "nivel": level,
                    "fonte": source,
                    "k": k,
                    **decide(
                        values,
                        "brier",
                        "A0",
                        "historico",
                        noise(group, "brier", seeds),
                        higher_is_better=False,
                    ),
                }
            )
    if decisions:
        pl.DataFrame(decisions).write_csv(REPORT / f"frente_a_{variant}_resumo.csv")
    with pl.Config(tbl_rows=-1, tbl_cols=-1, tbl_width_chars=250, float_precision=4):
        if decisions:
            print(pl.DataFrame(decisions))
        print(pl.DataFrame(alerts))
        print(
            table.filter(pl.col("k") == -1)
            .group_by("nivel", "fonte", "variante")
            .agg(
                pl.col("rps", "rps_historico", "skill_rps").mean(),
                (pl.col("skill_rps") > 0).sum().alias("meses_skill_pos"),
            )
            .sort("nivel", "fonte", "variante")
        )
        print(
            per_k.group_by("nivel", "fonte", "k", "variante")
            .agg(pl.col("ap", "brier").mean())
            .sort("nivel", "fonte", "k", "variante")
        )


if __name__ == "__main__":
    main()
