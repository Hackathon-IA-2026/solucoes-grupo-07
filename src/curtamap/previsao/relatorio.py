"""Resume o backtest: métricas por mês, limiar de alerta e decisão por célula.

Regra registrada no diário antes dos resultados: o modelo de ocorrência substitui o melhor
baseline de uma fonte se vencer em AP na média das dobras **e** em pelo menos 6 de 8 meses,
nas mesmas linhas. Volume e causa não são modelos no produto (26/09/2026); o macro-F1 das
causas históricas (usina 28 d e estado 7 d) continua reportado.

O limiar de alerta é escolhido nas previsões fora da amostra de jan–abr e verificado em
mai–ago. O limiar final (para o modelo congelado) usa jan–ago inteiro.

Uso:
`uv run python -m curtamap.previsao.relatorio data/interim/previsao docs/reports/nova-abordagem`.
"""

import argparse
import json
from pathlib import Path

import polars as pl

from curtamap.previsao.avaliacao import choose_threshold, metrics

CELLS = {
    "corte": ("ap", ["historico", "mesmo_slot_ultimo_dia", "ultimo_valor"], True),
}
MIN_WINS = 6


def thresholds(predictions: pl.DataFrame) -> dict[str, float]:
    return {
        source: round(choose_threshold(f["y_corte"].to_numpy(), f["p_corte"].to_numpy()), 4)
        for (source,), f in predictions.partition_by("fonte", as_dict=True).items()
    }


def decide(table: pl.DataFrame) -> pl.DataFrame:
    rows = []
    for (source,), frame in sorted(table.partition_by("fonte", as_dict=True).items()):
        for cell, (metric, baselines, higher) in CELLS.items():
            model = frame[f"{metric}_modelo"]
            best = frame.select(
                (pl.max_horizontal if higher else pl.min_horizontal)(
                    [f"{metric}_{b}" for b in baselines]
                )
            ).to_series()
            best_mean = {b: frame[f"{metric}_{b}"].mean() for b in baselines}
            best_name = (max if higher else min)(best_mean, key=best_mean.get)
            wins = int(((model > best) if higher else (model < best)).sum())
            mean_win = (
                (model.mean() > best_mean[best_name])
                if higher
                else (model.mean() < best_mean[best_name])
            )
            rows.append(
                {
                    "fonte": source,
                    "celula": cell,
                    "metrica": metric,
                    "modelo_media": model.mean(),
                    "melhor_baseline": best_name,
                    "baseline_media": best_mean[best_name],
                    "meses_vencidos": wins,
                    "meses": frame.height,
                    "adota_modelo": bool(mean_win and wins >= MIN_WINS),
                }
            )
    return pl.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("entrada", type=Path)
    parser.add_argument("saida", type=Path)
    args = parser.parse_args()
    predictions = pl.concat(
        [pl.read_parquet(p) for p in sorted(args.entrada.glob("backtest_*.parquet"))]
    )
    early = predictions.filter(pl.col("mes") < pl.date(2026, 5, 1))
    chosen_early = thresholds(early)
    final = thresholds(predictions)
    table = metrics(predictions, chosen_early)
    decision = decide(table)
    args.saida.mkdir(parents=True, exist_ok=True)
    table.write_csv(args.saida / "metricas_backtest.csv")
    decision.write_csv(args.saida / "decisao_celulas.csv")
    limiares = {"jan_abr": chosen_early, "final_jan_ago": final}
    (args.saida / "limiares.json").write_text(json.dumps(limiares, indent=2), encoding="utf-8")
    (args.entrada / "limiares.json").write_text(json.dumps(final, indent=2), encoding="utf-8")
    with pl.Config(tbl_rows=-1, tbl_cols=-1, tbl_width_chars=250, float_precision=3):
        print(limiares)
        print(decision)
        for prefix in ("ap_", "brier_", "f1_"):
            columns = [c for c in table.columns if c.startswith(prefix)]
            print(table.select("fonte", "periodo", *columns))
        print(
            table.select(
                "fonte",
                "periodo",
                "prevalencia",
                "recall_alerta",
                "precisao_alerta",
            )
        )


if __name__ == "__main__":
    main()
