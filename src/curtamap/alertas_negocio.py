"""Causa histórica e avaliação contrafactual de manutenção; nunca previsão de volume.

PLD realizado e geração realizada entram somente depois de escolher a janela.
Não representa faturamento, ressarcimento ou economia comprovada em operação.
"""

import argparse
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl

from curtamap.forecasting import load_history
from curtamap.previsao.alertas import sha256, validate_alerts

KEY = ["fonte", "id_ons"]
CCEE_URL = "https://dadosabertos.ccee.org.br/dataset/pld_horario"
CCEE_DOWNLOAD = "https://pda-download.ccee.org.br/6A5wq97KTCWv_bvs3CqsQQ/content"


def read_pld(path: Path) -> pl.DataFrame:
    raw = pl.read_csv(path, separator=";", infer_schema=False)
    day = pl.when(pl.col("DIA").str.contains("/"))
    day = day.then(pl.col("DIA").str.strptime(pl.Date, "%d/%m/%Y", strict=False)).otherwise(
        pl.concat_str(pl.col("MES_REFERENCIA"), pl.col("DIA").str.pad_start(2, "0")).str.strptime(
            pl.Date, "%Y%m%d", strict=False
        )
    )
    hours = raw["HORA"].cast(pl.Int32)
    if hours.null_count() or not hours.is_between(0, 23).all():
        raise ValueError("HORA precisa usar 0–23, conforme CSV da CCEE")
    prices = raw.select(
        (day.cast(pl.Datetime("us")) + pl.duration(hours=pl.col("HORA").cast(pl.Int32))).alias(
            "hora"
        ),
        pl.col("SUBMERCADO")
        .replace_strict({"NORDESTE": "NE", "NORTE": "N", "SUDESTE": "SE", "SUL": "S"})
        .alias("id_subsistema"),
        pl.col("PLD_HORA")
        .str.replace(",", ".", literal=True)
        .cast(pl.Float64)
        .alias("pld_brl_mwh"),
    )
    if (
        any(prices.null_count().row(0))
        or prices.is_duplicated().any()
        or prices.select("hora", "id_subsistema").is_duplicated().any()
    ):
        raise ValueError("PLD com chave duplicada ou valor ausente")
    if not prices["pld_brl_mwh"].is_finite().all() or (prices["pld_brl_mwh"] < 0).any():
        raise ValueError("PLD inválido")
    return prices


def select_window(
    profile: pl.DataFrame,
    score: str,
    *,
    high: bool = True,
    slots: int = 4,
    start: int = 16,
    end: int = 36,
) -> int | None:
    """Índice de início do bloco completo; usa só o score, nunca verdade futura."""
    if profile.height != 48 or slots < 1 or not 0 <= start <= end - slots <= 48 - slots:
        raise ValueError("Grade ou duração de manutenção inválida")
    values = profile[score].to_numpy()
    candidates = [
        (i, float(np.mean(values[i : i + slots])))
        for i in range(start, end - slots + 1)
        if np.isfinite(values[i : i + slots]).all()
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda pair: (-pair[1] if high else pair[1], pair[0]))[0]


def opportunity_cost(
    profile: pl.DataFrame,
    index: int | None,
    *,
    fraction: float,
    slots: int = 4,
    fixed_price: float | None = None,
) -> float | None:
    if not math.isfinite(fraction) or not 0 < fraction <= 1:
        raise ValueError("Fração indisponível deve estar em (0, 1]")
    if fixed_price is not None and (not math.isfinite(fixed_price) or fixed_price < 0):
        raise ValueError("Preço de cenário inválido")
    if index is None:
        return None
    if index < 0 or slots < 1 or index + slots > profile.height:
        raise ValueError("Janela de custo fora do perfil")
    selected = profile.slice(index, slots)
    generation = selected["geracao_mw"].to_numpy()
    prices = (
        selected["pld_brl_mwh"].to_numpy() if fixed_price is None else np.full(slots, fixed_price)
    )
    if (
        selected.height != slots
        or not np.isfinite(generation).all()
        or not np.isfinite(prices).all()
        or (generation < 0).any()
    ):
        return None
    return float(np.sum(generation * prices) * 0.5 * fraction)


