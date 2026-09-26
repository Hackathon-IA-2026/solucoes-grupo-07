"""Avaliação dos candidatos congelados, impacto do limiar, fevereiro, custos e gráficos.

Lê `congelamento.json` (escrito antes das rodadas finais) e as previsões gravadas. Nada aqui
escolhe modelo: as escolhas vieram de jan–abr.
"""

import hashlib
import json
import platform
import subprocess
from datetime import date
from importlib import metadata
from pathlib import Path

import numpy as np
import polars as pl

from curtamap.config import settings
from curtamap.data_contract import SPECS
from curtamap.experimentos.rede_temporal.avaliar import (
    add_served,
    choose_thresholds,
    error_concentration,
    load_predictions,
    monthly_wins,
    seed_summary,
)
from curtamap.experimentos.rede_temporal.dados import (
    EVALUATION_MONTHS,
    HOLDOUT_DAY,
    SELECTION_MONTHS,
    SEPTEMBER,
)
from curtamap.experimentos.rede_temporal.limiar import (
    alert_counts,
    choose_threshold_fixed,
    round_preserving,
)
from curtamap.experimentos.rede_temporal.metricas import metric_table
from curtamap.previsao.avaliacao import choose_threshold

RESERVE_MONTH = HOLDOUT_DAY  # arquivos `pred/2026-09-25_*`


def adjusted_columns(frame: pl.DataFrame, freeze: dict) -> pl.DataFrame:
    """HGB ajustado: por fonte, a variante escolhida para ocorrência e a para volume."""
    wind = pl.col("fonte") == "eolica"

    def pick(kind: str, choice: dict) -> pl.Expr:
        return (
            pl.when(wind)
            .then(pl.col(f"{kind}_{choice['eolica']}"))
            .otherwise(pl.col(f"{kind}_{choice['fotovoltaica']}"))
        )

    return frame.with_columns(
        pick("p", freeze["hgb_ocorrencia"]).alias("p_B_ajustado"),
        pick("v", freeze["hgb_volume"]).alias("v_B_ajustado"),
    )


def _prepare(output: Path, months: list[date], freeze: dict) -> pl.DataFrame:
    frame = load_predictions(output, months)
    return adjusted_columns(add_served(frame), freeze)


def _candidates(freeze: dict, frame: pl.DataFrame) -> list[str]:
    nets = [f"{freeze['rede']}_s{s}" for s in freeze["sementes"]]
    nets = [n for n in nets if f"p_{n}" in frame.columns]
    return ["historico", "servido", "B0_original", "B_ajustado", *nets]


def _threshold_table(selection: pl.DataFrame, freeze: dict, candidates: list[str]) -> dict:
    thresholds = choose_thresholds(selection, candidates, until=EVALUATION_MONTHS[0])
    # Sementes sem previsões em jan–abr usam o limiar da semente 0 (declarado no relatório).
    first = f"{freeze['rede']}_s{freeze['sementes'][0]}"
    for source in ("eolica", "fotovoltaica"):
        for seed in freeze["sementes"]:
            name = f"{freeze['rede']}_s{seed}"
            thresholds.setdefault((source, name), thresholds.get((source, first), 0.5))
    return thresholds


