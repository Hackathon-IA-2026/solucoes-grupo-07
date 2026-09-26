"""Tabelas, escolhas e gráficos do experimento a partir das previsões gravadas.

    uv run python -m curtamap.experimentos.rede_temporal.avaliar selecao
    uv run python -m curtamap.experimentos.rede_temporal.avaliar final

- `selecao`: métricas de jan–abr/2026 e escolhas pré-registradas: melhor variante do HGB por
  fonte (AP na ocorrência; WAPE diário no volume) e melhor configuração da rede (WAPE diário
  eólico médio).
- `final`: candidatos congelados em mai–ago/2026 e em setembro; impacto do limiar; diagnóstico
  de fevereiro; gráficos.

Todas as comparações usam as mesmas linhas (interseção das colunas dos candidatos).
"""

import argparse
import json
from datetime import date
from pathlib import Path

import polars as pl

from curtamap.experimentos.rede_temporal.dados import (
    EVALUATION_MONTHS,
    OUTPUT,
    SELECTION_MONTHS,
    month_key,
)
from curtamap.experimentos.rede_temporal.limiar import choose_threshold_fixed, round_preserving
from curtamap.experimentos.rede_temporal.metricas import metric_table

REPORT = Path("docs/reports/experimento-rede-temporal")
KEY = ["fonte", "id_ons", "dia", "slot"]
HGB_VARIANTS = [
    "B0_original",
    "B1_mudanca",
    "B2_janela180",
    "B3_recencia60",
    "B4_hp_rapido",
    "B5_hp_suave",
]
NETS = ["C_gru64_k28", "C_gru32_k14"]


def load_predictions(output: Path, months: list[date]) -> pl.DataFrame:
    frames = []
    for month in months:
        for path in sorted((output / "pred").glob(f"{month_key(month)}_*.parquet")):
            frame = pl.read_parquet(path)
            net = path.with_name(f"rede_{path.name}")
            if net.exists():
                frame = frame.join(pl.read_parquet(net), on=KEY, how="left")
            frames.append(frame.with_columns(pl.lit(month).alias("mes")))
    return pl.concat(frames, how="diagonal_relaxed")


def add_served(frame: pl.DataFrame) -> pl.DataFrame:
    """Composição servida pelo produto: volume eólico do histórico, com o HGB sem histórico."""
    wind = pl.col("fonte") == "eolica"
    return frame.with_columns(
        pl.col("p_B0_original").alias("p_servido"),
        pl.when(wind)
        .then(pl.coalesce(pl.col("vol_hist_28d").cast(pl.Float64), pl.col("v_B0_original")))
        .otherwise(pl.col("v_B0_original"))
        .alias("v_servido"),
    )


def choose_thresholds(frame: pl.DataFrame, candidates: list[str], *, until: date) -> dict:
    """Limiar F1 corrigido por fonte × candidato, só com os meses anteriores a `until`."""
    early = frame.filter(pl.col("mes") < until)
    out = {}
    for (source,), part in early.partition_by("fonte", as_dict=True).items():
        for candidate in candidates:
            column = f"p_{candidate}"
            if column not in part.columns:
                continue
            valid = part.filter(pl.col(column).is_not_null())
            p = valid[column].to_numpy()
            threshold = choose_threshold_fixed(valid["y_corte"].to_numpy(), p)
            out[(source, candidate)] = round_preserving(threshold, p, 4)
    return out


def diverged_volume(frame: pl.DataFrame, candidates: list[str], factor: float = 10.0) -> set:
    """Candidatos com volume não finito ou acima de `factor` × o maior volume real da fonte.

    Emenda de 26/09/2026 ao protocolo: a Poisson do HGB divergiu em algumas variantes; uma
    receita que diverge em qualquer dobra de qualquer fonte fica inelegível para volume.
    """
    out = set()
    for _, part in frame.partition_by("fonte", as_dict=True).items():
        limit = factor * part["y_volume"].max()
        for candidate in candidates:
            v = part[f"v_{candidate}"]
            if (~v.is_finite()).any() or v.max() > limit:
                out.add(candidate)
    return out


def _monthly(table: pl.DataFrame) -> pl.DataFrame:
    return table.filter(pl.col("periodo") != "agregado")


def select_best(table: pl.DataFrame, candidates: list[str], metric: str, *, higher: bool) -> dict:
    means = (
        _monthly(table)
        .filter(pl.col("candidato").is_in(candidates))
        .group_by("fonte", "candidato")
        .agg(pl.col(metric).mean())
        .sort(["fonte", metric, "candidato"], descending=[False, higher, False])
    )
    return {s: f["candidato"][0] for (s,), f in means.partition_by("fonte", as_dict=True).items()}


def monthly_wins(
    table: pl.DataFrame, candidate: str, reference: str, metric: str, *, higher: bool
) -> pl.DataFrame:
    monthly = _monthly(table)
    a = monthly.filter(pl.col("candidato") == candidate).select("fonte", "periodo", metric)
    b = monthly.filter(pl.col("candidato") == reference).select(
        "fonte", "periodo", pl.col(metric).alias("_ref")
    )
    joined = a.join(b, on=["fonte", "periodo"])
    better = pl.col(metric) > pl.col("_ref") if higher else pl.col(metric) < pl.col("_ref")
    return (
        joined.group_by("fonte")
        .agg(
            better.sum().alias("meses_vencidos"),
            pl.len().alias("meses"),
            pl.col(metric).mean().alias("media_candidato"),
            pl.col("_ref").mean().alias("media_referencia"),
        )
        .with_columns(
            pl.lit(candidate).alias("candidato"),
            pl.lit(reference).alias("referencia"),
            pl.lit(metric).alias("metrica"),
        )
        .sort("fonte")
    )


