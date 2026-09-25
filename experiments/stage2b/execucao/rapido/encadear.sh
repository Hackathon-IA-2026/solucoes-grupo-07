#!/usr/bin/env bash
# Espera o fim de uma fila (arquivo .status) e dispara a seguinte. Uso: encadear.sh <status anterior> <jobs>
cd "M:/Bibliotecas/Development/workspaces/hackathon-ia-coppe-2026"
until grep -q "FILA CONCLUIDA" "$1" 2>/dev/null; do sleep 10; done
bash experiments/stage2b/execucao/rapido/fila.sh "$2"
