"""Números de apoio ao pitch: quanto da perda chega avisada e quanto uma parada remarcada poupa.

Camada 1 (medida): das previsões de setembro, emitidas às 20h da véspera, qual fração da
energia efetivamente cortada caiu em meias-horas em alerta.

Camada 3 (cenário retrospectivo): uma intervenção flexível de 2 h, que para uma fração `f`
da usina, é posicionada dentro de 06h–18h por estratégias que só usam a informação da emissão.
A perda de cada bloco é pontuada depois, com a geração observada:

- meia-hora sem restrição: a parada tira `f × geração`;
- meia-hora com restrição: a ordem do ONS fixa um teto (a geração observada). A usina só perde
  o que a capacidade restante, `(1 − f) × referência`, deixa de alcançar:
  `max(0, geração − (1 − f) × referência)`.

A segunda regra é **hipótese operacional** (o teto não é redistribuído por causa da parada), não
evidência física. Energia em MWh = MWmed × 0,5 h.
"""

import argparse
import json
from datetime import date
from pathlib import Path

import polars as pl
from sklearn.metrics import average_precision_score

from zelo.previsao.modelo import DailyModel
from zelo.previsao.setembro import DIRECTORY, read_september

KEY = ["fonte", "id_ons", "dia"]
BLOCK = 4  # meias-horas: 2 h
FIRST_START = 12  # 06h00
LAST_START = 32  # bloco 16h00–18h00
FIXED_START = 16  # 08h00–10h00, referência ilustrativa
FRACTIONS = (0.05, 0.10, 0.25, 0.50)
PRICES = (100.0, 200.0, 300.0)  # R$/MWh, cenário declarado, sem fonte
DEFAULT_OUTPUT = Path("docs/reports/pitch-impacto")


def stop_loss_mwh(fraction: float) -> pl.Expr:
    """Energia (MWh) que uma parada da fração `fraction` tira em cada meia-hora."""
    if not 0 < fraction <= 1:
        raise ValueError("fraction deve estar em (0, 1]")
    free = fraction * pl.col("geracao")
    capped = (pl.col("geracao") - (1 - fraction) * pl.col("referencia")).clip(lower_bound=0)
    return pl.when(pl.col("limitada")).then(capped).otherwise(free) * 0.5


