# Prompt autossuficiente para a Etapa 3 — recomendação e impacto

Você vai implementar a Etapa 3 do CurtaMap: transformar a previsão de curtailment em uma
recomendação rastreável para o gerador eólico/solar, com estimativa de energia recuperável,
valor financeiro e CO2 evitado **como cenários com premissas visíveis**, nunca como garantia.

## Antes de começar

Leia integralmente: `AGENTS.md`, `docs/parallel-plan.md`, `docs/architecture.md`,
`docs/roadmap.md` (seção 3), `docs/target-definition.md`, `docs/pitch-notes.md`,
`src/curtamap/contracts.py`, `src/curtamap/forecasting.py` e `src/curtamap/targets.py`.
Leia também as últimas entradas de `docs/implementation-journal.md`.

Trabalhe na branch `etapa-3-recomendacao`, criada a partir do `origin/main` atualizado.
Faça commits atômicos em português (Conventional Commits) e push da branch. Não faça merge no
`main`: a integração é por Pull Request revisado pelo responsável.

Para ter dados reais: `uv sync --extra data --dev` e `uv run python -m curtamap.download_data`.

## O que já existe e não deve ser alterado sem combinar

- `FORECAST_SCHEMA` e `validate_forecast`: a entrada da sua etapa. Uma linha por
  `fonte + id_ons + t0 + horizonte`, 48 janelas de 30 minutos, com `p_corte`, `alerta`,
  `energia_esperada_mwh`, `causa_prevista` (REL/CNF/ENE ou nula com `motivo_sem_causa`),
  `tipo_saida` e `modelo_id`.
- `RECOMMENDATION_SCHEMA` e `validate_recommendations`: a sua saída. Toda recomendação que
  você produzir deve passar por `validate_recommendations`.
- `SameSlotRecentBaseline`: o preditor provisório, com dados reais. O modelo definitivo da
  Etapa 2 vai substituí-lo depois, com o mesmo formato. Seu código não pode depender de qual
  preditor gerou a previsão, nem importar `curtamap.experimental`.

Se precisar de uma coluna nova no contrato, pare e proponha ao responsável um PR pequeno e
separado em `contracts.py`. Não altere `src/curtamap/app.py`: a interface é de outro
desenvolvedor, que vai consumir a sua saída pelo contrato.

## Entregas

1. **Regras causa → ação** (`docs/recommendation-rules.md` + `src/curtamap/recommendation.py`).
   Regras explícitas e determinísticas, não aprendidas. Para cada causa (`REL`, `CNF`, `ENE`,
   `PAR` e causa desconhecida/nula), diga que ações o gerador pode tomar, com que antecedência,
   e quais limites operacionais e regulatórios existem. Diferencie eólica e solar e, quando
   ajudar, origem `LOC`/`SIS`. Cada regra precisa de uma justificativa com fonte (documentos do
   ONS, ANEEL, CCEE, Caderno de Desafios) ou ser marcada como hipótese. Quando a causa for nula,
   a recomendação deve dizer isso, e não inventar uma causa.

2. **Janelas de risco.** Agrupe janelas consecutivas com `alerta = True` da mesma
   `fonte + id_ons` e emissão `t0` em episódios (`inicio`, `fim`), somando
   `energia_esperada_mwh` como `energia_em_risco_mwh`. Não some emissões sobrepostas: cada
   recomendação pertence a uma única emissão `t0`.

3. **Premissas versionadas** (por exemplo `configs/premissas/v1.json` + seção no documento).
   Preço de energia (por exemplo o PLD por submercado, da CCEE), fator de emissão do SIN
   (MCTI) e parâmetros das ações (por exemplo potência, capacidade e eficiência de
   armazenamento). Cada número precisa de fonte, URL, data de consulta e unidade. Defina
   cenários baixo/base/alto. **Não invente números.** Se não houver fonte, deixe o valor nulo e
   registre a lacuna. `premissas_versao` identifica o arquivo usado.

4. **Impacto.** Para cada recomendação: `energia_recuperavel_mwh` (nunca maior que a energia
   em risco), `valor_estimado_brl` e `co2_evitado_t`, calculados a partir das premissas. Inclua
   uma função de sensibilidade que devolva os três cenários. Explicite que a energia cortada
   não vira automaticamente energia recuperada nem receita: isso depende da ação, do contrato e
   da regulação. Propague `tipo_saida` e `modelo_id` da previsão.

5. **Resumo tático histórico.** Funções que agregam o histórico real (derivado por
   `derive_targets` sobre as bases principais) por usina, semana/mês, causa, UF e subsistema,
   para a aba "Visão tática". São dados observados, não previsão.

## Regras obrigatórias

- **TDD:** primeiro o teste que falha, depois a implementação mínima, depois a refatoração.
  Teste limites, nulos, causa ausente, episódio de uma única janela, episódios separados por
  uma janela sem alerta, fontes diferentes com o mesmo `id_ons` e premissas ausentes.
- **Teste reservado:** nunca leia, exiba ou use dados com `din_instante >= 2026-05-01`, nem
  para "dar uma olhada". Também não escolha exemplos, números de demonstração ou premissas a
  partir desse período. O código já recusa esse período por padrão; não passe
  `allow_reserved_test=True`.
- Use Polars/DuckDB; não carregue as bases inteiras em pandas.
- Não use LLM para calcular nada.
- Separe fatos observados, premissas, hipóteses e cenários em código, documentação e
  mensagens.
- Antes de cada commit: `uv run pytest`, `uv run ruff check .` e `uv run ruff format --check .`.
  No Windows, se `tests/test_feature_inventory.py` falhar por encoding, rode com
  `PYTHONUTF8=1`: é um problema conhecido e anterior a esta etapa.

## Validação com o usuário

Escreva, em `docs/recommendation-rules.md`, uma história realista de um gerador usando a
recomendação numa emissão real (antes de maio de 2026): o que ele vê, o que decide, o que
ganharia em cada cenário e o que a ferramenta **não** pode garantir. Isso vai para o pitch.

## Encerramento

Acrescente uma entrada no fim de `docs/implementation-journal.md`, seguindo a estrutura de
oito itens definida no `AGENTS.md`. Atualize `docs/pitch-notes.md` com os números de impacto
e o estado de cada um (fonte, premissa ou hipótese). Faça push da branch e informe ao
responsável o que ficou pronto, o que ficou pendente e quais premissas precisam de validação.
