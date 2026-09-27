"""Arquivo de avisos emitidos: um aviso por dia-alvo, emitido às 20h da véspera.

Setembro de 2026 foi a validação final congelada (`docs/reports/nova-abordagem/README.md`,
seção 3). Encerrada a validação, os avisos de setembro passam a ser exibidos pelo painel
como demonstração do produto. Eles são convertidos das previsões avaliadas
(`previsoes_sem_rotulo.parquet`) sem repontuar, então a chance exibida é a mesma que produziu
as métricas. Nenhum modelo nem limiar é ajustado.

O arquivo não traz o que aconteceu depois. O painel mostra só o que se sabia às 20h da
véspera, como no uso real.

Uso: `uv run python -m zelo.previsao.avisos --modelo models/previsao/<artefato>.joblib`.
"""

import argparse
from datetime import datetime, time, timedelta
from pathlib import Path

import polars as pl

from zelo.config import settings
from zelo.contracts import SOURCES
from zelo.data_contract import SPECS
from zelo.forecasting import ENTITY_ATTRIBUTES
from zelo.previsao.calendario import EMISSION_TIME
from zelo.previsao.modelo import DailyForecaster, DailyModel
from zelo.previsao.setembro import DIRECTORY, read_september

ARCHIVE = settings.data_dir / "processed" / "avisos.parquet"
_KEY = ["fonte", "id_ons"]


def build_archive(
    predictions: pl.DataFrame, attributes: pl.DataFrame, forecaster: DailyForecaster
) -> pl.DataFrame:
    frames = []
    for (dia, ultimo), rows in predictions.group_by(["dia", "ultimo_dia"]):
        emitted = datetime.combine(dia - timedelta(days=1), EMISSION_TIME)
        frames.append(
            forecaster.from_rows(
                rows,
                datetime.combine(dia, time()),
                datetime.combine(ultimo + timedelta(days=1), time()),
                generated_at=emitted,
                emitted_at=emitted,
            )
        )
    return (
        pl.concat(frames)
        .join(attributes.select(*_KEY, *ENTITY_ATTRIBUTES), on=_KEY, how="left")
        .sort([*_KEY, "t0", "horizonte"])
    )


def entity_attributes(history: pl.DataFrame) -> pl.DataFrame:
    """Nome, UF e subsistema mais recentes de cada usina."""
    return (
        history.sort("din_instante")
        .group_by(_KEY)
        .agg(pl.col(c).drop_nulls().last() for c in ENTITY_ATTRIBUTES)
    )


def snapshot_attributes(data_dir: Path = settings.data_dir) -> pl.DataFrame:
    """Atributos do snapshot, para usinas que não aparecem na publicação de setembro."""
    frames = [
        pl.scan_parquet(Path(data_dir) / "raw" / SPECS[source].filename).select(
            pl.lit(source).alias("fonte"), "id_ons", "din_instante", *ENTITY_ATTRIBUTES
        )
        for source in SOURCES
    ]
    return entity_attributes(pl.concat(frames).collect())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelo", type=Path, required=True)
    args = parser.parse_args()
    predictions = pl.read_parquet(DIRECTORY / "previsoes_sem_rotulo.parquet")
    forecaster = DailyForecaster(DailyModel.load(args.modelo))
    recent = entity_attributes(read_september(DIRECTORY))
    older = snapshot_attributes().join(recent, on=_KEY, how="anti")
    archive = build_archive(predictions, pl.concat([recent, older]), forecaster)
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    archive.write_parquet(ARCHIVE)
    print(f"{ARCHIVE}: {archive.height} linhas, {archive['t0'].n_unique()} avisos")


if __name__ == "__main__":
    main()
