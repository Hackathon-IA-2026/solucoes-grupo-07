# AGENTS.md

## Objetivo do projeto

Construir o Zelo, um protótipo para o desafio de curtailment do Hackathon IA COPPE 2026. O sistema deve antecipar cortes de geração eólica e solar, diagnosticar a causa provável e transformar o resultado em uma recomendação rastreável para o gerador.

Zelo é o nome de trabalho adotado em todo o repositório. O nome do produto ainda não é definitivo e poderá ser substituído globalmente no futuro.

## Fonte de verdade

- A proposta funcional vigente e o briefing do Zelo fornecido pela equipe, consolidado em `docs/architecture.md`.
- O Caderno de Desafios e Dados define o contexto e as restricoes oficiais.
- O pitch do Ideathon serve como compromisso de coerencia, nao como especificacao imutavel.
- Nao invente resultados, metricas, acesso a infraestrutura ou regras da organizacao. Marque hipoteses e dados simulados de forma visivel.

## Escopo do MVP

1. Prever, por usina e janela de 30 minutos, probabilidade e volume de curtailment para as proximas 24 horas.
2. Diagnosticar a causa provavel (`REL`, `CNF`, `ENE` ou `PAR`) e a origem (`LOC` ou `SIS`) quando houver cobertura suficiente.
3. Recomendar uma acao compatível com a causa e estimar MWh recuperaveis, valor financeiro e CO2 evitado como cenarios, nao como garantias.
4. Expor previsoes, incerteza, explicacoes e recomendacoes em um dashboard operacional.

O usuario principal e o gerador eolico/solar. Analises para investidores e cargas flexiveis sao extensoes.

## Principios tecnicos

- Python 3.12 e `uv` para ambiente, dependencias e comandos.
- Processamento colunar com Polars, DuckDB e Parquet; nunca carregue os 100+ milhoes de registros integralmente em pandas.
- Modelos tabulares explicáveis são o núcleo. Comece com baselines temporais e compare algoritmos candidatos antes de escolher o modelo final. LightGBM é um candidato, não uma decisão antecipada.
- Separe o problema em: classificacao de ocorrencia, regressao de volume condicional ao corte e classificacao de causa.
- Use divisao temporal e backtesting rolling/expanding. Nunca use split aleatorio em series temporais.
- Qualquer feature precisa estar disponivel no instante real da previsao. Vento ou irradiancia verificados sao aceitaveis para analise historica, mas nao devem ser apresentados como feature D+1 sem um substituto de previsao meteorologica.
- Compare sempre com pelo menos dois baselines: ultimo valor e mesmo horario do dia anterior.
- Reporte desbalanceamento e metricas adequadas: PR-AUC/recall para evento, MAE/WAPE para volume e macro-F1 para causa.
- SHAP explica associacoes do modelo, nao causalidade.
- A camada LLM e opcional e nunca decide numeros. Ela apenas verbaliza saidas estruturadas do pipeline, com fallback deterministico.
- Integracoes AWS e NVIDIA devem ficar atras de interfaces/configuracao; o produto precisa rodar localmente sem credenciais externas.

## Dados e rastreabilidade

- Nao versione Parquet, modelos treinados, credenciais ou dados derivados grandes.
- Preserve `fonte + id_ons` como chave na base integrada; `id_ons` isolado nao e global.
- Nao impute silenciosamente. Gere relatorio de nulos por campo e por periodo antes da modelagem.
- Defina e documente a formula de curtailment antes de treinar. Mantenha unidade, limites e tratamento de valores negativos testados.
- Registre dataset, periodo, features, seed, parametros e metricas de cada artefato de modelo.
- Toda estimativa financeira e de carbono deve exibir premissas e analise de sensibilidade.

## Estrutura esperada

- `src/zelo/`: código de produto e domínio.
- `tests/`: testes unitarios e de contratos de dados.
- `data/`: apenas documentacao e diretorios locais ignorados pelo Git.
- `models/`: artefatos locais ignorados pelo Git.
- `docs/`: decisoes de arquitetura e notas tecnicas.

