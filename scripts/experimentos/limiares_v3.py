"""Limiares das faixas da v3 (frente A), congelados no pré-registro (diário 8/n).

k₀ = 0; k₁ e k₂ são os tercis (p33 e p67) da fração **positiva** nos dias-alvo de 01/01 a
31/12/2025, anteriores à primeira dobra, por fonte e por nível, arredondados para 2 casas.
Lê o cache v2 (linhas e ordem do backtest) e calcula `cap_91d` com a base compacta.

Uso: `uv run python scripts/experimentos/limiares_v3.py`.
Saída: `docs/reports/nova-abordagem/v3/faixas.json`.
"""

import json
from datetime import date, datetime
from pathlib import Path

import numpy as np
import polars as pl

from curtamap.config import settings
from curtamap.previsao.avaliacao import load_base
from curtamap.previsao.faixas import CAP_DAYS, CAP_QUANTILE, cap_91d, fracao, rotulo_diario, tercis

CACHE = settings.data_dir / "interim" / "previsao" / "v2"
OUT = Path("docs/reports/nova-abordagem/v3/faixas.json")
START, END = date(2025, 1, 1), date(2025, 12, 31)


def main() -> None:
    base = load_base(settings.data_dir, datetime(2026, 9, 1))
    result = {
        "definicao": {
            "k0": 0.0,
            "k1_k2": "tercis (p33, p67) da fração positiva, 2 casas",
            "periodo": f"{START}..{END} (dias-alvo)",
            "fracao_meia_hora": "y_volume / cap_91d",
            "fracao_diaria": "energia cortada no dia / (cap_91d × 24 h), exige 48 slots",
            "cap_91d": (
                f"p{int(CAP_QUANTILE * 100)} de val_geracaoreferencia em (L − {CAP_DAYS}, L]"
            ),
            "faixas": "sem corte (= 0), leve (0, k1], moderado (k1, k2], severo (> k2)",
        },
        "meia_hora": {},
        "diario": {},
        "contagens": {},
    }
    for source in ("eolica", "fotovoltaica"):
        rows = pl.read_parquet(
            CACHE / f"features_{source}.parquet",
            columns=["fonte", "id_ons", "dia", "slot", "ultimo_dia", "y_volume"],
        )
        cap = cap_91d(base.filter(pl.col("fonte") == source), rows["ultimo_dia"].unique())
        rows = rows.join(cap, on=["fonte", "id_ons", "ultimo_dia"], how="left").with_columns(
            fracao(pl.col("y_volume"), pl.col("cap_91d")).alias("fracao")
        )
        slots = rows.filter(pl.col("dia").is_between(START, END))
        days = rotulo_diario(rows).filter(pl.col("dia").is_between(START, END))
        half = slots["fracao"].drop_nulls().to_numpy()
        daily = days["fracao_dia"].drop_nulls().to_numpy()
        for level, values in (("meia_hora", half), ("diario", daily)):
            k1, k2 = tercis(values, casas=2)
            result[level][source] = {"k0": 0.0, "k1": k1, "k2": k2}
        result["contagens"][source] = {
            "meias_horas": slots.height,
            "meias_horas_fracao_nula": slots["fracao"].null_count(),
            "meias_horas_positivas": int((half > 0).sum()),
            "meias_horas_fracao_acima_de_1": int((half > 1).sum()),
            "dias": days.height,
            "dias_excluidos": days["fracao_dia"].null_count(),
            "dias_sem_48_slots": int((days["slots_validos"] < 48).sum()),
            "dias_cap_zero": int((days["cap_91d"] <= 0).sum()),
            "dias_positivos": int((daily > 0).sum()),
            "p33_p67_exatos_meia_hora": [
                float(np.quantile(half[half > 0], q)) for q in (1 / 3, 2 / 3)
            ],
            "p33_p67_exatos_diario": [
                float(np.quantile(daily[daily > 0], q)) for q in (1 / 3, 2 / 3)
            ],
        }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
