"""Cache da v3 (fora do produto): estende o cache v2 com faixas, restrição e causa em 91 d.

Mantém exatamente as linhas do cache v2 (a ordem afeta os bins do HGB) e acrescenta, com
dados até o último dia liberado L de cada dia-alvo (protocolo no diário 8/n):

- `cap_91d` e o rótulo `y_fracao` (volume da meia-hora sobre `cap_91d`);
- baselines de excedência por limiar: `exc_hist_k{j}` (frequência em 28 d no slot) e
  `exc_ult_k{j}` (indicador em L);
- frente B: `sin_ene_*` (regime nacional) e `grupo_*` (grupo de restrição);
- frente C: `causa_*_91d` por slot.

Também gera a tabela usina × dia (`diario_<fonte>.parquet`) com o rótulo diário, as
features agregadas e os baselines diários, e os diagnósticos de nulos e de grupos em
`docs/reports/nova-abordagem/v3/`.

Uso: `uv run python scripts/experimentos/cache_features_v3.py`.
"""

import json
from datetime import datetime
from pathlib import Path

import polars as pl

from curtamap.config import settings
from curtamap.data_contract import SPECS
from curtamap.previsao.avaliacao import FIRST_DAY, load_base
from curtamap.previsao.faixas import (
    agregar_diario,
    cap_91d,
    fracao,
    frequencia_excedencia,
    rotulo_diario,
)
from curtamap.previsao.restricoes import (
    causa_slot,
    grupo_restricao,
    nivel_grupo,
    normalizar_restricao,
    regime_nacional,
)
from curtamap.targets import derive_targets

V2 = settings.data_dir / "interim" / "previsao" / "v2"
OUT = settings.data_dir / "interim" / "previsao" / "v3"
REPORT = Path("docs/reports/nova-abordagem/v3")
END = datetime(2026, 9, 1)
HIST_DAYS = 28
POR_SLOT = ["hist_7d", "hist_28d", "hist_91d", "ultimo_slot", "vol_hist_7d", "vol_hist_28d"]
SIN = ["sin_ene_ultimo", "sin_ene_7d", "sin_ene_ultimo_total", "sin_ene_7d_total"]
GRUPO = ["grupo_nivel_ultimo", "grupo_nivel_7d", "grupo_tamanho"]
CAUSA_91 = ["causa_rel_91d", "causa_cnf_91d", "causa_ene_91d"]
DIARIAS = [
    "id_estado",
    "ultimo_dia",
    "usina_nivel_ultimo",
    "usina_nivel_7d",
    "estado_nivel_ultimo",
    "estado_nivel_7d",
    "estado_nivel_28d",
    "estado_ene_7d",
    "idade",
    "dia_semana",
    "feriado",
    *SIN,
    "grupo_restricao",
    *GRUPO,
]


def eventos_locais(source: str) -> pl.DataFrame:
    """Meias-horas com corte positivo e causa CNF/REL, com a restrição normalizada."""
    raw = (
        pl.scan_parquet(settings.data_dir / "raw" / SPECS[source].filename)
        .select(
            "fonte",
            "id_ons",
            pl.col("din_instante").cast(pl.Datetime("us")),
            "val_geracaolimitada",
            "val_geracaoreferencia",
            "val_geracao",
            "cod_razaorestricao",
            "cod_origemrestricao",
            "dsc_restricao",
        )
        .filter(
            pl.col("din_instante").is_between(
                datetime.combine(FIRST_DAY, datetime.min.time()), END, closed="left"
            )
        )
        .collect()
    )
    events = derive_targets(raw).filter(
        pl.col("corte_positivo").fill_null(False), pl.col("causa").is_in(["CNF", "REL"])
    )
    texts = events["dsc_restricao"].drop_nulls().unique()
    mapping = pl.DataFrame(
        {"dsc_restricao": texts, "restricao": [normalizar_restricao(t) for t in texts]},
        schema={"dsc_restricao": pl.String, "restricao": pl.String},
    )
    return events.join(mapping, on="dsc_restricao", how="left").select(
        "fonte", "id_ons", pl.col("din_instante").dt.date().alias("dia"), "restricao"
    )


def excedencias(labels, mapping, ks, chave, prefix=""):
    """Colunas `exc_hist_k{j}` e `exc_ult_k{j}` para cada limiar."""
    out = None
    for j, k in enumerate(ks):
        part = frequencia_excedencia(labels, mapping, k, HIST_DAYS, chave).rename(
            {"freq": f"{prefix}exc_hist_k{j}", "ultimo": f"{prefix}exc_ult_k{j}"}
        )
        out = part if out is None else out.join(part, on=[*chave, "dia"], how="left")
    return out