def threshold_impact(selection: pl.DataFrame, evaluation: pl.DataFrame) -> pl.DataFrame:
    """Limiar original × corrigido do HGB B0, escolhidos em jan–abr e aplicados depois."""
    rows = []
    for (source,), early in selection.partition_by("fonte", as_dict=True).items():
        y, p = early["y_corte"].to_numpy(), early["p_B0_original"].to_numpy()
        fixed = choose_threshold_fixed(y, p)
        versions = {
            "original_arredondado": round(choose_threshold(y, p), 4),
            "original_sem_arredondar": choose_threshold(y, p),
            "corrigido": fixed,
            "corrigido_arredondado_4": round(fixed, 4),
            "corrigido_arredondamento_seguro": round_preserving(fixed, p, 4),
        }
        late = evaluation.filter(pl.col("fonte") == source)
        blocks = [("selecao_jan_abr", early)]
        blocks += [(k[0], v) for k, v in late.partition_by("bloco", as_dict=True).items()]
        for name, part in blocks:
            y_b, p_b = part["y_corte"].to_numpy(), part["p_B0_original"].to_numpy()
            for version, threshold in versions.items():
                c = alert_counts(y_b, p_b, threshold)
                alerts, positives = c["vp"] + c["fp"], c["vp"] + c["fn"]
                rows.append(
                    {
                        "fonte": source,
                        "bloco": name,
                        "versao": version,
                        "limiar": threshold,
                        **c,
                        "precisao": c["vp"] / alerts if alerts else float("nan"),
                        "recall": c["vp"] / positives if positives else float("nan"),
                        "f1": 2 * c["vp"] / (alerts + positives) if alerts + positives else 0.0,
                        "valores_distintos_p": int(np.unique(p).size),
                        "linhas_selecao": int(p.size),
                    }
                )
    return pl.DataFrame(rows)


def february(selection: pl.DataFrame, report: Path) -> dict:
    """Diagnóstico da eólica em fevereiro: hipóteses verificadas com números."""
    wind = selection.filter(pl.col("fonte") == "eolica")
    feb = wind.filter(pl.col("mes") == date(2026, 2, 1))
    conc = {
        name: error_concentration(feb, f"v_{name}")
        .head(15)
        .with_columns(pl.lit(name).alias("candidato"))
        for name in ("historico", "B0_original")
    }
    pl.concat(list(conc.values())).write_csv(report / "fevereiro_concentracao_erro.csv")
    context = (
        wind.group_by("mes")
        .agg(
            (pl.col("y_volume").sum() * 0.5).alias("energia_real_mwh"),
            (pl.col("v_historico").sum() * 0.5).alias("energia_historico_mwh"),
            (pl.col("v_B0_original").sum() * 0.5).alias("energia_B0_mwh"),
            pl.col("y_corte").mean().alias("prevalencia"),
            pl.col("vol_hist_28d").is_null().mean().alias("parcela_sem_historico"),
            pl.col("cobertura_28d").mean().alias("cobertura_media"),
            pl.col("idade").cast(pl.Float64).mean().alias("idade_media_dias"),
            (pl.col("idade") >= 4).mean().alias("parcela_idade_4_ou_mais"),
        )
        .sort("mes")
    )
    context.write_csv(report / "fevereiro_contexto_mensal.csv")
    daily = (
        wind.filter(pl.col("mes") <= date(2026, 3, 1))
        .group_by("dia")
        .agg(
            (pl.col("y_volume").sum() * 0.5).alias("real_mwh"),
            (pl.col("v_historico").sum() * 0.5).alias("historico_mwh"),
            (pl.col("v_B0_original").sum() * 0.5).alias("B0_mwh"),
            pl.col("idade").first(),
        )
        .sort("dia")
    )
    daily.write_csv(report / "fevereiro_diario.csv")
    top10 = {k: float(v["parcela_acumulada"][9]) for k, v in conc.items()}
    return {"parcela_erro_top10_usinas": top10, "contexto": context.to_dicts()}


def costs(output: Path) -> pl.DataFrame:
    records = [
        json.loads(line) for line in (output / "tempos.jsonl").read_text("utf-8").splitlines()
    ]
    frame = pl.DataFrame(
        [
            {k: v for k, v in r.items() if k != "historico"}
            for r in records
            if r["etapa"] in ("hgb", "rede")
        ],
        infer_schema_length=None,
    )
    return (
        frame.group_by("etapa", "candidato")
        .agg(
            pl.len().alias("ajustes"),
            pl.col("segundos_treino").mean().alias("treino_medio_s"),
            pl.col("segundos_inferencia").mean().alias("inferencia_media_s"),
            (pl.col("epocas").mean() if "epocas" in frame.columns else pl.lit(None)).alias(
                "epocas_medias"
            ),
        )
        .sort("etapa", "candidato")
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest(output: Path, freeze: dict) -> dict:
    raw = settings.data_dir / "raw"
    files = [SPECS[s].filename for s in ("eolica", "fotovoltaica")]
    september = json.loads((output / "setembro" / "manifesto.json").read_text("utf-8"))
    return {
        "commit_base": "7ee94f4",
        "commit_execucao": subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
        ).stdout.strip(),
        "dados": {f: {"sha256": _sha256(raw / f)} for f in files},
        "setembro": september,
        "reserva": HOLDOUT_DAY.isoformat(),
        "dobras_selecao": [m.isoformat() for m in SELECTION_MONTHS],
        "dobras_avaliacao": [m.isoformat() for m in EVALUATION_MONTHS],
        "setembro_bloco": "01–24/09/2026 (não cego)",
        "congelamento": freeze,
        "versoes": {
            "python": platform.python_version(),
            **{p: metadata.version(p) for p in ("polars", "scikit-learn", "torch", "numpy")},
        },
        "maquina": platform.processor(),
    }


