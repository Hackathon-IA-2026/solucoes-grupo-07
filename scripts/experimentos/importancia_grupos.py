"""Frente 2 da v2: correlação entre features e importância por permutação em grupos.

Protocolo pré-registrado no diário (6/n):

- pool = todas as colunas de `build_features` + as 4 tendências do cache;
- Spearman entre pares numa amostra de 300 mil linhas de treino (dobra de agosto) por fonte;
  grupos pela clusterização hierárquica (ligação média) sobre 1 − |ρ|, corte em |ρ| > 0,7;
- modelo superconjunto (ocorrência + volume esperado, hiperparâmetros da v1) em cada uma das
  8 dobras; no mês fora da amostra, cada grupo é permutado em conjunto, 3 repetições;
- importância = queda de AP (ocorrência) e aumento da deviance de Poisson (volume).

Importância é associação no modelo, não causalidade.

Uso: `uv run python scripts/experimentos/importancia_grupos.py`.
Saída em `docs/reports/nova-abordagem/v2/`.
"""

import json
import time
from pathlib import Path

import numpy as np
import polars as pl
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import average_precision_score, mean_poisson_deviance
from v2_comum import folds, load, matrix, pool

from curtamap.contracts import SOURCES
from curtamap.previsao.features import OCCURRENCE, VOLUME
from curtamap.previsao.modelo import PARAMS

OUT = Path("docs/reports/nova-abordagem/v2")
SAMPLE = 300_000
CUT = 0.3  # distância 1 − |ρ|: grupos com |ρ| > 0,7
REPEATS = 3
SEED = 0


def groups(frame: pl.DataFrame, columns: list[str], source: str) -> dict[str, list[str]]:
    sample = frame.sample(min(SAMPLE, frame.height), seed=SEED)
    # Nulo vira −1 (fora do domínio de todas as features); a taxa de nulos é reportada.
    values = sample.select(pl.col(columns).fill_null(-1.0)).to_numpy()
    rho = np.nan_to_num(spearmanr(values).statistic, nan=0.0)
    pl.DataFrame(rho, schema=columns).insert_column(0, pl.Series("feature", columns)).write_csv(
        OUT / f"spearman_{source}.csv"
    )
    distance = np.clip(1 - np.abs(rho), 0, None)
    np.fill_diagonal(distance, 0)
    labels = fcluster(linkage(squareform(distance, checks=False), "average"), CUT, "distance")
    found: dict[str, list[str]] = {}
    for label, column in zip(labels, columns, strict=True):
        found.setdefault(f"g{label:02d}", []).append(column)
    return {"+".join(members): members for members in found.values()}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    rows, summary = [], {}
    for source in SOURCES:
        frame = load(source)
        columns = pool(frame)
        nulls = frame.select(pl.col(columns).null_count() / frame.height).row(0, named=True)
        august = list(folds(frame))[-1][2]
        found = groups(august, columns, source)
        summary[source] = {
            "pool": columns,
            "v1_ocorrencia": OCCURRENCE,
            "v1_volume": VOLUME,
            "taxa_nulos": nulls,
            "grupos": list(found.values()),
        }
        for month, _, train, test in folds(frame):
            started = time.time()
            x_train, x_test = matrix(train, columns), matrix(test, columns)
            occurrence = HistGradientBoostingClassifier(**PARAMS).fit(
                x_train, train["y_corte"].to_numpy()
            )
            volume = HistGradientBoostingRegressor(loss="poisson", **PARAMS).fit(
                x_train, train["y_volume"].to_numpy()
            )
            y, v = test["y_corte"].to_numpy(), test["y_volume"].to_numpy()
            ap = average_precision_score(y, occurrence.predict_proba(x_test)[:, 1])
            dev = mean_poisson_deviance(v, volume.predict(x_test))
            rows.append(
                {
                    "fonte": source,
                    "mes": month.isoformat(),
                    "grupo": "(nenhum)",
                    "ap_base": ap,
                    "deviance_base": dev,
                    "queda_ap": 0.0,
                    "aumento_deviance": 0.0,
                }
            )
            for name, members in found.items():
                index = [columns.index(m) for m in members]
                drops, rises = [], []
                for _ in range(REPEATS):
                    shuffled = x_test.copy()
                    order = rng.permutation(len(shuffled))
                    shuffled[:, index] = x_test[order][:, index]
                    drops.append(
                        ap - average_precision_score(y, occurrence.predict_proba(shuffled)[:, 1])
                    )
                    rises.append(mean_poisson_deviance(v, volume.predict(shuffled)) - dev)
                rows.append(
                    {
                        "fonte": source,
                        "mes": month.isoformat(),
                        "grupo": name,
                        "ap_base": ap,
                        "deviance_base": dev,
                        "queda_ap": float(np.mean(drops)),
                        "aumento_deviance": float(np.mean(rises)),
                    }
                )
            print(
                json.dumps(
                    {
                        "fonte": source,
                        "mes": month.isoformat(),
                        "ap": round(ap, 4),
                        "deviance": round(dev, 3),
                        "segundos": round(time.time() - started),
                    }
                ),
                flush=True,
            )
        del frame
    table = pl.DataFrame(rows)
    table.write_csv(OUT / "importancia_grupos.csv")
    (OUT / "grupos.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), "utf-8")
    agg = (
        table.filter(pl.col("grupo") != "(nenhum)")
        .group_by("fonte", "grupo")
        .agg(
            pl.col("queda_ap").mean().alias("ap_media"),
            pl.col("queda_ap").std().alias("ap_desvio"),
            (pl.col("queda_ap") > 0).sum().alias("ap_dobras_pos"),
            (pl.col("aumento_deviance") / pl.col("deviance_base")).mean().alias("dev_rel_media"),
            (pl.col("aumento_deviance") / pl.col("deviance_base")).std().alias("dev_rel_desvio"),
            (pl.col("aumento_deviance") > 0).sum().alias("dev_dobras_pos"),
        )
        .sort("fonte", "ap_media", descending=[False, True])
    )
    agg.write_csv(OUT / "importancia_grupos_resumo.csv")
    with pl.Config(tbl_rows=-1, tbl_width_chars=250, fmt_str_lengths=120, float_precision=4):
        print(agg)


if __name__ == "__main__":
    main()