def historical_context(
    history: pl.DataFrame, cutoff: datetime
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Contexto dos 28 dias publicados, [corte − 28d, corte), sem inferir causa futura."""
    past = history.filter(
        pl.col("din_instante") >= cutoff - timedelta(days=28), pl.col("din_instante") < cutoff
    )
    valid = past.filter(pl.col("val_geracao").is_finite() & (pl.col("val_geracao") >= 0))
    generation = (
        valid.with_columns(
            (
                pl.col("din_instante").dt.hour().cast(pl.Int32) * 2
                + pl.col("din_instante").dt.minute() // 30
            ).alias("slot")
        )
        .group_by([*KEY, "slot"])
        .agg(pl.col("val_geracao").mean().alias("geracao_historica_28d"))
    )
    causes = (
        past.filter(pl.col("restricao_registrada"))
        .with_columns(pl.col("causa").fill_null("DESCONHECIDA").alias("causa"))
        .group_by([*KEY, "causa"])
        .agg(pl.len().alias("n_ordens"))
    )
    causes = causes.with_columns(
        (pl.col("n_ordens") / pl.col("n_ordens").sum().over(KEY)).alias("participacao")
    )
    return generation, causes.sort(
        [*KEY, "n_ordens", "causa"], descending=[False, False, True, False]
    )


def evaluate(
    replay: pl.DataFrame, history: pl.DataFrame, prices: pl.DataFrame, fraction: float = 0.1
) -> tuple[pl.DataFrame, pl.DataFrame]:
    validate_alerts(replay)
    observed = history.select(
        *KEY,
        pl.col("din_instante").alias("tau"),
        "id_subsistema",
        pl.col("val_geracao").alias("geracao_mw"),
    )
    if observed.select(*KEY, "tau").is_duplicated().any():
        raise ValueError("Observações duplicadas")
    records, contexts = [], []
    for (day,), forecasts in replay.partition_by("dia", as_dict=True).items():
        cutoff = forecasts["corte_dados"].unique()
        if len(cutoff) != 1:
            raise ValueError("Mais de um corte de publicação no mesmo dia")
        generation, causes = historical_context(history, cutoff.item())
        contexts.append(
            causes.with_columns(
                pl.lit(day).alias("dia"), pl.lit(cutoff.item()).alias("corte_dados")
            )
        )
        decision = forecasts.join(generation, on=[*KEY, "slot"], how="left")
        # Observados anexados só para pontuação ex post; select_window só lê o score.
        joined = (
            decision.join(observed, on=[*KEY, "tau"], how="left", validate="1:1")
            .with_columns(pl.col("tau").dt.truncate("1h").alias("hora"))
            .join(prices, on=["id_subsistema", "hora"], how="left", validate="m:1")
        )
        for (source, entity), profile in joined.partition_by(KEY, as_dict=True).items():
            profile = profile.sort("tau")
            choices = {
                "curtamap": select_window(profile, "p_corte"),
                "fixo_08h": 16,
                "historico_corte": select_window(profile, "hist_28d"),
                "menor_geracao_historica": select_window(
                    profile, "geracao_historica_28d", high=False
                ),
            }
            for scenario, fixed in [
                ("PLD_CCEE_observado", None),
                ("cenario_50", 50.0),
                ("cenario_100", 100.0),
                ("cenario_200", 200.0),
            ]:
                costs = {
                    name: opportunity_cost(profile, i, fraction=fraction, fixed_price=fixed)
                    for name, i in choices.items()
                }
                row = {
                    "fonte": source,
                    "id_ons": entity,
                    "dia": day,
                    "cenario": scenario,
                    "fracao_indisponivel": fraction,
                    "avaliavel": all(c is not None for c in costs.values()),
                }
                row.update({f"custo_{name}_brl": cost for name, cost in costs.items()})
                row.update(
                    {
                        f"inicio_{name}": profile["tau"][i] if i is not None else None
                        for name, i in choices.items()
                    }
                )
                for name in choices:
                    if name != "curtamap":
                        row[f"diferenca_vs_{name}_brl"] = (
                            costs[name] - costs["curtamap"]
                            if costs[name] is not None and costs["curtamap"] is not None
                            else None
                        )
                records.append(row)
    return pl.DataFrame(records), pl.concat(contexts)


def summarize(results: pl.DataFrame) -> pl.DataFrame:
    rows = []
    for (source, scenario), group in results.partition_by(
        ["fonte", "cenario"], as_dict=True
    ).items():
        valid = group.filter(pl.col("avaliavel"))
        for baseline in ("fixo_08h", "historico_corte", "menor_geracao_historica"):
            gain = valid[f"diferenca_vs_{baseline}_brl"].cast(pl.Float64)
            rows.append(
                {
                    "fonte": source,
                    "cenario": scenario,
                    "baseline": baseline,
                    "oportunidades": group.height,
                    "avaliaveis": valid.height,
                    "diferenca_soma_brl": gain.sum() if valid.height else None,
                    "diferenca_media_brl": gain.mean(),
                    "diferenca_mediana_brl": gain.median(),
                    "melhores": int((gain > 0.01).sum()),
                    "piores": int((gain < -0.01).sum()),
                    "empates": int((gain.abs() <= 0.01).sum()),
                    "custo_curtamap_brl": valid["custo_curtamap_brl"].sum()
                    if valid.height
                    else None,
                    "custo_baseline_brl": valid[f"custo_{baseline}_brl"].sum()
                    if valid.height
                    else None,
                }
            )
    return pl.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--pld", type=Path, required=True)
    parser.add_argument("--dados", type=Path, default=Path("data"))
    parser.add_argument("--saida", type=Path, default=Path("data/interim/negocio"))
    args = parser.parse_args()
    replay = pl.read_parquet(args.replay)
    history = load_history(
        args.dados,
        replay["corte_dados"].min() - timedelta(days=28),
        replay["tau"].max() + timedelta(minutes=30),
        sources=tuple(replay["fonte"].unique()),
    )
    prices = read_pld(args.pld)
    results, context = evaluate(replay, history, prices)
    args.saida.mkdir(parents=True, exist_ok=True)
    prefix = args.saida / args.replay.stem
    results.write_parquet(prefix.with_suffix(".parquet"))
    context.write_parquet(args.saida / f"{args.replay.stem}_causas.parquet")
    summary = summarize(results)
    summary.write_csv(prefix.with_suffix(".csv"))
    weekly = []
    for (week,), part in (
        results.with_columns(pl.col("dia").dt.truncate("1w").alias("semana"))
        .partition_by("semana", as_dict=True)
        .items()
    ):
        weekly.append(summarize(part).with_columns(pl.lit(week).alias("semana")))
    pl.concat(weekly).write_csv(args.saida / f"{args.replay.stem}_semanas.csv")
    manifest = {
        "natureza": "contrafactual_retrospectivo_nao_economia_realizada",
        "gerado_em": datetime.now().isoformat(),
        "sha256_replay": sha256(args.replay),
        "sha256_pld": sha256(args.pld),
        "sha256_script": sha256(Path(__file__)),
        "fonte_pld": CCEE_URL,
        "download_pld": CCEE_DOWNLOAD,
        "licenca_pld": "CC-BY-4.0; CCEE; transformação: hora/submercado e junção com ONS",
        "acesso": "download público pelo navegador em 26/09/2026; API/HTTP de terminal bloqueados",
        "horario": "hora civil ONS/CCEE; HORA no CSV 0–23; sem ajuste UTC",
        "preco_disponivel_na_emissao": "não verificado; usado somente ex post",
        "duracao_horas": 2,
        "janela_trabalho": "08h–18h",
        "fracao_indisponivel": 0.1,
        "criterio_curtamap": "maior média de p_corte; desempate mais cedo",
        "custos_adicionais": "mão de obra, mobilização e contratos não incluídos",
        "causa": "distribuição histórica de ordens dos 28 dias publicados; não prevista",
        "oportunidades": results.filter(pl.col("cenario") == "PLD_CCEE_observado").height,
        "sha256_resultados": sha256(prefix.with_suffix(".parquet")),
    }
    prefix.with_suffix(".json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(summary.filter(pl.col("cenario") == "PLD_CCEE_observado").write_csv())


if __name__ == "__main__":
    main()
