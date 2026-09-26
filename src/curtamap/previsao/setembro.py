"""Validação final independente em setembro de 2026 (publicação do ONS, fora do snapshot).

Regra do responsável: setembro é aberto uma única vez, depois de a receita estar congelada
num commit. A ordem é fixa e cada passo grava um artefato antes do próximo:

1. `baixar`: salva os Parquet mensais do ONS e um manifesto com data e SHA-256;
2. `prever`: com o modelo congelado, gera as previsões de cada dia-alvo de setembro com a
   informação da emissão das 20h da véspera (snapshot até 31/08 + dias de setembro já
   liberados) e grava as previsões **sem** o rótulo;
3. `avaliar`: junta o rótulo observado e calcula as métricas por semana e no mês.

A publicação atual usa `''` onde o snapshot usa `NULL`; `derive_targets` já trata texto vazio
como ausência. Agosto republicado em 25/09 não entra: o histórico até 31/08 vem do snapshot.
"""

import argparse
import hashlib
import json
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl

from curtamap.config import settings
from curtamap.contracts import SOURCES
from curtamap.forecasting import _RAW_COLUMNS
from curtamap.previsao.avaliacao import KEEP, load_base, metrics
from curtamap.previsao.calendario import load_calendar
from curtamap.previsao.features import (
    attach_targets,
    base_from_history,
    build_features,
    release_map,
)
from curtamap.previsao.modelo import DailyModel, predict_source
from curtamap.targets import derive_targets

URL = (
    "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/restricao_coff_{fonte}_tm/"
    "RESTRICAO_COFF_{FONTE}_2026_09.parquet"
)
MONTH = date(2026, 9, 1)
DIRECTORY = settings.data_dir / "interim" / "setembro"


def download(directory: Path = DIRECTORY) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {"baixado_em": datetime.now(UTC).isoformat(timespec="seconds"), "arquivos": []}
    for source in SOURCES:
        url = URL.format(fonte=source, FONTE=source.upper())
        path = directory / f"{source}_2026_09.parquet"
        with urllib.request.urlopen(url, timeout=120) as response:
            content = response.read()
            modified = response.headers.get("Last-Modified")
        path.write_bytes(content)
        manifest["arquivos"].append(
            {
                "fonte": source,
                "url": url,
                "last_modified": modified,
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    (directory / "manifesto.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def read_september(directory: Path = DIRECTORY) -> pl.DataFrame:
    """Normaliza a publicação atual para as colunas do snapshot e deriva os alvos."""
    frames = []
    for source in SOURCES:
        frame = pl.read_parquet(directory / f"{source}_2026_09.parquet")
        frames.append(
            frame.with_columns(pl.lit(source).alias("fonte"))
            .select(_RAW_COLUMNS)
            .with_columns(
                pl.col("din_instante").cast(pl.Datetime("us")),
                pl.col("val_geracaolimitada", "val_geracaoreferencia", "val_geracao").cast(
                    pl.Float64, strict=False
                ),
                pl.col("cod_razaorestricao", "cod_origemrestricao").cast(pl.String),
            )
            .filter(pl.col("din_instante") >= datetime.combine(MONTH, datetime.min.time()))
        )
    return derive_targets(pl.concat(frames))


def predict(model_path: Path, directory: Path = DIRECTORY) -> Path:
    calendar = load_calendar()
    model = DailyModel.load(model_path)
    september = base_from_history(read_september(directory))
    base = pl.concat(
        [load_base(settings.data_dir, datetime.combine(MONTH, datetime.min.time())), september]
    ).sort(["fonte", "id_ons", "dia", "slot"])
    last_day = september["dia"].max()
    days = pl.date_range(MONTH, last_day, eager=True).to_list()
    features = build_features(base, release_map(days, calendar))
    parts = [
        predict_source(model.sources[s], features.filter(pl.col("fonte") == s))
        for s in model.sources
    ]
    predicted = pl.concat(parts, how="diagonal_relaxed").with_columns(
        pl.lit(model.model_id).alias("modelo_id")
    )
    path = directory / "previsoes_sem_rotulo.parquet"
    predicted.drop([c for c in predicted.columns if c.startswith("y_")]).sort(
        ["fonte", "id_ons", "dia", "slot"]
    ).write_parquet(path)
    return path


def evaluate(model_path: Path, directory: Path = DIRECTORY) -> pl.DataFrame:
    model = DailyModel.load(model_path)
    predictions = pl.read_parquet(directory / "previsoes_sem_rotulo.parquet")
    truth = base_from_history(read_september(directory))
    scored = attach_targets(predictions, truth).filter(pl.col("y_corte").is_not_null())
    thresholds = {s: m.threshold for s, m in model.sources.items()}
    columns = [c for c in KEEP if c in scored.columns]
    weekly = scored.select(columns).with_columns(
        (pl.col("dia") - pl.duration(days=pl.col("dia").dt.weekday())).alias("mes")
    )
    monthly = scored.select(columns).with_columns(pl.lit(MONTH).alias("mes"))
    table = pl.concat(
        [
            metrics(weekly, thresholds).with_columns(pl.lit("semana").alias("recorte")),
            metrics(monthly, thresholds).with_columns(pl.lit("mes").alias("recorte")),
        ]
    )
    table.write_csv(directory / "metricas_setembro.csv")
    return table


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("passo", choices=["baixar", "prever", "avaliar"])
    parser.add_argument("--modelo", type=Path)
    args = parser.parse_args()
    if args.passo == "baixar":
        print(json.dumps(download(), indent=2))
    elif args.passo == "prever":
        print(predict(args.modelo))
    else:
        with pl.Config(tbl_rows=-1, tbl_cols=-1):
            print(evaluate(args.modelo))


if __name__ == "__main__":
    main()
