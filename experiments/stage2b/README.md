# Etapa 2B — raiz operacional e artefatos

Este diretório espelha a raiz experimental da Etapa 2B, que antes ficava em
`Y:\CurtaMap Etapa 2B`. A estrutura de pastas foi mantida, para que continuem válidos os
caminhos relativos citados no relatório, no prompt da 2C e no `run-index`, como
`execucao/run-index.json` e `experimentos/<run>/metrics/…`.

## O que está no Git

- `execucao/`: scripts operacionais, `run-index.json`, checkpoints, logs de cada passo
  (`passos/`), verificações e medições. Os backups `.before-*` guardam versões de scripts
  nunca commitadas.
- `handoff/`: relatório factual, inventários e `SHA256SUMS-handoff.txt`.
- `experimentos/<run>/`: `manifest.json`, `checksums.json`, `reports/`, `metrics/` e
  `diagnostics/`.

O `.gitattributes` desativa a conversão de fim de linha aqui, para que os bytes (e os
`checksums.json`) sejam os mesmos em qualquer clone.

## O que fica fora do Git (disco externo, via junction)

| Caminho aqui | Conteúdo | Tamanho aproximado |
|---|---|---|
| `experimentos/<run>/predictions` | Previsões Parquet | 58,7 GB |
| `experimentos/<run>/models` | Modelos `.joblib` (≈ 11 h de treino) | 27 MB |
| `experimentos/stage2b-datasets` | Features e baselines | 8,2 GB |
| `cache`, `dados`, `sondas`, `temporarios` | Alvos, dados brutos, sondagens, spill | ≈ 0,9 GB |
| `env.ps1` | Caminhos desta máquina (modelo em `env.example.ps1`) | — |
| `**/*.progress.jsonl`, `**/*.sqlite` | Progresso intermediário de medições e verificações | 72 MB |

Nada disso deve ser recriado: os artefatos são caros. Em outra máquina, copie as pastas para os
mesmos caminhos relativos (como pastas reais ou symlinks) e confira com:

```bash
uv run python scripts/stage2b/conferir_migracao.py "<origem>" experiments/stage2b
```

No computador dedicado, as junctions são criadas por `scripts/stage2b/migrar-para-repo.ps1`.
O script só copia arquivos e cria junctions; nunca apaga nada.

## Atenção

- **Nunca rode `git clean -x` (nem `-X`) neste repositório.** O Git trata as junctions como
  diretórios comuns e apagaria os dados reais no disco externo.
- **Novas runs:** `execucao/run-step.ps1` grava os passos aqui, mas `CURTAMAP_EXPERIMENT_DIR`
  continua no disco externo, porque as previsões não cabem no disco do repositório. Depois de
  cada run, rode de novo `migrar-para-repo.ps1` e `conferir_migracao.py` para trazer as partes
  leves e criar as junctions.
- **Caminhos absolutos gravados:** os manifests e relatórios registram caminhos `Y:\…`. Isso
  é histórico e continua válido nesta máquina.
- **Fila da 2B:** `execucao/fila/fila-2b.ps1` e `status-fila.ps1` são registros da fila já
  concluída. Eles ainda apontam para o `Y:` e para o worktree removido; adapte-os antes de
  reutilizá-los.