def _plots(
    table: pl.DataFrame,
    final: pl.DataFrame,
    candidates: list[str],
    report: Path,
    scatter: list[str],
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = ["#898781", "#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7", "#e87ba4", "#008300"]
    monthly = table.filter(pl.col("periodo").str.len_chars() == 10)
    for metric, label in [("wape_diario", "WAPE diário (usina × dia)"), ("ap", "AP da ocorrência")]:
        fig, axes = plt.subplots(1, 2, figsize=(13, 4.5), sharey=False)
        for ax, source in zip(axes, ("eolica", "fotovoltaica"), strict=True):
            part = monthly.filter(pl.col("fonte") == source)
            for color, candidate in zip(colors, candidates, strict=False):
                series = part.filter(pl.col("candidato") == candidate).sort("periodo")
                if series.is_empty():
                    continue
                ax.plot(
                    series["periodo"].str.slice(0, 7).to_list(),
                    series[metric].to_list(),
                    marker="o",
                    lw=2,
                    color=color,
                    label=candidate,
                )
            ax.axvspan(-0.5, 3.5, color="#f0efec", zorder=0)
            ax.set_title(f"{source} · {label}")
            ax.tick_params(axis="x", rotation=45)
            ax.grid(alpha=0.3)
        axes[0].legend(fontsize=8)
        fig.text(
            0.01, 0.01, "Faixa cinza: dobras de seleção (jan–abr). Setembro não é cego.", fontsize=8
        )
        fig.tight_layout()
        fig.savefig(report / f"grafico_mensal_{metric}.png", dpi=120)
        plt.close(fig)

    daily = final.filter(pl.col("bloco") == "avaliacao_mai_ago")
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    for ax, source in zip(axes, ("eolica", "fotovoltaica"), strict=True):
        part = (
            daily.filter(pl.col("fonte") == source)
            .group_by("dia")
            .agg(pl.col("y_volume").sum() * 0.5, *(pl.col(f"v_{c}").sum() * 0.5 for c in scatter))
        )
        top = part["y_volume"].max()
        for color, c in zip(["#2a78d6", "#1baf7a", "#4a3aa7"], scatter, strict=False):
            ax.scatter(part["y_volume"], part[f"v_{c}"], s=10, alpha=0.6, color=color, label=c)
        ax.plot([0, top], [0, top], color="#52514e", lw=1, ls="--")
        ax.set_xlabel("energia real do dia na fonte (MWh)")
        ax.set_ylabel("energia prevista (MWh)")
        ax.set_title(f"{source} · mai–ago/2026, um ponto por dia")
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(report / "grafico_observado_previsto.png", dpi=120)
    plt.close(fig)


def _february_plot(report: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    daily = pl.read_csv(report / "fevereiro_diario.csv", try_parse_dates=True)
    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.plot(daily["dia"], daily["real_mwh"], color="#0b0b0b", lw=2, label="real")
    ax.plot(daily["dia"], daily["historico_mwh"], color="#898781", lw=1.5, label="histórico 28 d")
    ax.plot(daily["dia"], daily["B0_mwh"], color="#2a78d6", lw=1.5, label="HGB B0")
    ax.set_title("Eólica, jan–mar/2026: energia cortada do dia (soma das usinas, MWh)")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(report / "grafico_fevereiro_diario.png", dpi=120)
    plt.close(fig)


def run_final(output: Path, report: Path) -> None:
    freeze = json.loads((report / "congelamento.json").read_text("utf-8"))
    selection = _prepare(output, SELECTION_MONTHS, freeze).with_columns(
        pl.lit("selecao_jan_abr").alias("bloco")
    )
    blocks = [
        _prepare(output, EVALUATION_MONTHS, freeze).with_columns(
            pl.lit("avaliacao_mai_ago").alias("bloco")
        ),
        _prepare(output, [SEPTEMBER], freeze).with_columns(
            pl.lit("setembro_nao_cego").alias("bloco")
        ),
    ]
    if list((output / "pred").glob("reserva_*.parquet")):
        blocks.append(
            _prepare(output, [RESERVE_MONTH], freeze).with_columns(
                pl.lit("reserva_25_09").alias("bloco")
            )
        )
    final = pl.concat(blocks, how="diagonal_relaxed")
    candidates = _candidates(freeze, final)
    thresholds = _threshold_table(selection, freeze, candidates)

    tables = []
    blocks = [("selecao_jan_abr", selection)]
    blocks += [(k[0], v) for k, v in final.partition_by("bloco", as_dict=True).items()]
    for block, part in blocks:
        present = [c for c in candidates if f"p_{c}" in part.columns]
        table = metric_table(part, present, thresholds)
        nets = [int(c.rsplit("_s", 1)[1]) for c in present if c.startswith(freeze["rede"])]
        if len(nets) > 1:
            table = pl.concat(
                [table, seed_summary(table, freeze["rede"], nets)], how="diagonal_relaxed"
            )
        tables.append(table.with_columns(pl.lit(block).alias("bloco")))
    table = pl.concat(tables, how="diagonal_relaxed")
    table.write_csv(report / "final_metricas.csv")

    evaluation = table.filter(pl.col("bloco") == "avaliacao_mai_ago")
    summary_name = f"{freeze['rede']}_sementes"
    has_summary = evaluation.filter(pl.col("candidato") == summary_name).height > 0
    net_name = summary_name if has_summary else f"{freeze['rede']}_s0"
    wins = []
    for reference in ("servido", "historico", "B0_original"):
        for candidate in ("B_ajustado", net_name, "servido", "B0_original"):
            if candidate == reference:
                continue
            for metric, higher in [
                ("wape_diario", False),
                ("wape", False),
                ("ap", True),
                ("brier", False),
                ("f1", True),
            ]:
                wins.append(monthly_wins(evaluation, candidate, reference, metric, higher=higher))
    pl.concat(wins).write_csv(report / "final_vitorias_mai_ago.csv")

    threshold_impact(selection, final).write_csv(report / "limiar_impacto.csv")
    diagnosis = february(selection, report)
    costs(output).write_csv(report / "custos.csv")
    (report / "manifesto.json").write_text(
        json.dumps(
            {
                **manifest(output, freeze),
                "fevereiro": diagnosis,
                "limiares_aplicados": {f"{s}|{c}": t for (s, c), t in thresholds.items()},
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )
    plot_candidates = ["historico", "servido", "B0_original", "B_ajustado", net_name]
    scatter = ["servido", "B_ajustado", f"{freeze['rede']}_s{freeze['sementes'][0]}"]
    _plots(
        table.filter(pl.col("bloco") != "reserva_25_09"), final, plot_candidates, report, scatter
    )
    _february_plot(report)
    with pl.Config(tbl_rows=-1, tbl_cols=-1, tbl_width_chars=220, float_precision=4):
        summary = (
            table.filter(pl.col("periodo") != "agregado")
            .group_by("bloco", "fonte", "candidato")
            .agg(pl.col("ap", "brier", "f1", "wape", "wape_diario", "vies").mean())
            .sort("bloco", "fonte", "wape_diario")
        )
        print(summary)
        summary.write_csv(report / "final_resumo.csv")
