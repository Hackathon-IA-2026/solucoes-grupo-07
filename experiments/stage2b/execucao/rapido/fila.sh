#!/usr/bin/env bash
# Executor sequencial das runs rápidas (25/09/2026). Uso: fila.sh <arquivo de jobs>.
# Cada linha do arquivo é um comando; o status vai para <arquivo>.status, uma linha por job.
cd "M:/Bibliotecas/Development/workspaces/hackathon-ia-coppe-2026"
export TMP="Y:/CurtaMap Etapa 2B/temporarios" TEMP="Y:/CurtaMap Etapa 2B/temporarios"
export POLARS_TEMP_DIR="Y:/CurtaMap Etapa 2B/temporarios/polars" PYTHONIOENCODING=utf-8 PYTHONUTF8=1
JOBS="$1"; STATUS="$JOBS.status"; : > "$STATUS"
n=0
while IFS= read -r job; do
  [ -z "$job" ] && continue
  n=$((n+1)); echo "INICIO $n $(date +%H:%M:%S) $job" >> "$STATUS"
  bash -c "$job" > "experiments/stage2b/execucao/rapido/job-$(basename "$JOBS" .txt)-$n.log" 2>&1
  echo "FIM $n exit=$? $(date +%H:%M:%S)" >> "$STATUS"
done < "$JOBS"
echo "FILA CONCLUIDA $(date +%H:%M:%S)" >> "$STATUS"
