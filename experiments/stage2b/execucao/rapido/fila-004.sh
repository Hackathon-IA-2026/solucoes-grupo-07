#!/usr/bin/env bash
# Fila sequencial das runs rápidas (25/09/2026): solar 004 (offset, sem sazonalidade) e eólica 003 na V4.
cd "M:/Bibliotecas/Development/workspaces/hackathon-ia-coppe-2026"
export TMP="Y:/CurtaMap Etapa 2B/temporarios" TEMP="Y:/CurtaMap Etapa 2B/temporarios" POLARS_TEMP_DIR="Y:/CurtaMap Etapa 2B/temporarios/polars" PYTHONIOENCODING=utf-8 PYTHONUTF8=1
DROP=t0_month,t0_day_of_year,tau_month,tau_day_of_year
L=experiments/stage2b/execucao/rapido
for r in 2 1 3 4; do
  uv run python scripts/rapido/treinar_contexto.py --source fotovoltaica --round V$r --task corte_positivo --slots 4 --offset --drop $DROP --run-id rapido-fv-v$r-corte-004 > $L/rapido-fv-v$r-corte-004.log 2>&1; echo "fv V$r 004 exit $?"
done
uv run python scripts/rapido/treinar_contexto.py --source eolica --round V4 --task corte_positivo --slots 2 --chunk-days 7 --drop $DROP --run-id rapido-eol-v4-corte-003 > $L/rapido-eol-v4-corte-003.log 2>&1; echo "eol V4 003 exit $?"
uv run python scripts/rapido/resumir.py
echo FIM