def diagnosticos(rows: pl.DataFrame, source: str, grupos: pl.DataFrame) -> None:
    columns = ["cap_91d", "y_fracao", *SIN, "grupo_restricao", *GRUPO, *CAUSA_91]
    nulls = (
        rows.group_by(pl.col("dia").dt.truncate("1mo").alias("mes"))
        .agg(
            pl.len().alias("linhas"),
            *(pl.col(c).null_count().truediv(pl.len()).alias(c) for c in columns),
        )
        .sort("mes")
        .with_columns(pl.lit(source).alias("fonte"))
    )
    nulls.write_csv(REPORT / f"nulos_features_{source}.csv")
    sizes = grupos.join(
        grupos.group_by("ultimo_dia", "grupo_restricao").agg(pl.len().alias("tamanho")),
        on=["ultimo_dia", "grupo_restricao"],
    )
    summary = (
        sizes.group_by(pl.col("ultimo_dia").dt.truncate("1mo").alias("mes"))
        .agg(
            pl.col("id_ons").n_unique().alias("usinas_com_grupo"),
            (pl.col("tamanho") == 1).mean().alias("frac_usinas_em_grupo_unitario"),
            pl.col("tamanho").median().alias("mediana_tamanho_por_usina"),
            pl.col("grupo_restricao").n_unique().alias("grupos"),
        )
        .sort("mes")
        .with_columns(pl.lit(source).alias("fonte"))
    )
    summary.write_csv(REPORT / f"grupos_{source}.csv")
    # Usina com ordem local no slot em 91 d, mas sem grupo: só se não houve corte local.
    suspicious = rows.filter(
        pl.col("dia") >= pl.date(2025, 12, 1),
        (pl.col("causa_cnf_91d") > 0) | (pl.col("causa_rel_91d") > 0),
        pl.col("grupo_restricao").is_null(),
    )
    print(
        json.dumps({"fonte": source, "linhas_ordem_local_sem_grupo_desde_dez25": suspicious.height})
    )
    with pl.Config(tbl_rows=-1, tbl_cols=-1, tbl_width_chars=250, float_precision=3):
        print(nulls)
        print(summary)


def main() -> None:
    thresholds = json.loads((REPORT / "faixas.json").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    base = load_base(settings.data_dir, END)
    ultimos_all = pl.concat(
        [
            pl.read_parquet(V2 / f"features_{s}.parquet", columns=["ultimo_dia"])
            for s in ("eolica", "fotovoltaica")
        ]
    )["ultimo_dia"].unique()
    national = regime_nacional(base, ultimos_all)
    for source in ("eolica", "fotovoltaica"):
        rows = pl.read_parquet(V2 / f"features_{source}.parquet").with_row_index("_ordem")
        v2_height = rows.height
        ultimos = rows["ultimo_dia"].unique()
        source_base = base.filter(pl.col("fonte") == source)
        rows = rows.join(
            cap_91d(source_base, ultimos), on=["fonte", "id_ons", "ultimo_dia"], how="left"
        )
        rows = rows.with_columns(fracao(pl.col("y_volume"), pl.col("cap_91d")).alias("y_fracao"))
        mapping = rows.select("dia", "ultimo_dia").unique()
        half = thresholds["meia_hora"][source]
        slot_key = ["fonte", "id_ons", "slot"]
        labels = rows.select(*slot_key, "dia", pl.col("y_fracao").alias("fracao"))
        rows = rows.join(
            excedencias(labels, mapping, [half["k0"], half["k1"], half["k2"]], slot_key),
            on=[*slot_key, "dia"],
            how="left",
        )
        rows = rows.join(national, on=["fonte", "ultimo_dia"], how="left")
        grupos = grupo_restricao(eventos_locais(source), ultimos)
        rows = rows.join(grupos, on=["fonte", "id_ons", "ultimo_dia"], how="left")
        rows = rows.join(
            nivel_grupo(source_base, grupos, ultimos),
            on=["fonte", "id_ons", "ultimo_dia"],
            how="left",
        )
        rows = rows.join(causa_slot(source_base, ultimos), on=[*slot_key, "ultimo_dia"], how="left")
        rows = rows.sort("_ordem").drop("_ordem")
        assert rows.height == v2_height, "o cache v3 precisa ter as linhas do v2"
        rows.write_parquet(OUT / f"features_{source}.parquet")
        diagnosticos(rows, source, grupos)

        daily = rotulo_diario(rows).join(
            agregar_diario(rows, POR_SLOT, DIARIAS), on=["fonte", "id_ons", "dia"]
        )
        day = thresholds["diario"][source]
        daily_labels = daily.select("fonte", "id_ons", "dia", pl.col("fracao_dia").alias("fracao"))
        daily = daily.join(
            excedencias(
                daily_labels, mapping, [day["k0"], day["k1"], day["k2"]], ["fonte", "id_ons"]
            ),
            on=["fonte", "id_ons", "dia"],
            how="left",
        ).sort(["fonte", "id_ons", "dia"])
        daily.write_parquet(OUT / f"diario_{source}.parquet")
        print(
            json.dumps(
                {
                    "fonte": source,
                    "linhas": rows.height,
                    "dias": daily.height,
                    "dias_rotulo_nulo": daily["fracao_dia"].null_count(),
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