def error_concentration(frame: pl.DataFrame, column: str) -> pl.DataFrame:
    """Erro absoluto por usina, em ordem decrescente, com parcela e parcela acumulada."""
    per_plant = (
        frame.group_by("fonte", "id_ons")
        .agg(
            (pl.col("y_volume") - pl.col(column)).abs().sum().alias("erro_abs_mwmed"),
            (pl.col("y_volume").sum() * 0.5).alias("energia_real_mwh"),
            (pl.col(column).sum() * 0.5).alias("energia_prevista_mwh"),
        )
        .sort("erro_abs_mwmed", descending=True)
    )
    total = per_plant["erro_abs_mwmed"].sum()
    return per_plant.with_columns(
        (pl.col("erro_abs_mwmed") / total).alias("parcela_erro"),
        (pl.col("erro_abs_mwmed").cum_sum() / total).alias("parcela_acumulada"),
    )


def seed_summary(table: pl.DataFrame, config: str, seeds: list[int]) -> pl.DataFrame:
    """Média e desvio entre sementes, como um candidato `<config>_sementes`."""
    names = [f"{config}_s{s}" for s in seeds]
    metrics = [c for c in table.columns if table[c].dtype.is_float()]
    part = table.filter(pl.col("candidato").is_in(names))
    grouped = part.group_by("fonte", "periodo").agg(
        pl.col("n").first(),
        pl.col("linhas_sem_previsao").first(),
        *(pl.col(m).mean() for m in metrics),
        *(pl.col(m).std().alias(f"{m}_desvio") for m in ("ap", "wape", "wape_diario", "vies")),
    )
    return grouped.with_columns(pl.lit(f"{config}_sementes").alias("candidato"))


# --------------------------------------------------------------------------------------
# Seleção (jan–abr)


def run_selection(output: Path, report: Path) -> dict:
    frame = add_served(load_predictions(output, SELECTION_MONTHS))
    nets = [f"{n}_s0" for n in NETS if f"p_{n}_s0" in frame.columns]
    candidates = ["historico", "servido", *HGB_VARIANTS, *nets]
    thresholds = choose_thresholds(frame, candidates, until=EVALUATION_MONTHS[0])
    table = metric_table(frame, candidates, thresholds)
    report.mkdir(parents=True, exist_ok=True)
    table.write_csv(report / "selecao_metricas.csv")
    diverged = diverged_volume(frame, HGB_VARIANTS)
    stable = [v for v in HGB_VARIANTS if v not in diverged]
    choices = {
        "hgb_ocorrencia": select_best(table, HGB_VARIANTS, "ap", higher=True),
        "hgb_volume": select_best(table, stable, "wape_diario", higher=False),
        "hgb_volume_sem_emenda": select_best(table, HGB_VARIANTS, "wape_diario", higher=False),
        "volume_divergente": sorted(diverged),
        "rede": select_best(
            table.filter(pl.col("fonte") == "eolica"), nets, "wape_diario", higher=False
        )
        .get("eolica", "")
        .removesuffix("_s0"),
        "limiares_selecao": {f"{s}|{c}": t for (s, c), t in thresholds.items()},
        "criterio": "médias das 4 dobras jan–abr/2026; AP (ocorrência), WAPE diário (volume)",
    }
    summary = (
        _monthly(table)
        .group_by("fonte", "candidato")
        .agg(pl.col("ap", "brier", "f1", "wape", "wape_diario", "vies", "mae_mwmed").mean())
        .sort("fonte", "wape_diario")
    )
    summary.write_csv(report / "selecao_resumo.csv")
    (report / "selecao_escolhas.json").write_text(
        json.dumps(choices, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    with pl.Config(tbl_rows=-1, tbl_cols=-1, tbl_width_chars=200, float_precision=4):
        print(summary)
    print(json.dumps(choices, indent=2, ensure_ascii=False, default=str))
    return choices


def freeze(report: Path, seeds: list[int]) -> dict:
    """Congela as escolhas de jan–abr com a configuração completa de cada candidato."""
    from dataclasses import asdict

    from curtamap.experimentos.rede_temporal.executar import NETS
    from curtamap.experimentos.rede_temporal.hgb import VARIANTS
    from curtamap.experimentos.rede_temporal.rede import NetConfig

    choices = json.loads((report / "selecao_escolhas.json").read_text("utf-8"))
    choices["rede"] = choices["rede"].removesuffix("_s0")
    used = sorted({*choices["hgb_ocorrencia"].values(), *choices["hgb_volume"].values()})
    frozen = {
        "hgb_ocorrencia": choices["hgb_ocorrencia"],
        "hgb_volume": choices["hgb_volume"],
        "variantes_hgb": {name: asdict(VARIANTS[name]) for name in used},
        "rede": choices["rede"],
        "config_rede": asdict(NetConfig(**NETS[choices["rede"]])),
        "sementes": seeds,
        "limiares": "escolhidos pela função corrigida nas previsões de jan–abr de cada candidato",
    }
    (report / "congelamento.json").write_text(
        json.dumps(frozen, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    return frozen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("passo", choices=["selecao", "congelar", "final"])
    parser.add_argument("--sementes", nargs="+", type=int, default=[0, 1, 2])
    parser.add_argument("--saida", type=Path, default=OUTPUT)
    parser.add_argument("--relatorio", type=Path, default=REPORT)
    args = parser.parse_args()
    if args.passo == "selecao":
        run_selection(args.saida, args.relatorio)
    elif args.passo == "congelar":
        print(json.dumps(freeze(args.relatorio, args.sementes), indent=2, ensure_ascii=False))
    else:
        from curtamap.experimentos.rede_temporal.final import run_final

        run_final(args.saida, args.relatorio)


if __name__ == "__main__":
    main()
