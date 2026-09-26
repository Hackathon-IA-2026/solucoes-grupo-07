"""Frente C da v3: causa, tentando vencer a moda da usina nas trocas de regime (diário 8/n).

Referências: a moda servida (participações da usina no slot em 28 d, com recurso ao estado
em 7 d) e o HGB v1 de causa (balanceado, só reportado).

- C1: HGB multiclasse sem peso, com `CAUSE` + moda de 28 d em one-hot + `causa_*_91d` +
  regime nacional + grupo de restrição;
- C2: HGB binário ENE × local com as mesmas features; se local, CNF ou REL pela moda da
  usina no slot em 91 d (empate ou sem histórico → CNF).

Treino nas ordens com causa conhecida (como na v1). Avaliação principal nas linhas com causa
conhecida e corte real; o subconjunto da v1 (toda ordem com causa) sai ao lado.

Uso: `uv run python scripts/experimentos/frente_c.py`.
"""

import json
import time

import numpy as np
import polars as pl
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import f1_score
from v3_comum import REPORT, SEEDS, decide, folds, load, matrix, noise

from curtamap.contracts import PREDICTABLE_CAUSES
from curtamap.previsao.features import CAUSE
from curtamap.previsao.modelo import CAUSE_PARAMS

PLANT = [f"causa_{c.lower()}_28d" for c in PREDICTABLE_CAUSES]
STATE = [f"estado_{c.lower()}_7d" for c in PREDICTABLE_CAUSES]
MODE = [f"moda_{c.lower()}" for c in PREDICTABLE_CAUSES]
SIN = ["sin_ene_ultimo", "sin_ene_7d", "sin_ene_ultimo_total", "sin_ene_7d_total"]
GRUPO = ["grupo_nivel_ultimo", "grupo_nivel_7d", "grupo_tamanho"]
CAUSA_91 = ["causa_rel_91d", "causa_cnf_91d", "causa_ene_91d"]
FEATURES = [*CAUSE, *MODE, *CAUSA_91, *SIN, *GRUPO]
LABELS = list(PREDICTABLE_CAUSES)


def _argmax(columns: list[str]) -> pl.Expr:
    present = pl.all_horizontal(pl.col(c).is_not_null() for c in columns)
    choice = pl.concat_list(pl.col(c) for c in columns).list.arg_max()
    return pl.when(present).then(choice.replace_strict(dict(enumerate(LABELS))))


def prepare(frame: pl.DataFrame) -> pl.DataFrame:
    plant = _argmax(PLANT)
    return frame.with_columns(
        plant.alias("moda_usina"),
        pl.coalesce(plant, _argmax(STATE)).fill_null("SEM").alias("moda_servida"),
        *(
            (plant == c).fill_null(False).cast(pl.Float32).alias(m)
            for c, m in zip(LABELS, MODE, strict=True)
        ),
        pl.when(pl.col("causa_rel_91d").fill_null(0) > pl.col("causa_cnf_91d").fill_null(0))
        .then(pl.lit("REL"))
        .otherwise(pl.lit("CNF"))
        .alias("local_91d"),
    )


def scores(y: np.ndarray, predicted: np.ndarray, mode: np.ndarray) -> dict:
    per_class = f1_score(y, predicted, labels=LABELS, average=None, zero_division=0)
    switch = (mode != y) & (mode != None)  # noqa: E711  (moda nula não conta como troca)
    return {
        "macro_f1": float(f1_score(y, predicted, labels=LABELS, average="macro", zero_division=0)),
        **{f"f1_{c.lower()}": float(v) for c, v in zip(LABELS, per_class, strict=True)},
        "acuracia": float((y == predicted).mean()),
        "taxa_troca": float(switch.mean()),
        "acuracia_troca": float((y[switch] == predicted[switch]).mean()) if switch.any() else None,
        "n": len(y),
    }


