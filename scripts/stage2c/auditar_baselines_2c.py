"""Auditoria única dos baselines usados como comparadores na Etapa 2C.

Uma agregação DuckDB, somente leitura, sobre `stage2b-datasets/.../baselines.parquet` do
cenário principal, restrita às emissões pontuadas de V1–V4 (t0 >= início e t0 + 24h <= fim).
Por fonte, rodada e baseline, mede:

- linhas e taxa de disponibilidade nativa (sem fallback), com os níveis de fallback;
- linhas cujo `source_time + 30 min` passa de `t0` (uso de informação ainda não encerrada);
- idade média do dado usado.

Uso: uv run python scripts/stage2c/auditar_baselines_2c.py [saida.json]
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DATASETS = ROOT / "experiments" / "stage2b" / "experimentos" / "stage2b-datasets"
DEFAULT_OUTPUT = ROOT / "docs" / "reports" / "stage2c" / "auditoria-baselines-2c.json"
ROUNDS = {
    "V1": ("2025-01-01", "2025-05-01"),
    "V2": ("2025-05-01", "2025-09-01"),
    "V3": ("2025-09-01", "2026-01-01"),
    "V4": ("2026-01-01", "2026-05-01"),
}


def main(output: Path) -> int:
    started = time.perf_counter()
    connection = duckdb.connect()
    connection.execute("SET threads = 6")
    connection.execute("SET memory_limit = '12GB'")
    cases = " ".join(
        f"WHEN t0 >= TIMESTAMP '{start}' AND t0 + INTERVAL 24 HOUR <= TIMESTAMP '{end}' "
        f"THEN '{round_id}'"
        for round_id, (start, end) in ROUNDS.items()
    )
    rows = []
    for source in ("eolica", "fotovoltaica"):
        pattern = (
            DATASETS
            / "scenario=noturno_dia_util"
            / f"source={source}"
            / "round=development"
            / "date=*"
            / "baselines.parquet"
        ).as_posix()
        query = f"""
            WITH scored AS (
                SELECT CASE {cases} END AS round_id, baseline_id, native_available,
                       fallback_level, t0, source_time, history_age_hours
                FROM read_parquet('{pattern}')
                WHERE t0 >= TIMESTAMP '2025-01-01' AND t0 < TIMESTAMP '2026-05-01'
            )
            SELECT round_id, baseline_id, fallback_level,
                   count(*) AS rows,
                   sum(CASE WHEN native_available THEN 1 ELSE 0 END) AS native_rows,
                   sum(CASE WHEN source_time + INTERVAL 30 MINUTE > t0 THEN 1 ELSE 0 END)
                       AS source_after_t0,
                   sum(CASE WHEN source_time IS NULL THEN 1 ELSE 0 END) AS source_time_null,
                   avg(history_age_hours) AS mean_age_hours
            FROM scored
            WHERE round_id IS NOT NULL
            GROUP BY ALL
            ORDER BY ALL
        """
        for record in connection.execute(query).fetchall():
            rows.append(
                dict(
                    zip(
                        (
                            "round",
                            "baseline_id",
                            "fallback_level",
                            "rows",
                            "native_rows",
                            "source_after_t0",
                            "source_time_null",
                            "mean_age_hours",
                        ),
                        record,
                        strict=True,
                    ),
                    source=source,
                )
            )
        print(source, "ok", round(time.perf_counter() - started, 1), "s", flush=True)
    result = {
        "scenario": "noturno_dia_util",
        "rounds": ROUNDS,
        "seconds": time.perf_counter() - started,
        "groups": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=1, ensure_ascii=False, default=str), "utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT))