## Comandos

```bash
uv sync --dev
# Quando uma integracao for realmente usada:
uv sync --extra data --extra llm --extra aws --dev
uv run streamlit run src/zelo/app.py
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Fluxo de desenvolvimento

- Siga TDD no ciclo Red-Green-Refactor: escreva primeiro um teste que expresse o comportamento, confirme a falha esperada, implemente o mínimo necessário e refatore mantendo a suíte verde.
- Toda transformação de dados deve ter testes de contrato, unidade, limites, nulos e casos anômalos. Não transforme uma hipótese sobre os dados em regra sem evidência mensurável.
- Mantenha uma narrativa cronológica em `docs/implementation-journal.md`. Antes de concluir qualquer tarefa material, acrescente uma entrada seguindo o fluxo definido abaixo.
- Registre decisões relevantes, evidências, limitações e resultados em `docs/`. Preserve especialmente o material que possa sustentar o storytelling de negócio e a apresentação final.
- Mantenha frontend, backend, modelagem e infraestrutura no mesmo repositório. Integrações devem respeitar essa estrutura de monorepo.

## Diário de implementação

O diário é uma fonte de estudo para o responsável pelo projeto e a memória factual da apresentação. Ele deve permitir reconstruir não apenas o que foi feito, mas por que foi feito e o que foi aprendido.

- Adicione uma entrada para toda tarefa que produza código relevante, análise de dados, resultado experimental, decisão de produto ou arquitetura, alteração metodológica ou descoberta sobre o problema.
- Não crie entrada para formatação ou manutenção trivial sem consequência técnica ou narrativa.
- Escreva em português do Brasil, de forma didática para uma pessoa que não acompanhou a execução detalhada.
- Mantenha as entradas em ordem cronológica e em formato append-only. Não reescreva silenciosamente uma conclusão antiga; registre uma correção ou evolução posterior.
- Diferencie explicitamente fatos observados, interpretações, hipóteses e decisões. Nunca apresente inferência como evidência confirmada.
- Inclua números, consultas, fontes e artefatos que sustentem conclusões. Resultados provisórios devem ser identificados como tal.
- Relacione a descoberta ao usuário final e indique se ela pode sustentar problema, “por que agora?”, solução, impacto, limitação ou demonstração no pitch.
- Registre alternativas consideradas e explique por que foram aceitas, adiadas ou descartadas.
- Termine com limitações e próximos passos, para que a sessão seguinte consiga continuar sem reconstruir o raciocínio.

Cada entrada deve usar, quando aplicável, esta estrutura:

1. contexto e pergunta;
2. fatos e evidências observados;
3. interpretação e decisão;
4. alternativas consideradas;
5. implementação e validação;
6. limitações e incertezas;
7. valor para o usuário e para a apresentação;
8. próximos passos.

## Git

- Use Conventional Commits.
- Escreva assunto e corpo dos commits em português do Brasil.
- Use uma frase curta, direta e no imperativo no assunto. Inclua corpo quando a motivação, as decisões ou as limitações não forem óbvias pelo diff.
- Produza commits atômicos: cada commit deve representar uma mudança coerente, reversível e verificável de forma independente.
- Não misture refatoração, funcionalidade e documentação sem necessidade. Preserve o histórico como documentação e facilite `revert`, `cherry-pick` e revisão.
- Antes de cada commit, execute os testes e verificações relevantes ao escopo alterado.

## Criterios de conclusao

- Mudancas pequenas, testadas e documentadas.
- Sem vazamento temporal ou dependencia obrigatoria de servico externo.
- Resultados reais claramente separados de mock, hipotese e cenario.
- Dashboard deve revelar fonte, janela temporal, ultima atualizacao, incerteza e limitacoes.
- Uma tarefa material só está concluída quando sua narrativa foi acrescentada ao diário de implementação.
- Antes de concluir uma tarefa, execute testes e lint relevantes e relate qualquer verificacao que nao foi possivel fazer.