def observed(september: pl.DataFrame) -> pl.DataFrame:
    """Uma linha por usina × meia-hora com o observado; linhas de volume inválido saem."""
    moment = pl.col("din_instante")
    return september.filter(pl.col("volume_valido") & pl.col("val_geracao").is_not_null()).select(
        "fonte",
        "id_ons",
        moment.dt.date().alias("dia"),
        (moment.dt.hour() * 2 + moment.dt.minute() // 30).cast(pl.Int8).alias("slot"),
        pl.col("restricao_registrada").alias("limitada"),
        pl.col("corte_positivo").alias("corte"),
        pl.col("energia_mwh"),
        pl.col("val_geracao").alias("geracao"),
        pl.col("val_geracaoreferencia").alias("referencia"),
    )


def coverage(scored: pl.DataFrame, thresholds: dict[str, float]) -> pl.DataFrame:
    """Camada 1 por fonte. `scored` traz `p_corte` (nulo = sem previsão) e o observado."""
    rows = []
    for source, frame in sorted(scored.partition_by("fonte", as_dict=True).items()):
        source = source[0]
        alert = (pl.col("p_corte") >= thresholds[source]).fill_null(False)
        frame = frame.with_columns(alert.alias("alerta"))
        predicted = frame.filter(pl.col("p_corte").is_not_null())
        cut = frame.filter(pl.col("corte"))
        days = frame.group_by(KEY).agg(pl.col("corte").any(), pl.col("alerta").any())
        cut_days = days.filter(pl.col("corte"))
        # Controle: o `historico` com o mesmo número de meias-horas em alerta.
        budget = int(predicted["alerta"].sum())
        history = predicted.sort("hist_28d", descending=True).with_row_index("_ordem")
        history_cut = history.filter(pl.col("corte"))
        rows.append(
            {
                "fonte": source,
                "ap": average_precision_score(
                    predicted["corte"].to_numpy(), predicted["p_corte"].to_numpy()
                ),
                "recall_meia_hora": cut["alerta"].mean(),
                "precisao_meia_hora": frame.filter(pl.col("alerta"))["corte"].mean(),
                "energia_cortada_mwh": cut["energia_mwh"].sum(),
                "energia_avisada_mwh": cut.filter(pl.col("alerta"))["energia_mwh"].sum(),
                "fracao_energia_avisada": cut.filter(pl.col("alerta"))["energia_mwh"].sum()
                / cut["energia_mwh"].sum(),
                "taxa_alerta": predicted["alerta"].mean(),
                "fracao_energia_historico_mesmo_n": history_cut.filter(pl.col("_ordem") < budget)[
                    "energia_mwh"
                ].sum()
                / cut["energia_mwh"].sum(),
                "meias_horas_cortadas_sem_previsao": cut["p_corte"].null_count(),
                "usina_dias_com_corte": cut_days.height,
                "fracao_usina_dias_avisados": cut_days["alerta"].mean(),
            }
        )
    return pl.DataFrame(rows)


def block_table(scored: pl.DataFrame, fraction: float) -> pl.DataFrame:
    """Uma linha por usina × dia × início de bloco completo dentro da janela."""
    frame = scored.sort([*KEY, "slot"]).with_columns(stop_loss_mwh(fraction).alias("perda"))
    columns = {"p_corte": "zelo", "hist_28d": "historico", "ref_hist_28d": "potencial"}
    shifted = [
        pl.col(c).shift(-k).over(KEY).alias(f"{c}_{k}")
        for c in [*columns, "perda", "slot"]
        for k in range(BLOCK)
    ]
    frame = frame.with_columns(shifted)
    contiguous = pl.all_horizontal(
        [pl.col(f"slot_{k}") == pl.col("slot") + k for k in range(BLOCK)]
    ).fill_null(False)
    complete = pl.all_horizontal(
        [pl.col(f"{c}_{k}").is_not_null() for c in [*columns, "perda"] for k in range(BLOCK)]
    )
    return frame.filter(
        pl.col("slot").is_between(FIRST_START, LAST_START) & contiguous & complete
    ).select(
        *KEY,
        pl.col("slot").alias("inicio"),
        *(
            pl.mean_horizontal([pl.col(f"{c}_{k}") for k in range(BLOCK)]).alias(name)
            for c, name in columns.items()
        ),
        pl.sum_horizontal([pl.col(f"perda_{k}") for k in range(BLOCK)]).alias("perda"),
        pl.max_horizontal([pl.col(f"p_corte_{k}") for k in range(BLOCK)]).alias("p_max"),
    )


def choose(blocks: pl.DataFrame, thresholds: dict[str, float]) -> pl.DataFrame:
    """Perda (MWh) do bloco escolhido por estratégia, por usina × dia. Empate: o mais cedo."""
    expected = LAST_START - FIRST_START + 1
    blocks = blocks.filter(pl.len().over(KEY) == expected)

    def pick(score: str, descending: bool, name: str) -> pl.DataFrame:
        return (
            blocks.sort([*KEY, score, "inicio"], descending=[False] * 3 + [descending, False])
            .group_by(KEY, maintain_order=True)
            .first()
            .select(*KEY, pl.col("perda").alias(name), pl.col("inicio").alias(f"inicio_{name}"))
        )

    result = (
        pick("zelo", True, "zelo")
        .join(pick("historico", True, "historico"), on=KEY)
        .join(pick("potencial", False, "menor_potencial"), on=KEY)
        .join(pick("perda", False, "oraculo"), on=KEY)
        .join(
            blocks.filter(pl.col("inicio") == FIXED_START).select(
                *KEY, pl.col("perda").alias("fixo_08h")
            ),
            on=KEY,
        )
    )
    alerted = (
        blocks.with_columns(
            (pl.col("p_max") >= pl.col("fonte").replace_strict(thresholds)).alias("alerta")
        )
        .group_by(KEY)
        .agg(pl.col("alerta").any().alias("dia_com_alerta"))
    )
    return result.join(alerted, on=KEY).with_columns(
        # Política do produto: só sugere remarcar quando há alerta na janela; senão, mantém
        # a regra simples de menor potencial.
        pl.when(pl.col("dia_com_alerta"))
        .then(pl.col("zelo"))
        .otherwise(pl.col("menor_potencial"))
        .alias("zelo_so_alerta")
    )


def summarize(choices: pl.DataFrame, fraction: float) -> pl.DataFrame:
    """Economia média do Zelo contra cada referência, em MWh por intervenção."""
    rows = []
    references = ["fixo_08h", "historico", "menor_potencial"]
    for source, frame in sorted(choices.partition_by("fonte", as_dict=True).items()):
        for subset, part in [("todos", frame), ("dias_com_alerta", frame.filter("dia_com_alerta"))]:
            for strategy in ["zelo", "zelo_so_alerta"]:
                for reference in references:
                    saving = part[reference] - part[strategy]
                    rows.append(
                        {
                            "fonte": source[0],
                            "fracao_parada": fraction,
                            "recorte": subset,
                            "estrategia": strategy,
                            "referencia": reference,
                            "intervencoes": part.height,
                            "perda_referencia_mwh": part[reference].mean(),
                            "perda_estrategia_mwh": part[strategy].mean(),
                            "perda_oraculo_mwh": part["oraculo"].mean(),
                            "economia_media_mwh": saving.mean(),
                            "economia_mediana_mwh": saving.median(),
                            "fracao_melhor": (saving > 1e-9).mean(),
                            "fracao_pior": (saving < -1e-9).mean(),
                            "fracao_do_teto": saving.sum()
                            / (part[reference] - part["oraculo"]).sum(),
                        }
                    )
    return pl.DataFrame(rows)


def run(model_path: Path, output: Path, last_day: date) -> dict:
    model = DailyModel.load(model_path)
    thresholds = {s: m.threshold for s, m in model.sources.items()}
    predictions = pl.read_parquet(DIRECTORY / "previsoes_sem_rotulo.parquet").select(
        *KEY, "slot", "p_corte", "hist_28d", "ref_hist_28d"
    )
    truth = observed(read_september()).filter(pl.col("dia") <= last_day)
    scored = truth.join(predictions, on=[*KEY, "slot"], how="left")
    output.mkdir(parents=True, exist_ok=True)
    layer1 = coverage(scored, thresholds)
    layer1.write_csv(output / "camada1_cobertura.csv")
    present = scored.filter(pl.col("p_corte").is_not_null())
    layer3 = pl.concat(
        [summarize(choose(block_table(present, f), thresholds), f) for f in FRACTIONS]
    )
    layer3.write_csv(output / "camada3_manutencao.csv")
    manifest = {
        "modelo": model.model_id,
        "limiares": thresholds,
        "dias_alvo": f"2026-09-01 a {last_day.isoformat()}",
        "setembro": json.loads((DIRECTORY / "manifesto.json").read_text(encoding="utf-8")),
        "janela": "blocos de 2 h com início entre 06h00 e 16h00",
        "fracoes_parada": FRACTIONS,
        "precos_cenario_rs_mwh": PRICES,
    }
    (output / "manifesto.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"camada1": layer1, "camada3": layer3}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelo", type=Path, required=True)
    parser.add_argument("--saida", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ultimo-dia", type=date.fromisoformat, default=date(2026, 9, 24))
    args = parser.parse_args()
    result = run(args.modelo, args.saida, args.ultimo_dia)
    with pl.Config(tbl_rows=-1, tbl_cols=-1, tbl_width_chars=250):
        print(result["camada1"])
        print(
            result["camada3"].filter(
                (pl.col("fracao_parada") == 0.10) & (pl.col("estrategia") == "zelo")
            )
        )


if __name__ == "__main__":
    main()
