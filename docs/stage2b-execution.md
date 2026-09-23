# Execução da Etapa 2B no computador dedicado

Estado deste documento: código preparado no Mac; piloto real e campanha pesada pendentes.
O teste reservado de maio–agosto de 2026 continua bloqueado.

## 1. Transferência sem push

No Mac, na branch `etapa-2-experimental`, confirme e gere um bundle:

```bash
git branch --show-current
git status --short
git bundle create curtamap-etapa-2b.bundle etapa-2-experimental
git bundle verify curtamap-etapa-2b.bundle
```

Copie o bundle para o computador dedicado. Não dependa de clone remoto atualizado. No destino:

```bash
git clone curtamap-etapa-2b.bundle curtamap-etapa-2b
cd curtamap-etapa-2b
git switch etapa-2-experimental
git rev-parse HEAD
```

Copie separadamente somente os dois Parquet principais originais para a raiz de dados escolhida.
Não copie a integrada nem os arquivos detail para o experimento. Confira os SHA-256 contra
`docs/reports/stage1/audit.json`. O computador dedicado não altera código e não cria commits.

## 2. Ambiente e caminhos

Instale Python 3.12 e `uv`. No macOS, LightGBM também requer o runtime OpenMP (`brew install
libomp`). No computador dedicado, instale a dependência equivalente do sistema operacional
caso a importação do LightGBM indique biblioteca OpenMP ausente.

Exemplo Bash, com espaços intencionais nos caminhos:

```bash
export CURTAMAP_DATA_DIR="/volume externo/CurtaMap/dados"
export CURTAMAP_MODEL_DIR="/volume externo/CurtaMap/modelos"
export CURTAMAP_EXPERIMENT_DIR="/volume externo/CurtaMap/experimentos"
export CURTAMAP_CACHE_DIR="/volume externo/CurtaMap/cache"
export CURTAMAP_TEMP_DIR="/volume externo/CurtaMap/temporarios"
uv sync --dev
uv run curtamap-experiment --config configs/experimental/stage2b.example.json preflight
```

Exemplo PowerShell:

```powershell
$env:CURTAMAP_DATA_DIR = "D:\CurtaMap externo\dados"
$env:CURTAMAP_MODEL_DIR = "D:\CurtaMap externo\modelos"
$env:CURTAMAP_EXPERIMENT_DIR = "D:\CurtaMap externo\experimentos"
$env:CURTAMAP_CACHE_DIR = "D:\CurtaMap externo\cache"
$env:CURTAMAP_TEMP_DIR = "D:\CurtaMap externo\temporarios"
uv sync --dev
uv run curtamap-experiment --config configs/experimental/stage2b.example.json preflight
```

O `preflight` deve mostrar a branch correta, o commit, os dois arquivos existentes e espaço
livre. Os caminhos resolvidos ficam apenas no manifesto externo; não entram no Git.

## 3. Alvos e datasets experimentais

Prepare separadamente os dois cenários. A transformação é mensal, colunar e gera derivados no
cache; os originais não são alterados.

```bash
uv run curtamap-experiment --config configs/experimental/stage2b.example.json prepare-targets --scenario noturno_dia_util
uv run curtamap-experiment --config configs/experimental/stage2b.example.json prepare-targets --scenario noturno_mais_24h
```

Gere as features até o fim do desenvolvimento, sem abrir o teste reservado. Use uma partição
`development` por fonte/cenário; a campanha seleciona V1–V4 por `t0`.

```bash
uv run curtamap-experiment --config configs/experimental/stage2b.example.json build-features --scenario noturno_dia_util --source eolica --round development --start 2023-10-01T00:00:00 --end 2026-05-01T00:00:00
uv run curtamap-experiment --config configs/experimental/stage2b.example.json build-features --scenario noturno_dia_util --source fotovoltaica --round development --start 2024-04-01T00:00:00 --end 2026-05-01T00:00:00
uv run curtamap-experiment --config configs/experimental/stage2b.example.json build-features --scenario noturno_mais_24h --source eolica --round development --start 2023-10-01T00:00:00 --end 2026-05-01T00:00:00
uv run curtamap-experiment --config configs/experimental/stage2b.example.json build-features --scenario noturno_mais_24h --source fotovoltaica --round development --start 2024-04-01T00:00:00 --end 2026-05-01T00:00:00
```

Cada dia produz `features.parquet` e `baselines.parquet`. O gerador lê uma janela por vez,
mantém verdade futura fora das features e registra disponibilidade, fallback e idade.

## 4. Piloto técnico obrigatório

Antes do piloto, verifique cada dataset com o módulo versionado
`python -m curtamap.experimental.dataset_verification`. Argumentos posicionais:
diretório `round=development`, início ISO inclusivo, fim ISO exclusivo e JSON novo.
Argumentos obrigatórios: `--targets` com o glob do cache de alvos da fonte/cenário,
`--calendar` com o manifesto congelado, `--source`, `--scenario` e `--dataset-commit`
com o commit que efetivamente gerou o dataset. No computador dedicado, execute pelo
executor durável, com um StepId novo e sem concorrência pesada.

