"""Leitura do cache v3 e regra de adoção da v3 (protocolo no diário 8/n; fora do produto).

As dobras são as da v2 (`v2_comum.folds`): cada mês M de jan–ago/2026 treina com dias-alvo
em (L_M − 365, L_M] e testa nos dias de M.
"""

import json
from pathlib import Path

import numpy as np
import polars as pl
from v2_comum import ORDER, folds, matrix  # noqa: F401  (reexportados para os runners)

from curtamap.config import settings

CACHE = settings.data_dir / "interim" / "previsao" / "v3"
REPORT = Path("docs/reports/nova-abordagem/v3")
NOT_FEATURES = {"fonte", "id_ons", "id_estado", "dia", "ultimo_dia", "grupo_restricao"}
SEEDS = (0, 1, 2)
MIN_MONTHS = 6


def _cast(frame: pl.DataFrame) -> pl.DataFrame:
    numeric = [
        c
        for c in frame.columns
        if c not in NOT_FEATURES and not c.startswith("y_") and frame[c].dtype.is_numeric()
    ]
    return frame.with_columns(pl.col(numeric).cast(pl.Float32))


def load(source: str) -> pl.DataFrame:
    """Cache v3 por meia-hora, ordenado como em `modelo.fit` (reproduz a v1)."""
    return _cast(pl.read_parquet(CACHE / f"features_{source}.parquet").sort(ORDER))


def load_daily(source: str) -> pl.DataFrame:
    """Tabela usina × dia do cache v3."""
    return _cast(
        pl.read_parquet(CACHE / f"diario_{source}.parquet").sort(["fonte", "id_ons", "dia"])
    )


def thresholds() -> dict:
    return json.loads((REPORT / "faixas.json").read_text(encoding="utf-8"))


def noise(values: pl.DataFrame, metric: str, variants: list[str]) -> pl.DataFrame:
    """Maior diferença da métrica entre réplicas (variantes com sementes) por mês."""
    return (
        values.filter(pl.col("variante").is_in(variants))
        .group_by("mes")
        .agg((pl.col(metric).max() - pl.col(metric).min()).alias("ruido"))
    )


def decide(
    values: pl.DataFrame,
    metric: str,
    candidate: str,
    reference: str,
    noise_by_month: pl.DataFrame,
    higher_is_better: bool = True,
) -> dict:
    """Regra da seção 1: vence na média e em ≥ 6 de 8 meses com margem acima do ruído."""
    pick = lambda name: values.filter(pl.col("variante") == name).select(  # noqa: E731
        "mes", pl.col(metric).alias(name)
    )
    table = pick(candidate).join(pick(reference), on="mes").join(noise_by_month, on="mes")
    sign = 1.0 if higher_is_better else -1.0
    margin = sign * (table[candidate] - table[reference])
    mean_c, mean_r = float(table[candidate].mean()), float(table[reference].mean())
    wins = int((margin > table["ruido"]).sum())
    better = sign * (mean_c - mean_r) > 0
    return {
        "candidato": candidate,
        "referencia": reference,
        "metrica": metric,
        "media_candidato": mean_c,
        "media_referencia": mean_r,
        "meses": table.height,
        "meses_vencidos_acima_ruido": wins,
        "meses_vencidos_sem_ruido": int((margin > 0).sum()),
        "ruido_medio": float(table["ruido"].mean()),
        "adotado": bool(better and wins >= MIN_MONTHS),
    }


def reliability(y: np.ndarray, p: np.ndarray, bins: int = 10) -> list[dict]:
    """Confiabilidade em bins iguais de probabilidade: média prevista × frequência observada."""
    index = np.minimum((np.clip(p, 0, 1) * bins).astype(int), bins - 1)
    out = []
    for b in range(bins):
        mask = index == b
        if mask.any():
            out.append(
                {
                    "bin": b,
                    "n": int(mask.sum()),
                    "p_media": float(p[mask].mean()),
                    "freq_observada": float(y[mask].mean()),
                }
            )
    return out