def run(source: str) -> list[dict]:
    frame = prepare(load(source))
    rows = []
    for month, _, train, test in folds(frame):
        train = train.filter(pl.col("y_causa").is_not_null())
        test = test.filter(pl.col("y_causa").is_not_null())
        y_train = train["y_causa"].to_numpy()
        predicted = {"moda": test["moda_servida"].to_numpy()}
        started = time.time()
        v1 = HistGradientBoostingClassifier(class_weight="balanced", **CAUSE_PARAMS).fit(
            matrix(train, CAUSE), y_train
        )
        predicted["hgb_v1"] = v1.predict(matrix(test, CAUSE))
        for seed in SEEDS:
            params = {**CAUSE_PARAMS, "random_state": seed}
            c1 = HistGradientBoostingClassifier(**params).fit(matrix(train, FEATURES), y_train)
            predicted[f"C1_s{seed}"] = c1.predict(matrix(test, FEATURES))
            c2 = HistGradientBoostingClassifier(**params).fit(
                matrix(train, FEATURES), (y_train == "ENE").astype(int)
            )
            ene = c2.predict_proba(matrix(test, FEATURES))[:, 1] >= 0.5
            predicted[f"C2_s{seed}"] = np.where(ene, "ENE", test["local_91d"].to_numpy())
        cut = test["y_corte"].to_numpy() == 1
        y = test["y_causa"].to_numpy()
        mode = test["moda_usina"].to_numpy()
        for name, values in predicted.items():
            for subset, mask in (("principal", cut), ("v1", np.ones_like(cut))):
                rows.append(
                    {
                        "fonte": source,
                        "mes": month.isoformat(),
                        "variante": name,
                        "subconjunto": subset,
                        **scores(y[mask], values[mask].astype(object), mode[mask]),
                    }
                )
        print(
            json.dumps(
                {"fonte": source, "mes": str(month), "segundos": round(time.time() - started)}
            ),
            flush=True,
        )
    return rows


def main() -> None:
    tables, decisions = [], []
    for source in ("eolica", "fotovoltaica"):
        part = REPORT / f"_frente_c_{source}.csv"
        if part.exists():
            table = pl.read_csv(part)
        else:
            table = pl.DataFrame(run(source))
            table.write_csv(part)
        tables.append(table)
        main_rows = table.filter(pl.col("subconjunto") == "principal")
        for candidate in ("C1", "C2"):
            seeds = [f"{candidate}_s{s}" for s in SEEDS]
            values = main_rows.with_columns(
                pl.when(pl.col("variante") == f"{candidate}_s0")
                .then(pl.lit(candidate))
                .otherwise(pl.col("variante"))
                .alias("variante")
            )
            f1 = decide(values, "macro_f1", candidate, "moda", noise(main_rows, "macro_f1", seeds))
            accuracy = decide(
                values, "acuracia", candidate, "moda", noise(main_rows, "acuracia", seeds)
            )
            not_worse = accuracy["media_candidato"] >= accuracy["media_referencia"]
            decisions.append(
                {
                    "fonte": source,
                    **f1,
                    "acuracia_candidato": accuracy["media_candidato"],
                    "acuracia_moda": accuracy["media_referencia"],
                    "adotado": f1["adotado"] and not_worse,
                }
            )
    table = pl.concat(tables)
    table.write_csv(REPORT / "frente_c.csv")
    summary = pl.DataFrame(decisions)
    summary.write_csv(REPORT / "frente_c_resumo.csv")
    with pl.Config(tbl_rows=-1, tbl_cols=-1, tbl_width_chars=250, float_precision=4):
        print(summary)
        print(
            table.group_by("fonte", "subconjunto", "variante")
            .agg(
                pl.col(
                    "macro_f1",
                    "f1_rel",
                    "f1_cnf",
                    "f1_ene",
                    "acuracia",
                    "taxa_troca",
                    "acuracia_troca",
                ).mean()
            )
            .sort("fonte", "subconjunto", "variante")
        )
        print(
            table.filter(pl.col("subconjunto") == "principal").pivot(
                "variante", index=["fonte", "mes"], values="macro_f1"
            )
        )


if __name__ == "__main__":
    main()
