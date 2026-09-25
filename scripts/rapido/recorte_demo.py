"""Recorte leve de reprodução histórica para o dashboard (25/09/2026).

Aplica a receita confirmada no teste reservado (``curtamap.contexto.replay_frame``) com os
artefatos ``-reservado`` a uma emissão por dia (padrão: 20h, logo após a liberação simulada
das 19h30) de um trecho do período reservado. Grava ``experimentos/rapido-demo/replay.parquet``
(ignorado pelo Git) e um ``manifest.json`` leve com fonte, período, artefatos e contagens.

Uso: ``uv run python scripts/rapido/recorte_demo.py --start 2026-08-18 --days 14``.
"""

import argparse
import json
from datetime import datetime, time, timedelta
from pathlib import Path

import joblib
import polars as pl

from curtamap.contexto import KEYS, baseline_wide, replay_frame
from curtamap.experimental.calendar import load_calendar_manifest
from curtamap.experimental.campaign import _weekend_or_holiday

ROOT = Path(__file__).resolve().parents[2]
EXP = ROOT / "experiments" / "stage2b" / "experimentos"
DATASETS = EXP / "stage2b-datasets" / "scenario=noturno_dia_util"
ARTIFACTS = {
    "fotovoltaica": {"corte": "rapido-fv-final-corte-003-reservado", "causa": None},
    "eolica": {"corte": None, "causa": "rapido-eol-final-causa-005-reservado"},
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=datetime.fromisoformat, default=datetime(2026, 8, 18))
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--t0-time", type=time.fromisoformat, default=time(20, 0))
    args = parser.parse_args()
    calendar = load_calendar_manifest(ROOT / "configs/experimental/calendar-2023-2026.json")
    out = EXP / "rapido-demo"
    out.mkdir(exist_ok=True)
    parts, counts = [], {}
    for source, artifacts in ARTIFACTS.items():
        bundles = {
            k: joblib.load(EXP / run / "model.joblib") if run else None
            for k, run in artifacts.items()
        }
        base = DATASETS / f"source={source}" / "round=reserved"
        for offset in range(args.days):
            day = (args.start + timedelta(days=offset)).date()
            t0 = datetime.combine(day, args.t0_time)
            folder = base / f"date={day.isoformat()}"
            features = (
                pl.read_parquet(folder / "features.parquet")
                .filter(pl.col("t0") == t0)
                .with_columns(_weekend_or_holiday(calendar.calendar))
            )
            baselines = pl.read_parquet(folder / "baselines.parquet").filter(pl.col("t0") == t0)
            frame = features.join(baseline_wide(baselines.lazy()).collect(), on=KEYS, how="left")
            parts.append(replay_frame(frame, source, **bundles))
            counts[f"{source} {day}"] = frame.height
    replay = pl.concat(parts, how="diagonal_relaxed")
    replay.write_parquet(out / "replay.parquet", compression="zstd")
    manifest = {
        "tipo": "reprodução histórica (teste reservado, maio–agosto/2026)",
        "receita": "congelada no commit 8271bf1; ver docs/reports/rapido/resultados-2026-09-25.md",
        "artefatos": ARTIFACTS,
        "inicio": args.start.date().isoformat(),
        "dias": args.days,
        "emissao_diaria": args.t0_time.isoformat(),
        "linhas": replay.height,
        "linhas_por_fonte_dia": counts,
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), "utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k != "linhas_por_fonte_dia"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
