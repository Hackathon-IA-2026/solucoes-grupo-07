# Etapa 2B — raiz operacional e artefatos

Este diretório reúne a raiz experimental da Etapa 2B, que antes ficava inteira em
`Y:\CurtaMap Etapa 2B`. A estrutura de pastas foi mantida, para que continuem válidos os
caminhos relativos citados no relatório, no prompt da 2C e no `run-index`.

## Onde está cada coisa

| Caminho aqui | Onde fica fisicamente | No Git? |
|---|---|---|
| `execucao/` (scripts, `run-index.json`, logs de passos, verificações, checkpoints) | aqui | sim, exceto `*.progress.jsonl` e `*.sqlite` |
| `handoff/` (relatório, inventários, `SHA256SUMS-handoff.txt`) | aqui | sim |
| `cache/` (alvos), `dados/` (Parquet bruto), `sondas/` | aqui | não |
| `env.ps1` (caminhos desta máquina; modelo em `env.example.ps1`) | aqui | não |
| **`experimentos/`** | **junção** para `Y:\CurtaMap Etapa 2B\experimentos` (≈ 68 GB) | ver abaixo |
| `temporarios` (spill de runs pesadas) | só em `Y:\CurtaMap Etapa 2B\temporarios`, pelo `env.ps1` | não |

Dentro de `experimentos/<run>/`:

- `manifest.json`, `checksums.json`, `reports/`, `metrics/` e `diagnostics/` são versionados.
  O Git os lê através da junção.
- `predictions/` e `models/` ficam ignorados, assim como `experimentos/stage2b-datasets/`.

O `.gitattributes` desativa a conversão de fim de linha em `experiments/stage2b`, para que os
bytes (e os `checksums.json`) sejam os mesmos em qualquer clone.

## Em outra máquina (Mac)

Nada deve ser recriado: os artefatos levam horas para gerar.

1. Copie `Y:\CurtaMap Etapa 2B\experimentos` inteira para `experiments/stage2b/experimentos`,
   como pasta real ou symlink. Os arquivos leves já vêm do Git e são idênticos.
2. Copie também `cache/`, `dados/` e `sondas/` deste diretório, se forem necessários.
3. Confira:

```bash
uv run python scripts/stage2b/conferir_migracao.py
```

O script recalcula o SHA-256 de todas as entradas dos `checksums.json` (650 hoje).

## Atenção

- **Nunca rode `git clean -x` (nem `-X`) neste repositório.** O Git trata a junção como um
  diretório comum e apagaria os dados reais no disco externo.
- **Novas runs** gravam direto em `experimentos/` (portanto no `Y:`), e os passos do
  `run-step.ps1` vão para `execucao/passos/`.
- **Caminhos absolutos gravados:** manifests e relatórios registram caminhos `Y:\…`. Os de
  `experimentos` continuam válidos nesta máquina; os de `cache` e `dados` agora ficam aqui.
- **Fila da 2B:** `execucao/fila/fila-2b.ps1` e `status-fila.ps1` são registros da fila já
  concluída e ainda apontam para caminhos antigos; adapte-os antes de reutilizá-los.
