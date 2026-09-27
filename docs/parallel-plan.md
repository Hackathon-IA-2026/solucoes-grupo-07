# Plano de trabalho paralelo — 22 a 27/09/2026

## Por que dá para paralelizar agora

As etapas 3 a 6 não dependem de qual modelo a Etapa 2C vai escolher. Elas dependem só do
**formato da saída**, que está fixado em [`src/zelo/contracts.py`](../src/zelo/contracts.py):

- `FORECAST_SCHEMA`: uma linha por `fonte + id_ons + t0 + horizonte` (48 janelas de 30 min),
  com probabilidades, volume, causa, motivo de ausência e proveniência;
- `RECOMMENDATION_SCHEMA`: ação por usina e janela de risco, com energia, valor, CO2 e versão
  das premissas.

Enquanto a 2C não decide, o produto usa `SameSlotRecentBaseline`
([`src/zelo/forecasting.py`](../src/zelo/forecasting.py)): repete o mesmo horário do
dia disponível mais recente, até 28 dias. Ele usa dados reais e aparece marcado como
`baseline`. Quando o modelo escolhido existir, só o preditor muda; recomendação e interface
continuam iguais. Se a 2C concluir que o baseline é a melhor opção, nada muda.

## Divisão

| Pessoa | Ter–Qui (remoto) | Sex–Dom (presencial) |
|---|---|---|
| Responsável (Angelo) | Etapa 2 (2B → 2C) na branch `etapa-2-experimental`. Revisa e integra PRs. | Troca o preditor pelo escolhido. Validação final. |
| Dev 2 | Etapa 3 na branch `etapa-3-recomendacao` ([prompt](handoffs/stage3-prompt.md)). | Números e perguntas do pitch. |
| Dev 3 | Etapa 4 na branch `etapa-4-interface`; na quinta, preparação local da Etapa 5 ([prompt](handoffs/stage4-prompt.md)). | Deploy na AWS (acesso só de 25 a 27/09); contingência offline. |

A Etapa 6 (narrativa, slides e ensaio) começa na quinta com o material de `pitch-notes.md` e
fecha no presencial.

## Regras comuns

1. **Cada um trabalha na própria branch**, criada a partir do `origin/main` atualizado.
   Integração por Pull Request no GitHub, revisado pelo responsável.
2. **Contrato:** mudanças em `contracts.py` só por um PR pequeno e separado, combinado com o
   responsável antes. Adicionar coluna opcional é barato; renomear ou mudar tipo quebra os
   outros.
3. **Donos de arquivo:** `src/zelo/app.py` e a interface são do Dev 3.
   `recommendation`/impacto são do Dev 2. `contracts.py` e `forecasting.py`, do responsável.
4. **Teste reservado:** nenhum dado com `din_instante >= 2026-05-01` pode ser lido, exibido ou
   usado em demo, fixture ou número de impacto antes de a Etapa 2C liberar. O código já recusa
   esse período por padrão (`allow_reserved_test=False`). Não contorne.
5. **Dependências:** novas bibliotecas entram num extra próprio do `pyproject.toml`. Em conflito
   no `uv.lock`, rode `uv lock` de novo em vez de mesclar à mão.
6. **Diário:** cada tarefa material acrescenta uma entrada no fim de
   `docs/implementation-journal.md`. O `.gitattributes` une automaticamente as entradas de
   branches diferentes; confira a ordem no merge.

## Passo a passo de Git para a equipe

```bash
# Uma vez
git clone https://github.com/Hackathon-IA-2026/solucoes-grupo-07.git
cd solucoes-grupo-07
uv sync --extra data --dev
uv run python -m zelo.download_data     # baixa os Parquet para data/raw/

# Início do trabalho
git switch main && git pull
git switch -c etapa-3-recomendacao          # ou etapa-4-interface

# Durante o trabalho: commits pequenos, em português, Conventional Commits
uv run pytest && uv run ruff check . && uv run ruff format --check .
git add <arquivos> && git commit -m "feat: ..."
git push -u origin etapa-3-recomendacao

# Para trazer novidades do main para a sua branch
git fetch origin && git merge origin/main
```

Abra o Pull Request pelo GitHub quando houver uma fatia funcionando com testes. Prefira PRs
pequenos e frequentes a um único PR no sábado.

## Ordem de integração

1. Contrato + preditor provisório (já no `main`).
2. Dev 3: estrutura de páginas e tela operacional sobre o baseline.
3. Dev 2: recomendação e impacto; a interface passa a mostrar as ações reais.
4. Dev 3: Dockerfile e esqueleto CDK (sem conflito com o resto).
5. Etapa 2, depois da decisão da 2C; troca do preditor atrás do contrato.

## Limitações conhecidas do preditor provisório

- Disponibilidade simulada considera só fins de semana; feriados ainda não.
- Sem fallback regional: sem observação no horário, a previsão fica nula com motivo.
- Copia o último dia disponível. Se esse dia for domingo (carga baixa), a energia prevista
  tende a ficar alta. Em 14/10/2025 às 10h, a soma das 48 janelas foi ≈ 231 GWh, contra uma
  média diária de ≈ 102 GWh em 2025.
- Não há intervalo de volume nem probabilidade calibrada: probabilidades são 0 ou 1.