O verificador lê uma partição diária por vez. Não altera os Parquet. O primeiro
registro do cache e sua liberação são conferidos contra o calendário; somente dias
inteiros anteriores ao primeiro conhecimento podem estar sem partição. Dias ausentes
depois disso continuam sendo falha. Cada partição concluída é persistida em
`<nome>.progress.jsonl`; alvos indeterminados são deduplicados em
`<nome>.targets.sqlite`, evitando um conjunto global em RAM. Esses arquivos e o JSON
não podem ser sobrescritos. Uma interrupção nativa pode impedir o JSON final, mas o
progresso já sincronizado permanece disponível. Uma nova tentativa usa novos nomes.

O relatório conserva as checagens originais e acrescenta chaves/nulos, posição diária,
fonte, liberação inicial e exclusão do reservado pelos filtros reais de validação.
Listas de causas e baselines são completas, e os quatro baselines são conferidos por
requisição, além do total de linhas. `tau` pode cruzar o limite do desenvolvimento nas
últimas emissões; sua contagem é reportada sem pontuar esses horizontes. Exit 0 exige
todas as checagens aprovadas; falha de contrato ou erro de leitura retorna exit 1.
Não retome o piloto com resultado parcial ou reprovado.

Execute um piloto por fonte usando no máximo 500 mil exemplos elegíveis por tarefa. Ele ajusta
as duas famílias apenas para validar contratos, serialização e recursos. Não emite métrica de
seleção e não elimina candidato.

```bash
uv run curtamap-experiment --config configs/experimental/stage2b.example.json pilot --run-id pilot-eolica-001 --features "$CURTAMAP_EXPERIMENT_DIR/stage2b-datasets/scenario=noturno_dia_util/source=eolica/round=development/date=*/features.parquet"
uv run curtamap-experiment --config configs/experimental/stage2b.example.json pilot --run-id pilot-fotovoltaica-001 --features "$CURTAMAP_EXPERIMENT_DIR/stage2b-datasets/scenario=noturno_dia_util/source=fotovoltaica/round=development/date=*/features.parquet"
```

Antes da campanha, examine `reports/technical-pilot.json`, `failures/`, duração, pico de memória,
tamanho do run e espaço livre. Se o ajuste completo for inviável, pare e devolva essa evidência
ao Mac. Não introduza amostragem nem altere código na máquina dedicada.

## 5. Campanha V1–V4

Para cada fonte e rodada, crie um `run_id` novo. Exemplo eólico V1:

```bash
uv run curtamap-experiment --config configs/experimental/stage2b.example.json campaign-round --run-id main-eolica-v1-001 --source eolica --round V1 --features "$CURTAMAP_EXPERIMENT_DIR/stage2b-datasets/scenario=noturno_dia_util/source=eolica/round=development/date=*/features.parquet" --baselines "$CURTAMAP_EXPERIMENT_DIR/stage2b-datasets/scenario=noturno_dia_util/source=eolica/round=development/date=*/baselines.parquet"
```

Repita com `V2`, `V3`, `V4` e com `fotovoltaica`. Não execute rodadas em paralelo: o orçamento
de memória pressupõe um ajuste pesado por vez. Cada run persiste configurações internas,
modelos, previsões, métricas, diagnósticos, falhas, comando de retomada e checksums.

Depois de cada run principal, aplique a sensibilidade +24h sem reajustar nada. Exemplo V1:

```bash
uv run curtamap-experiment --config configs/experimental/stage2b.example.json sensitivity-round --run-id delay-eolica-v1-001 --source eolica --round V1 --frozen-run "$CURTAMAP_EXPERIMENT_DIR/main-eolica-v1-001" --features "$CURTAMAP_EXPERIMENT_DIR/stage2b-datasets/scenario=noturno_mais_24h/source=eolica/round=development/date=*/features.parquet" --baselines "$CURTAMAP_EXPERIMENT_DIR/stage2b-datasets/scenario=noturno_mais_24h/source=eolica/round=development/date=*/baselines.parquet"
```

## 6. Teste reservado

O comando padrão não aceita `TESTE_RESERVADO`. A porta separada exige simultaneamente uma flag
e uma referência não vazia à decisão congelada da Etapa 2C:

```bash
uv run curtamap-experiment --config configs/experimental/stage2b.example.json reserved-test --allow-reserved-test --decision-ref DECISAO_2C_CONGELADA
```

Na Etapa 2B esse comando deve permanecer bloqueado ou informar que a receita congelada ainda
não foi fornecida. Não gere features de maio–agosto de 2026 nem pontue esse período agora.

## 7. Retorno ao Mac

Traga somente os diretórios de run concluídos ou incompletos: `manifest.json`, `checksums.json`,
`metrics/`, `predictions/`, `models/`, `reports/`, `diagnostics/`, `logs/` e `failures/`.
Não traga cache, temporários, datasets derivados nem alterações de código. Verifique todos os
SHA-256 de `checksums.json` no Mac antes da análise. Correções, commits e interpretação dos
resultados acontecem exclusivamente no Mac e na branch `etapa-2-experimental`.

