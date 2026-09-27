"""Treina e congela o modelo diário do produto com todo o snapshot do hackathon.

O rótulo mais recente usado é o último dia liberado na emissão que prevê 01/09/2026, para
que nenhuma previsão de setembro use no treino um rótulo ainda não publicado. O limiar de
alerta por fonte vem das previsões fora da amostra do backtest (`avaliacao`), nunca do treino.

Uso: `uv run python -m zelo.previsao.treinar --limiares data/interim/previsao/limiares.json`.
"""

import argparse
import hashlib
import json
import subprocess
from datetime import date, datetime
from pathlib import Path

import polars as pl

from zelo.config import settings
from zelo.previsao.avaliacao import FIRST_DAY, load_base
from zelo.previsao.calendario import load_calendar
from zelo.previsao.features import release_map
from zelo.previsao.modelo import fit

FIRST_FORECAST_DAY = date(2026, 9, 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limiares", type=Path, required=True)
    parser.add_argument("--saida", type=Path, default=settings.model_dir / "previsao")
    parser.add_argument("--manifesto", type=Path, help="JSON versionado do congelamento")
    args = parser.parse_args()
    calendar = load_calendar()
    last_label = release_map([FIRST_FORECAST_DAY], calendar)["ultimo_dia"].item()
    thresholds = json.loads(args.limiares.read_text(encoding="utf-8"))
    base = load_base(settings.data_dir, datetime.combine(FIRST_FORECAST_DAY, datetime.min.time()))
    base = base.filter(pl.col("dia") <= last_label)
    days = pl.date_range(FIRST_DAY, last_label, eager=True).to_list()
    model = fit(
        base,
        release_map(days, calendar),
        last_label,
        dados="data/raw (snapshot do hackathon)",
        limiares_alerta=thresholds,
        treinado_em=datetime.now().isoformat(timespec="seconds"),
    )
    for source, threshold in thresholds.items():
        model.sources[source].threshold = float(threshold)
    path = model.save(args.saida)
    manifest = {
        "modelo_id": model.model_id,
        "artefato": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "commit_receita": subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
        ).stdout.strip(),
        "treino_ate": model.metadata["treino_ate"],
        "limiares_alerta": thresholds,
        "servico": model.metadata["servico"],
        "linhas_treino": model.metadata["linhas_treino"],
    }
    if args.manifesto:
        text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
        args.manifesto.write_text(text, encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
