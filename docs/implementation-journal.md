# Diário de implementação do CurtaMap

Registro cronológico das evidências, decisões, aprendizados e limitações produzidos durante o projeto. Este documento complementa o histórico do Git: os commits mostram a mudança; o diário explica o raciocínio e seu significado para o usuário e para a apresentação.

As entradas são append-only. Quando uma conclusão mudar, uma nova entrada deve explicar a evolução em vez de apagar o entendimento anterior.

## 2026-09-19 - Fundação técnica e aquisição das bases

### Contexto e pergunta

Era necessário preparar um repositório reproduzível e obter as bases oficiais sem versionar arquivos grandes ou depender de procedimentos manuais diferentes em cada máquina.

### Fatos e evidências observados

- O Caderno do Hackathon aponta uma pasta pública com cinco Parquet tratados do ONS e dois materiais de apoio do ERA5.
- As bases somam mais de 100 milhões de registros; portanto, não devem ser carregadas integralmente em pandas nem enviadas ao Git.
- O projeto precisa permanecer open source sob licença MIT e ser executável localmente antes de depender da AWS.

### Interpretação e decisão

- Adotar Python 3.12 e `uv` para um ambiente reproduzível.
- Manter os dados em `data/raw/`, ignorados pelo Git.
- Automatizar descoberta e download com um módulo do próprio pacote CurtaMap.
- Preservar arquivos existentes por padrão e exigir `--force` para substituição intencional.

### Alternativas consideradas

- Download manual: descartado como fluxo principal por ser pouco reproduzível.
- Versionar os Parquet: descartado por tamanho, custo e risco de duplicação.
- Baixar automaticamente durante `uv sync`: descartado para não gerar uma transferência grande e inesperada.

### Implementação e validação

- Criado `curtamap.download_data` com modos de listagem, download e inclusão opcional dos tutoriais.
- O desenvolvimento seguiu Red-Green-Refactor; os testes revelaram e corrigiram inicialmente um problema de empacotamento do módulo.
- A listagem remota confirmou os cinco Parquet esperados.

### Limitações e incertezas

- O script não registra checksums dos arquivos baixados ainda.
- O tamanho dos arquivos precisa ser considerado antes de cópias adicionais ou envio ao S3.

### Valor para o usuário e para a apresentação

A aquisição reproduzível demonstra que o CurtaMap pode ser reconstruído a partir de dados públicos e rastreáveis, fortalecendo a credibilidade técnica e a possibilidade de evolução além do protótipo.

### Próximos passos

Auditar schemas, cobertura, duplicidades e domínios; depois formalizar e testar a definição do alvo de curtailment.

## 2026-09-19 - Arquitetura inicial e ambiente AWS

### Contexto e pergunta

Era necessário decidir uma direção técnica sem antecipar algoritmos ou acoplar o produto a serviços que poderiam não estar disponíveis no ambiente do Hackathon.

### Fatos e evidências observados

- O ambiente permite ECS, ECR, CodeBuild, S3, DynamoDB, SageMaker, Bedrock, Cognito e observabilidade.
- O provisionamento deve ocorrer por CloudFormation ou CDK, nas regiões `us-east-1` ou `us-west-2`.
- Toda a solução deve permanecer em um único repositório.
- O problema central é tabular e temporal; modelos generativos não calculam a previsão de curtailment.

### Interpretação e decisão

- Manter frontend, backend, modelagem e infraestrutura em monorepo.
- Tratar React/Vite + FastAPI como candidato para a interface final e Streamlit como protótipo e contingência, aguardando um spike comparativo.
- Definir os três problemas de modelagem - ocorrência, volume e causa - sem escolher antecipadamente os algoritmos.
- Tratar Bedrock e NVIDIA NIM como provedores opcionais e substituíveis para explicação em linguagem natural.

### Alternativas consideradas

- Fixar Streamlit imediatamente: adiado por possível limitação de customização visual.
- Fixar React imediatamente: adiado pelo custo adicional de implementação e testes.
- Usar um LLM como núcleo: descartado porque o valor quantitativo precisa ser calculado por modelos e regras rastreáveis.

### Implementação e validação

- A arquitetura, as restrições AWS e o roadmap foram documentados.
- LightGBM e SHAP foram removidos das dependências para não converter candidatos em decisões prematuras.
- O esqueleto Streamlit permaneceu executável e retornou health check válido.

### Limitações e incertezas

- Permissões e custos efetivos dos serviços AWS ainda precisam de um spike.
- A tecnologia final da interface e os algoritmos serão escolhidos após evidências de esforço e desempenho.

### Valor para o usuário e para a apresentação

O desenho evita tecnologia pela tecnologia: cada componente deverá demonstrar utilidade para antecipação, explicação ou decisão do gerador. Isso sustenta uma defesa clara do papel central da IA e das limitações assumidas.

### Próximos passos

Executar a etapa de fundamentos e dados antes de iniciar spikes de interface, modelos candidatos ou implantação AWS.

## 2026-09-19 - Criação do fluxo contínuo de narrativa

### Contexto e pergunta

Como garantir que decisões tomadas por agentes de IA permaneçam compreensíveis e estudáveis pelo responsável humano, além de úteis para o storytelling final?

### Fatos e evidências observados

- O histórico do Git registra alterações, mas não captura sozinho todas as evidências, interpretações, alternativas e implicações de negócio.
- A EDA e os experimentos futuros produzirão descobertas que podem mudar tratamento, modelagem, produto e narrativa do pitch.

### Interpretação e decisão

Tornar este diário uma etapa obrigatória da conclusão de toda tarefa material. Cada entrada deve separar fatos, interpretações, decisões e hipóteses, conectando o trabalho ao usuário final e à apresentação.

### Alternativas consideradas

- Depender apenas das mensagens das sessões: descartado porque são dispersas e difíceis de consultar depois.
- Depender apenas dos commits: insuficiente para explicar resultados analíticos e raciocínio de negócio.
- Registrar somente ao final: descartado pelo risco de perda de contexto e reconstrução retrospectiva imprecisa.

### Implementação e validação

- O fluxo foi formalizado no `AGENTS.md`.
- Este arquivo foi criado como registro cronológico append-only.
- As principais decisões anteriores foram recuperadas para iniciar a narrativa com contexto.

### Limitações e incertezas

O diário exige disciplina contínua e deve evitar tanto omissões quanto excesso de detalhes sem valor decisório.

### Valor para o usuário e para a apresentação

O responsável passa a ter uma fonte única para estudar o problema, auditar o trabalho delegado e recuperar fatos, decisões e histórias que sustentem uma apresentação de negócio convincente.

### Próximos passos

Na Etapa 1, registrar separadamente a auditoria, a definição do alvo, cada descoberta relevante da EDA e qualquer mudança metodológica decorrente dos dados.

## 2026-09-19 - Etapa 1.1: contrato, auditoria e escolha da base analítica

### Contexto e pergunta

Precisávamos saber se os cinco arquivos representavam a mesma população e se poderiam
ser usados sem multiplicar energia. Antes de implementar, foram lidos AGENTS, roadmap,
arquitetura, diário, notas do pitch e documentação de dados; Git estava limpo.

### Fatos e evidências observados

A auditoria colunar encontrou 102.739.069 linhas físicas. As principais somam
10.806.720 observações sem chaves nulas, duplicatas ou lacunas internas. A integrada
exclui exatamente 1.365.552 linhas eólicas de out/2023–mar/2024; não altera valores.
O detail contém 385/56 duplicatas excedentes eólicas/solares e 358.844/2.064 janelas
internas ausentes. Há 267 entidades principais, majoritariamente conjuntos; não são
267 usinas individuais. A geração das 15 usinas individuais diretamente comparáveis
coincide em 732.384 intervalos. Fontes, consultas, checksums, schemas, nulos gerais e
condicionais mensais, domínios e extremos estão em `docs/reports/stage1/audit.json`.

### Interpretação e decisão

Usar a união das duas principais na EDA, sem concatenar integrada ou detail. Manter
`fonte + id_ons` mesmo sem colisão atual entre fontes. Reter anomalias como achados:
29 gerações negativas, um limite negativo e extremos meteorológicos/disponibilidade
exigem tratamento explícito; nenhum percentil vira regra física automaticamente.

### Alternativas consideradas

Usar somente a integrada perderia seis meses eólicos. Somar detail às principais
contaria usinas dentro de conjuntos novamente. Deduplicar sem inspecionar seria uma
regra sem evidência. Comparar todos os meses de uma só vez gerou spill excessivo;
a comparação exata por mês preservou a semântica e reduziu o custo operacional.

### Implementação e validação

Criados `data_contract.py` e `audit.py`, JSON e Markdown reproduzíveis. TDD começou
com falha de importação do módulo ausente; fixtures cobriram schema, fonte composta,
chaves nulas, duplicatas, lacunas, off-grid, infinitos, negativos, flags, identidade,
nulos condicionais, arquivos vazios/ausentes e diferenças de multiconjunto.
As sete verificações de auditoria passaram antes da execução completa do snapshot.
O Opus 5 (`claude-opus-5`, effort high) fez revisão metodológica somente leitura;
aceitamos investigar identidade, rótulo sem limite e distinguir comando de corte positivo.

### Limitações e incertezas

Fuso e convenção início/fim da janela não foram confirmados. O detail não tem chave
formal de conjunto neste snapshot; o join individual é apenas uma validação parcial.
Achados reais fazem `--strict` falhar deliberadamente, embora os testes passem.

### Valor para o usuário e para a apresentação

A unidade operacional é usina **ou conjunto**. A distinção evita apresentar uma
promessa de precisão por usina física que a base principal não sustenta. A auditoria
fornece evidência de credibilidade e limites, não melhoria de previsão.

### Próximos passos

Formalizar o alvo, medir o impacto das anomalias e confrontar a fórmula com a GNR
publicada diretamente pelo ONS, antes de interpretar tendências no notebook.

## 2026-09-19 - Etapa 1.2: alvo e confronto com GNRa publicada

### Contexto e pergunta

A fórmula proposta mede geração não realizada e corresponde aos campos oficiais?

### Fatos e evidências observados

Os dicionários ONS atuais incluem GNRa com a diferença referência menos geração,
clipping zero e condicionamento à limitação. Foram baixados 64 arquivos oficiais dos
mesmos períodos, separados em `data/interim/official`. A fórmula reproduziu os
3.127.621 valores publicados não nulos, sem divergência acima de 0,001 MW. Há 129.615
GNRa nulas em intervalos solares limitados de 2024: soma parcial não é total comparável.
O snapshot local de 2025 soma 37,21075 TWh; publicação atual difere −0,0160% na eólica
e −0,0212% na solar. Fontes/checksums/comparações estão nos relatórios `official-*`.

### Interpretação, decisão e alternativas

Separar comando de limitação e volume positivo. Usar referência comum, não referência
final REL para todas as causas. Preservar negativos e sinalizar 21 volumes eólicos
indeterminados; manter variante bruta de sensibilidade, 3.732,3295 MWh nesses casos.
Descartamos imputaçao silenciosa e substituição dos originais por dados revisados.
A revisão do Opus foi avaliada criticamente e preservada em `docs/reviews/`.

### Implementação e validação

Função pura Polars e projeção DuckDB têm testes de paridade, nulos, zero, clipping,
negativos, NaN/infinito, causas/origens, fonte e conversão de unidade. O comparador
público tem testes de cobertura, diferenças e integração das cinco dimensões.
TDD confirmou módulo ausente e depois rejeitou comparação de totais incompletos;
a implementação mantém esses deltas nulos. Consulte `docs/target-definition.md`.

### Limitações e incertezas

Comparar totais não reconcilia revisões linha a linha. O JSON detail eólico contém
campos do principal; preservamos a resposta e conferimos o PDF. Fuso/início/fim de
janela e latência de publicação seguem pendentes. Totais são estimativas provisórias.

### Valor para o usuário e apresentação

Podemos explicar de onde vem cada MWh analítico, sem prometer compensação, recuperação
ou equivalência com estatísticas comerciais. Nenhum LLM produziu as métricas.

### Próximos passos

Concluir a interpretação da EDA no notebook, inventário contra vazamento, notas do
pitch, revisão de código pelo Opus e fechamento documental da Etapa 1.

## 2026-09-19 - Etapa 1.3: revisão independente do trabalho anterior e revisões do ONS

### Contexto e pergunta

Um segundo agente recebeu a tarefa de revisar criticamente tudo o que a Etapa 1 já havia
produzido (auditoria, alvo, validação pública) antes de concluí-la. A pergunta era: as
conclusões registradas nas entradas 1.1 e 1.2 resistem a uma leitura adversarial?

### Fatos e evidências observados

- **Correção da entrada 1.2.** A entrada anterior citava só os deltas de 2025 (−0,0160% e
  −0,0212%). Os outros anos têm deltas maiores: eólica −0,238% (2023), **−0,850%
  (2024)**; solar −0,482% (2026). Além disso, `formula_validation` compara a GNRa publicada
  com a fórmula aplicada **ao próprio arquivo oficial**. Ela valida a definição, mas não
  diz se o snapshot é igual à publicação.
- Foi criada uma junção linha a linha snapshot × publicação atual (`revision_check`), pela chave
  `fonte + id_ons + din_instante`. Resultados: 10.806.096 linhas casam; 132.290 têm geração,
  limite ou referência diferentes; 173 têm rótulo diferente; 52.310 intervalos mudam de
  energia (soma −298.040 MWh); **47 de 64 meses** diferem. Os arquivos oficiais foram
  modificados entre 13/02/2025 e 19/09/2026; meses de 2023 foram regravados em 14/09/2026.
- A primeira versão da junção indicava cerca de 584 mil “revisões” solares em 2024. A
  investigação mostrou que eram só representação: `NULL` no snapshot e `''` na publicação atual.
  Com a normalização, sobram 173 diferenças reais de rótulo.
- 624 linhas de nov/2024 trocaram de código: `BA4ECLA` virou `CJU_BA4ECLA`.
- Bug de SQL: o alias `matched` sem `AS` é palavra reservada no DuckDB e quebrou a consulta
  nova. Todos os aliases da função passaram a usar `AS`. Também foi corrigida a precedência
  de `AND`/`OR` no contador `changed_energy`.
- Auditoria: `identity_drift` ignorava trocas entre `NULL` e valor, e o join detail × principal
  não media multiplicação por duplicatas. Após a correção e a reexecução (48 s): nenhuma
  mudança de UF, subsistema ou CEG, e `duplicated_join_rows = 0`. As conclusões de 1.1 se
  mantêm.
- O detail eólico começa em 01/01/2023, nove meses antes da principal. Isso não estava
  documentado.

### Interpretação e decisão

- As diferenças entre o snapshot e a publicação vêm de **revisões pós-operação do ONS**, não da
  fórmula. Todos os totais passam a ser tratados como provisórios. O JSON agora carrega
  `status: provisional` e o escopo explícito (não é reconciliação financeira, comercial nem CCEE).
- O snapshot continua sendo a fonte do alvo, porque é a base oficial do desafio. A publicação
  atual serve só como validação. Não substituímos os dados.
- Revisões são um risco de vazamento temporal: um backtest com dados revisados usa
  informação inexistente em `t0`. Isso foi registrado no inventário.
- `rotulo_sem_limite` passou a ignorar texto vazio, e foi criada a flag `origem_desconhecida`,
  simétrica a `razao_desconhecida`.

### Alternativas consideradas

- Comparar só totais: rejeitado, porque não separa revisão de erro de fórmula.
- Tratar `''` como rótulo: rejeitado, porque inflaria contradições artificiais em dados futuros.
- Reconciliar entidades renomeadas por nome: adiado, pois nome não é chave validada.

### Implementação e validação

Ciclo TDD: testes novos falharam primeiro (`ImportError` de `revision_check`, `KeyError` de
`origem_desconhecida`, contagem de `cegs` com `NULL`, ausência de `join_rows`) e depois
passaram. Os casos cobertos são: linha só em um lado, valor revisado, `''` × `NULL`,
referência igual à geração, conversão 100 MWmed → 50 MWh, grade incompleta preservada e
paridade Polars × DuckDB. Os relatórios `audit.json` e `official-comparison.json` foram
regenerados.

### Revisão metodológica externa

A revisão da entrada 1.1 foi feita com o modelo `claude-opus-5`, esforço `high`, somente
leitura, sem edição automática. O metadado local confirma o modelo. Cada uma das 15 sugestões
foi triada em `docs/reviews/opus-stage1-methodology.md`:

- **Aceitas:** 2, 5, 6, 8, 9, 10, 11, 12, 13 e 15.
- **Aceita como limitação:** 4, sobre fuso e convenção de início/fim.
- **Adaptadas:** 1 (dois alvos, sem forçar a troca) e 7 (igualdade exata em vez de tolerância).
- **Parcialmente aceita:** 14 (temp_directory no padrão).
- **Parcialmente rejeitada:** 3. A fórmula não é “só hipótese”, pois reproduz 3.127.621 valores
  publicados; os totais continuam provisórios.

### Limitações e incertezas

Não temos o histórico de versões (vintages) do ONS: não dá para reconstruir o que era
conhecido em cada data. A latência de publicação continua desconhecida.

### Valor para o usuário e para a apresentação

Mostra rigor: sabemos exatamente o que foi validado (a fórmula) e o que não foi (a igualdade com
a publicação atual). Também mostra uma característica real dos dados que o gerador precisa
conhecer: o ONS revisa o passado.

### Próximos passos

Refazer a EDA em notebook e concluir o inventário de vazamento (entrada 1.4).

## 2026-09-19 - Etapa 1.4: EDA em notebook, inventário contra vazamento e fechamento da Etapa 1

### Contexto e pergunta

O usuário pediu a EDA contida em um único notebook executável, com narrativa, consultas,
tabelas e gráficos. A EDA existia só como agregações em `eda.py` e um JSON temporário não
versionado. Pergunta: o problema é grande, crescente, concentrado e recorrente o suficiente para
justificar antecipação por entidade?

### Fatos e evidências observados

Todos os fatos abaixo vêm de `notebooks/01_eda_fundamentos_dados.ipynb` e são conferidos por
`assert` na seção 13.

- **Crescimento.** Na mesma janela abr–ago, a eólica foi de 4,40 para 9,54 e 12,24 TWh
  (2024–2026), e a solar de 1,38 para 4,72 e 6,03 TWh.
- **Painel fixo.** Na eólica, 135 entidades vão de 3,18 para 7,61 e 10,27 TWh. Na solar,
  50 entidades vão de 1,20 para 3,39 e **3,36** TWh. O crescimento solar recente vem de
  entidades novas.
- **Causa.** CNF dominava a eólica em 2024 (61%). ENE domina em 2025 (51% eólica, 61% solar)
  e em 2026 (61% e 84%). ENE eólico, em abr–ago, foi de 0,75 para 7,96 TWh; CNF ficou em cerca
  de 3 TWh. Em fev/2025 houve um pico isolado de REL eólico, com 2,01 TWh.
- **Geografia (2025).** Total de 37,21 TWh, 70% eólico. RN 32%, BA 29%, MG 13%; NE 84%.
- **Concentração.** 36, 85 e 112 de 180 entidades eólicas e 13, 34 e 49 de 87 solares concentram
  50, 80 e 90% da energia.
- **Tempo.** O pico de incidência é às 10 h, como publicado. A eólica tem incidência noturna de
  9–14%.
- **Episódios.** Mediana de 9 e 10 intervalos, ou seja, 4,5–5 h. Só 15–16% duram 30 min, e
  87–89% dos intervalos com corte estão em episódios de 4 h ou mais.
- **Persistência.** P(corte | corte 24 h antes) = 0,70 e 0,71, contra bases de 0,26 e 0,19.
  P(corte | corte 30 min antes) = 0,92 e 0,90.
- **Comando × corte.** 18% das limitações eólicas e 22% das solares têm volume zero.
- **Rótulos.** 0 limitações eólicas e 42 solares sem causa ou origem válida. PAR está ausente.
  A origem é SIS em 75% dos intervalos limitados eólicos e em 90% dos solares.

### Interpretação e decisão

- A narrativa do “por que agora” se sustenta com dados próprios: crescimento em painel fixo
  (eólica) e mudança de regime de CNF/local para ENE/sistêmico. Para o gerador, isso significa
  perdas mais longas e simultâneas em muitas usinas.
- A persistência alta indica que os baselines serão fortes. O valor do modelo precisa ser medido
  contra “mesmo horário do dia anterior”, com latência declarada.
- O critério descritivo de persistência (≥ 500 cortes e P(t+30 min) ≥ 0,8), fixado antes da
  contagem, aprovou 175 de 180 e 80 de 87 entidades. Ele **não discrimina**. A conclusão
  registrada é que a persistência é disseminada, não que exista um subconjunto especial.
- Decisão para a Etapa 2: dois alvos de ocorrência, volume condicionado ao corte positivo e
  avaliação por fonte, causa e painel.

### Alternativas consideradas

- Ler o `tmp/eda-tables.json` antigo: rejeitado, porque não é versionado nem reproduzível. O
  notebook recalcula a partir de `data/raw/` em cerca de 8 s, após conferir o SHA-256.
- Plotly: rejeitado para as saídas versionadas, porque embutir o plotly.js incharia o `.ipynb`.
  Usamos matplotlib com paleta categórica validada para daltonismo.
- Comparar totais anuais brutos: rejeitado, porque os anos das bordas são incompletos. Usamos a
  janela abr–ago e 2025 como ano completo.
- Texto com números digitados à mão sem verificação: rejeitado. A seção 13 falha se algum número
  mudar.

### Implementação e validação

- `eda.py` ganhou `episode_durations` e `daily_persistence`, com testes escritos antes. Os
  testes cobrem quebras por lacuna e por valor desconhecido e a exigência de par observado em
  t−24 h.
- O notebook foi gerado, formatado pelo Ruff e executado com `nbclient`. `tests/test_notebook.py`
  verifica as saídas versionadas e reexecuta o notebook quando os Parquet existem (cerca de 10 s).
- `docs/feature-inventory.md` classifica todos os campos do snapshot, os extras da publicação
  atual e as colunas do alvo. `tests/test_feature_inventory.py` falha se algum campo ficar sem
  classe. O documento registra: horizonte de 48 janelas; valores verificados futuros são
  pós-evento; vento e irradiância do detail são verificados, não previsão; meteorologia futura só
  com timestamp as-of; histórico próprio só como defasagem; latência ONS e revisões como
  incerteza.
- `pitch-notes.md` foi reescrito separando o que foi reproduzido, o que foi validado contra a
  publicação atual, as referências externas e as hipóteses.
- Os 20%, os 4.021 MWmed e os R$ 6,5 bi continuam **externos** e não reproduzidos.

### Limitações e incertezas

- Sem fuso e sem convenção de início/fim.
- Anos incompletos.
- Totais provisórios por causa das revisões.
- 21 volumes eólicos indeterminados.
- Persistência descritiva não é desempenho de modelo.
- O detail não foi usado.
- O notebook (0,95 MB) e o `audit.json` (1 MB) excedem o ideal de artefatos pequenos. É uma
  exceção consciente, documentada no contrato de dados.

### Valor para o usuário e para a apresentação

Sustenta os blocos do pitch:

- **Problema:** 37 TWh em 2025, concentrado e em episódios longos.
- **Por que agora:** ENE mais que dez vezes maior na mesma janela, com crescimento no painel fixo.
- **Solução:** persistência que permite antecipar.
- **Credibilidade:** fórmula validada contra o ONS e limitações assumidas.

O alerta sobre o painel fixo solar evita uma afirmação forte demais no palco.

### Próximos passos

Etapa 2:

1. Congelar cortes temporais e protocolo as-of com cenários de latência.
2. Implementar baselines e métricas por fonte e causa.
3. Buscar sinais sistêmicos ex-ante para ENE.
4. Decidir o tratamento das 21 linhas negativas e das entidades renomeadas.

## 2026-09-19 - Etapa 1.5: verificação adversarial independente

### Contexto e pergunta

Antes de entregar a Etapa 1, um agente verificador com contexto limpo e acesso somente leitura
tentou quebrar o código, os números e as afirmações das entradas 1.1–1.4.

### Fatos e evidências observados

- Cerca de 25 números dos documentos, do notebook e dos relatórios foram recalculados de forma
  independente com DuckDB sobre `data/raw` e `data/interim/official`. Todos conferiram.
- **Defeito confirmado, dormente.** `strip_chars()` do Polars remove tab e quebra de linha;
  `trim()` do DuckDB, sem argumento, não remove. Um rótulo como `"\tREL\n"` seria `REL` em
  Polars e `DESCONHECIDA` em DuckDB. Nenhum arquivo local ou oficial contém esses caracteres,
  então nenhum número publicado foi afetado.
- A aparente divergência entre “29 gerações negativas” (1.1), “21 eólicas” (contrato) e “20
  sob limitação” (alvo) foi resolvida: são recortes diferentes. São 21 eólicas (20 limitadas)
  + 8 solares = 29.

### Interpretação e decisão

Corrigir a paridade com um conjunto explícito de espaços (espaço, tab, LF, CR) nos dois
backends e também na comparação de rótulos de `revision_check`. A colisão teórica do token
`'<NULL>'` em `identity_drift` foi aceita como risco documentado: esse literal não ocorre nos dados.

### Implementação e validação

Casos de tab e quebra de linha foram adicionados ao teste de paridade. Eles falharam (Red) e
passaram após a correção. `official-comparison.json` foi regenerado: as diferenças ficaram
abaixo de 10⁻¹¹ % e vêm da ordem de soma paralela do DuckDB, sem mudança de resultado.

### Limitações, valor e próximos passos

A verificação reforça a credibilidade dos números do pitch, mas não substitui revisão de
especialista do setor elétrico. A Etapa 1 está pronta para aprovação e commit pelo responsável.

## 2026-09-20 - Correção de interpretação no fechamento da Etapa 1

### Contexto e pergunta

Uma revisão final identificou que a entrada 1.4 e a síntese do notebook aproximavam duas
dimensões distintas: causa (`CNF`/`ENE`) e origem (`LOC`/`SIS`). A mesma redação sugeria
simultaneidade entre entidades sem que a EDA tivesse calculado coocorrência temporal.

### Fatos e evidências observados

O notebook mede separadamente a participação de energia por causa, a fração de intervalos por
origem e a duração/persistência dos episódios em cada entidade. Ele não cruza causa com origem
na conclusão citada nem mede quantas entidades sofrem corte simultaneamente em cada janela.

### Interpretação e decisão

A conclusão anterior "CNF/local para ENE/sistêmico" fica substituída por duas afirmações
independentes: ENE passa a dominar a energia estimada em 2025/2026, e SIS predomina entre as
origens registradas. Episódios longos são fato observado; simultaneidade continua hipótese.
Persistência passa a ser descrita como sinal temporal candidato à antecipação, não como prova de
capacidade preditiva.

### Implementação, limitações e próximos passos

A síntese do notebook foi corrigida sem alterar código, dados, gráficos ou resultados numéricos.
A Etapa 2 deve medir desempenho fora da amostra e, se a simultaneidade for relevante para o
produto, incluir uma análise explícita de coocorrência por janela e região.

## 2026-09-22 - Etapa 2A: decisões metodológicas e protocolo experimental aprovado

### Contexto e pergunta

Partimos do commit `ce43c48fe974a5c36fba42ce1bfd3dc486f501f9`, com a Etapa 1 fechada e
o Git limpo. O responsável pediu uma etapa exclusiva de raciocínio e discussão antes
de implementar ou treinar modelos. A pergunta era como comparar previsões de corte
de forma útil para o gerador, sem usar informações que não estariam disponíveis na
emissão e sem escolher antecipadamente um algoritmo.

A discussão foi conduzida em linguagem progressivamente mais acessível. Primeiro,
esclarecemos os horários das janelas, a diferença entre data da ocorrência e data de
publicação, e por que a validação escolhe enquanto o teste final avalia uma escolha
já congelada. Depois, o responsável solicitou todas as decisões restantes em uma
única lista, aprovou o conjunto e refinou o orçamento e a divisão entre máquinas.

### Fatos e evidências observados

Foram lidos os documentos obrigatórios, o notebook e o código/testes relevantes.
A inspeção foi somente leitura: nenhuma feature experimental, baseline ou modelo
foi implementado e nenhum treinamento ou métrica preditiva foi executado nesta etapa.

As bases principais contêm 10.806.720 observações, de outubro/2023 a agosto/2026 para
eólica e abril/2024 a agosto/2026 para solar. A integrada sobrepõe as principais;
o detail não tem associação de conjuntos completamente validada. Há 21 volumes
eólicos indeterminados, 42 restrições solares com rótulo desconhecido e ausência
de PAR. Esses fatos vêm da auditoria e do notebook, não de novos experimentos.

A pesquisa nas fontes públicas foi motivada por duas dúvidas reais do protocolo:

- Os catálogos ONS informavam atualizações às 12h e 19h. A rotina RO-AO.BR.13,
  revisão 09, usa horário de Brasília e descreve apuração do dia anterior, com
  exceções de dias não úteis e flexibilidade às segundas/após feriados. Isso não
  garante que cada arquivo esteja completo às 19h nem prova a regra histórica
  para todos os anos do snapshot.
- A inspeção somente leitura de agosto/2026 dos dados oficiais intra-semihora
  encontrou todos os 215.685 registros eólicos e 74.886 solares com início/fim da
  restrição dentro da meia hora iniciada em `din_instante`. Exemplos: 00h contém
  00h00–00h29; 23h30 contém 23h30–23h59. URLs, contagens, comparação e hashes estão
  na seção 1.2 do [protocolo](experimental-protocol.md). Não foram incorporados
  novos dados ao snapshot nem aos resultados da Etapa 1.

O Mac disponível tem 8 GiB de memória. O responsável informou um computador dedicado
com Ryzen 5 5600X, 32 GB DDR4 a 3.200 MT/s, RTX 2060 de 6 GB e aproximadamente 580 GB
livres em SSD. O local usual do clone tem cerca de 44 GB livres em outra unidade.
As especificações do outro computador são informação do usuário, não uma medição
remota feita nesta sessão. Sistema operacional e caminhos serão verificados no destino.

### Interpretação e decisão

O protocolo aprovado está em [experimental-protocol.md](experimental-protocol.md).
Ele diferencia evidências, hipóteses, decisões, concretizações de implementação e
questões necessariamente dependentes de resultados. As decisões centrais são:

- Renovar previsões a cada 30 minutos, sempre cobrindo 24h. O timestamp passa a ser
  tratado como início: emissão 10h prevê primeiro 10h–10h30 e termina às 10h do dia
  seguinte. Isso evolui o inventário anterior, que começava em `t0 + 30 min`.
- Simular liberação integral às 19h30 do próximo dia útil, com calendário conservador
  explicitamente versionado. O horário é hipótese experimental, não SLA do ONS.
  Executar sensibilidade com mais 24h de atraso. Não reconstruir chegadas parciais
  das 12h a partir de um arquivo revisado que não registra sua disponibilidade.
- Tratar corte positivo como alerta principal e ordem de limitação como segunda
  tarefa. Isso evolui a preferência inicial por comando no documento de alvos.
  Ordens sem perda continuam relevantes, sem serem confundidas com energia perdida.
- Estimar volume condicional positivo e avaliar também o produto de probabilidade
  e volume sobre todos os casos válidos. Manter MWmed/MWh, cauda e os 21 nulos.
  Antecipar causa entre ordens conhecidas, preservando REL/CNF/ENE e sem inventar PAR.
- Comparar baselines temporais/estatísticos com famílias linear regularizada e
  boosting tabular, com LightGBM como candidato. Separar fontes e compartilhar
  aprendizado entre suas entidades, com horizonte como feature.
- Usar quatro validações de quatro meses, de janeiro/2025 a abril/2026, com treino
  crescente. Reservar maio–agosto/2026 para teste após escolha congelada. Ajustes
  internos, calibração e limiares usam exclusivamente segmentos anteriores.
- Manter painel aberto principal, aquecimento de 28 dias/80% e fallback explícito.
  Não selecionar retrospectivamente entidades sobreviventes, preencher ausências
  com zero ou usar atributos posteriores à emissão.
- Exigir probabilidades de ocorrência e avaliação de calibração. Intervalo de volume
  é recomendado, condicionado à execução e validação de cobertura. Probabilidade
  estimada não significa porcentagem de certeza de que uma decisão está correta.
- Fixar antes dos resultados margens práticas: +0,02 de AP, redução de 5% no MAE
  completo sem piorar WAPE e +0,02 de macro-F1; melhorar em três de quatro rodadas,
  com proteções de estabilidade, Brier, suporte, incerteza, entidades e episódios.
  Esses números são critérios aprovados para comparação, não métricas observadas.

O teste final não escolhe o vencedor: consultar sucessivamente seus resultados
também permite sobreajuste humano. Ele pode vetar adoção, mas não deve promover um
segundo colocado e continuar sendo descrito como avaliação independente da escolha.
Da mesma forma, prever períodos históricos é um ensaio para medir utilidade futura;
a simulação precisa respeitar o que poderia ser conhecido em cada emissão.

### Alternativas consideradas

Usar também meio-dia seria tecnicamente possível em uma coleta real. O problema
retrospectivo é desconhecer quais registros chegaram em cada publicação. A integração
foi adiada pelo escopo do hackathon, com proposta de capturas versionadas futuras.
Uma piora com histórico antigo não provará que essa integração resolverá o erro.

Prever só uma vez por noite simplificaria a emissão, mas reduziria a cobertura futura
ao longo do dia. A atualização de meia em meia hora foi mantida, mesmo sem novos
dados em cada emissão. Modelos recursivos, 48 modelos distintos, fontes conjuntas,
rolling de 12 meses, meteorologia e busca extensa ficaram adiados.

O teto inicial sugerido de 500 mil exemplos de treinamento foi revisto quando o
responsável informou a máquina dedicada. Ele significava amostragem, não lote de
leitura. A decisão final é priorizar todos os exemplos elegíveis. Uma execução
pequena serve para verificar funcionamento e medir recursos; não escolhe candidatos.
Amostragem só será considerada diante de inviabilidade demonstrada e registrada.
Processamento em lotes não garante que todo estimador treine fora da memória.

O orçamento de 12h é planejamento inicial da execução inteira, não previsão de
duração ou 12h por modelo. Os 50 GiB discutidos representam referência de armazenamento
de artefatos, não RAM; são revisáveis por medição, sem apagar resultados negativos.

Esperar pela AWS para os primeiros resultados foi rejeitado: concentraria ambiente,
implementação e descoberta de desempenho no evento. Experimentos e ajuste final são
planejados localmente; AWS fica para disponibilizar a solução, sem exigir retreino.

### Implementação e validação

Nesta etapa, foram alterados exclusivamente o protocolo e esta entrada append-only.
Os documentos históricos da Etapa 1 foram preservados; o protocolo registra as
evoluções de semântica e passa a especificar o experimento. Não foram alterados
código, dependências, notebook, dados ou resultados experimentais.

A Etapa 2B será implementada e testada no Mac, com caminhos genéricos/configuráveis.
O responsável transferirá/clonará os commits para o computador dedicado, editará
os caminhos locais e realizará ali o piloto e os treinamentos. Arquivos grandes,
caches e temporários também precisam usar o SSD externo escolhido. Um clone do remoto
não transfere commits que não receberam push: o handoff exige Git bundle ou cópia/clone
local e transferência separada dos dados ignorados, conferindo hashes no destino.

Verificações de fechamento documental executadas: `git diff --check`,
`uv run --no-sync ruff check .` (sem achados) e
`uv run --no-sync ruff format --check .` (33 arquivos já formatados). Uma checagem
somente leitura confirmou links locais, ausência de whitespace residual, formato dos
hashes de pesquisa, escopo restrito aos dois documentos e que o diário anterior foi
preservado byte a byte como prefixo da nova versão. A revisão de consistência cobriu
horários, cortes internos/externos, regras de fallback e handoff entre máquinas.
Não foram executados testes de treinamento nem a suíte que reexecuta a EDA: não houve
mudança de código e o escopo autorizado era exclusivamente documental.

### Limitações e incertezas

Não existe desempenho preditivo medido nesta etapa, nem garantia de treinamento
completo em determinado tempo. O snapshot contém revisões e não possui vintages;
o calendário de publicação é hipotético. O período reservado para teste já apareceu
na EDA descritiva. As faixas de incerteza, adequação do histórico noturno e modelos
finais dependem de experimentos e têm regras explícitas na seção 11 do protocolo.

A implementação pronta no Mac não significa que a Etapa 2B experimental terminou.
Ela só se completa depois da execução real, com falhas, cobertura, resultados
negativos e limitações preservados. Publicar um modelo retreinado posteriormente
não transfere automaticamente a avaliação independente de uma versão anterior.

### Valor para o usuário e para a apresentação

O gerador poderá distinguir risco de ordem, risco de perda energética, quantidade
esperada e causa condicional. A apresentação terá uma história verificável: o que
era conhecido na previsão, contra quais regras simples a IA foi comparada e onde
ela agrega ou não valor. Não se transforma persistência descritiva em acurácia,
porcentagem de saída em certeza ou simulação de horário em garantia de produção.

### Próximos passos

Implementar o protocolo com TDD no Mac, preparar configuração e handoff entre máquinas,
executar a campanha no computador dedicado e entregar o pacote neutro para análise.
A decisão de modelos virá depois dos resultados, seguida de ajuste/avaliação final
com teste protegido. Não houve push, treinamento ou implantação nesta etapa.

## 2026-09-22 - Correção do handoff entre o Mac e o computador dedicado

### Contexto e pergunta

Após a aprovação do protocolo, o responsável esclareceu que o computador dedicado
será exclusivamente um executor das tarefas pesadas. A implementação, a análise e
qualquer commit devem permanecer no Mac.

### Decisão

O código e a configuração já commitados no Mac serão levados ao computador dedicado
por cópia local, bundle ou meio equivalente, com caminhos editáveis e sem valores
pessoais versionados. Essa máquina não receberá desenvolvimento nem criará commits.
Ao final, serão trazidos de volta somente os artefatos da execução: manifesto,
métricas, previsões, modelos, logs, diagnósticos, falhas, checksums e relatório.
Commits, correções e análise dos resultados serão feitos no Mac após a conferência
dos artefatos.

### Limitações e próximos passos

O remoto não será usado como canal implícito de transferência: sem push, alterações
locais não aparecem em um clone remoto. O procedimento de transferência do código
e dos artefatos deve ser executado pelo responsável, preservando hashes. O prompt da
Etapa 2B deverá repetir essa separação e exigir configuração genérica dos diretórios.

## 2026-09-22 - Branch dedicada para a Etapa 2

### Contexto e decisão

O responsável pediu que o protocolo e a implementação da Etapa 2 não fossem mantidos
na `main`, seguindo o padrão de branch usado na Etapa 1. Foi criada a branch local
`etapa-2-experimental`, que contém o commit documental da Etapa 2. A `main` será
preservada no commit anterior ao protocolo.

Toda implementação da 2B deverá ocorrer nessa branch. O Sol não fará merge durante
a implementação ou a execução. Depois que os artefatos retornarem do computador
dedicado, a análise da 2C decidirá se a integração é apropriada; somente então um
merge poderá ser feito na `main`.

### Limitações e próximos passos

Esta branch é local e não será enviada por push nesta etapa. O computador dedicado
receberá uma cópia do código da branch, executará apenas as tarefas pesadas e devolverá
os artefatos. Commits e análise continuam no Mac. O prompt da 2B deve exigir branch,
proibir merge antecipado e manter a `main` intacta até a decisão posterior.

## 2026-09-22 - Etapa 2B: implementação experimental pronta no Mac

### Contexto e pergunta

A Etapa 2A foi aprovada no commit `fe71446d44aad1ec81cfb2219aadf87583c9e77c`.
A branch de trabalho continha também a extensão documental `cf21835`, que acrescentava
somente a regra de branch e handoff repetida pelo pedido atual. A árvore não era idêntica
ao commit aprovado; por isso o histórico foi preservado, sem reset, e a implementação
continuou exclusivamente em `etapa-2-experimental`.

A pergunta desta sessão foi como transformar o protocolo em código executável e
rastreável sem usar o Mac para a campanha pesada, sem conhecer informação futura e sem
converter uma família candidata em vencedora antes dos resultados.

### Fatos e evidências observados

- Foram lidos integralmente AGENTS, protocolo, roadmap, arquitetura, contrato, alvos,
  inventário, diário, pitch, as 40 células do notebook e os módulos/testes relevantes.
- O primeiro import do LightGBM no Mac falhou porque `libomp.dylib` não estava instalado.
  Após instalar `libomp` pelo Homebrew, as duas famílias ajustaram fixtures sintéticas.
  Isso é requisito técnico do macOS, não evidência a favor ou contra LightGBM.
- O `preflight` reconheceu a branch, os dois Parquet principais e caminhos externos com
  espaços. Ele informou cerca de 138 GB livres no volume usado apenas para essa checagem;
  esse número é do Mac e não estima o espaço do computador dedicado.
- A suíte completa terminou com **141 testes aprovados em 13,40 s**. Também passaram
  `ruff check`, `ruff format --check` e `git diff --check` no fechamento.
- Não foi executado piloto com dados reais, treinamento completo, inferência externa ou
  cálculo de métricas preditivas. Portanto, não existe resultado de modelo nesta entrada.

### Interpretação e decisão

A implementação foi separada em contratos temporais/baselines, candidatos/métricas/
artefatos e orquestração da campanha. O cenário principal e o atraso +24h geram datasets
distintos; a sensibilidade carrega os artefatos congelados do run principal e declara
`models_retrained: false`. O teste reservado tem comando separado e exige flag mais uma
referência não vazia à decisão 2C.

O calendário conservador foi congelado em configuração versionada, com fontes e hash do
arquivo salvos no manifesto. Dias parcialmente facultativos contam como inteiros, como
aprovado. Essa convenção não foi reinterpretada como escala real do ONS.

### Alternativas consideradas

Materializar todo o snapshot ou a expansão de horizontes em pandas foi rejeitado. A
preparação percorre meses e a geração de features percorre dias com Polars, DuckDB,
PyArrow e Parquet. Cada estimador ainda precisa materializar sua matriz de ajuste; o
piloto técnico existe justamente para medir essa fronteira antes da campanha completa.

Instalar novas famílias, integrar meteorologia ou executar GPU foi rejeitado por fugir do
protocolo mínimo. Origem LOC/SIS, atraso +72h, intervalos de volume e sementes adicionais
permanecem extensões posteriores ao mínimo. Uma amostragem automática foi rejeitada: se
os 32 GB forem insuficientes, o executor deve salvar a falha e devolver a evidência ao Mac.

### Implementação e validação

Os commits atômicos desta sessão foram:

- `32a1ac6`: horizontes, disponibilidade, elegibilidade, agregados as-of e baselines;
- `1bf8e0e`: pré-processamento, candidatos, calibração, métricas e artefatos;
- `8129e6d`: calendário, features, treino crescente, piloto, campanha e CLI;
- `1cbfcb2`: fallbacks do pipeline, diagnósticos e sensibilidade +24h congelada.

Os testes cobrem primeira/última janela, 19h30, fins de semana/feriados, +24h, labels e
features futuras, novas entidades, 28 dias/80%, ausência/zero/nulo, os 21 indeterminados,
causas sem PAR, fallback, agregado regional as-of, ajuste só no treino, persistência,
semente, caminhos com espaços e trava do teste. Métricas sintéticas são apenas oráculos
de software; não foram incorporadas ao relatório como desempenho.

Os comandos de transferência, preparação, piloto, V1–V4, sensibilidade, retomada e retorno
dos artefatos estão em `docs/stage2b-execution.md`. O estado factual está em
`docs/reports/stage2b/implementation-status.md`, e o prompt autossuficiente para Astra em
`docs/handoffs/stage2c-prompt.md`.

### Limitações e incertezas

A campanha pode exceder memória, tempo ou armazenamento; não há medição real ainda. O
snapshot revisado continua sem vintages. A compilação de calendário é uma hipótese
conservadora versionada. O runner preserva falhas e runs incompletos, mas sua eficiência
em centenas de milhões de unidades operacionais só será conhecida no piloto dedicado.

O caminho do teste reservado valida a autorização, mas a receita congelada ainda não
existe: ela será produto da 2C. Logo, a porta informa essa ausência e não abre o período.
Nenhum merge para `main`, push, treino real ou execução do teste foi realizado.

### Valor para o usuário e para a apresentação

O pacote torna auditável o que o modelo sabia em cada emissão, qual fallback usou, a idade
do histórico e onde uma previsão não pôde ser avaliada. Isso permite apresentar ganhos e
fracassos contra regras simples sem esconder ordens com volume zero, casos indeterminados,
entidades novas ou degradação por atraso.

### Próximos passos

Transferir o commit final por bundle/cópia local, executar preflight e piloto no computador
dedicado e devolver os artefatos com checksums. Se o piloto for viável, executar V1–V4 e
+24h, uma rodada pesada por vez. Se não for, não amostrar no executor: registrar recursos,
falha e projeção, voltar ao Mac e decidir a contingência. Depois, Astra executa a Etapa 2C,
aplica os critérios por tarefa/fonte e decide se o teste reservado pode ser liberado.

## 2026-09-22 - Etapa 2B no computador dedicado: portabilidade Windows e medição de viabilidade

### Contexto e pergunta

O código da 2B (commit `e389332`) chegou ao computador dedicado, que roda Windows 11 Pro
(32 GB de RAM, 12 CPUs lógicas). As perguntas eram duas: a implementação roda nesse host
e a campanha completa cabe no orçamento de 12 horas do protocolo (§12.2)?

### Fatos e evidências observados

- Branch, commit e worktree conferiam. O SHA-256 das duas bases principais bate com
  `docs/reports/stage1/audit.json`. As cópias para a raiz externa de dados conferem.
- No Windows, `import resource` (módulo exclusivo de Unix) em `preparation.py` e
  `runner.py` impedia o CLI de carregar, inclusive o `preflight`. As chaves de
  `checksums.json` saíam com `\`. Um teste lia Markdown sem UTF-8.
- Depois das correções: `pytest` com 143 testes aprovados no Windows, `ruff check` e
  `ruff format --check` limpos, e `preflight` aprovado com caminhos externos com espaços.
- `prepare-targets` levou 60,5 s no cenário principal e 50,9 s no +24h, com pico de cerca
  de 1,0 GB. As contagens foram 7.951.920 linhas eólicas e 2.854.800 solares.
- Sonda de `build-features` para um único dia eólico (15/01/2025): nenhum dia concluído
  em 544,7 s. Foi interrompida pelo operador.
- Cronometragem de um único `t0` eólico (features mais 30 requisições de baseline): não
  concluiu em mais de 20 minutos. Foi interrompida pelo operador.

### Interpretação e decisão

Os três problemas de portabilidade eram defeitos de software, sem efeito metodológico.
Foram corrigidos aqui com autorização explícita do responsável. A medição de memória
passou a ser portável e reportada em bytes (`peak_rss_bytes`), e as chaves de
checksum usam sempre `/`.

A geração de features e de baselines é inviável no desenho atual. Há três causas
principais: laços Python linha a linha, `_regional_frequency` recalculada sobre todo o
histórico para cada entidade e horizonte, e cada requisição de baseline percorrendo
toda a janela de histórico. Projeção mínima: mais de 16 h por dia de emissões, ou
milhares de horas por fonte e cenário. Há ainda um limite independente:
`campaign-round` e `sensitivity-round` fazem `collect()` de todo o período de
desenvolvimento. Estimativa aproximada: centenas de milhões de linhas de features e
cerca de quatro vezes isso em baselines por fonte, o que não cabe em 32 GB.

Nenhum dataset, piloto, rodada V1–V4 ou sensibilidade foi executado. Todas essas runs
ficam em "não iniciada — bloqueio de viabilidade".

### Alternativas consideradas

Amostrar dias, entidades ou exemplos para caber no orçamento foi rejeitado: seria mudança
metodológica não autorizada (§12.2). Rodar a sonda até o fim também foi rejeitado,
porque o piso medido já excede o orçamento. A alternativa prevista no protocolo é
reduzir materialização redundante e vetorizar preservando a semântica, usando a
implementação atual como oráculo de igualdade. Ela depende de decisão do responsável.

### Limitações e incertezas

As projeções são pisos obtidos por cronometragem interrompida, não durações completas. A
divisão do custo entre features e baselines não foi isolada. Mesmo com geração
eficiente, o ajuste com todos os elegíveis pode exceder a memória; isso só o piloto
mede. Observações de conformidade, sem correção aqui:

- os baselines são pontuados com limiar 0,5, e não pelo procedimento F2 interno (§7.2);
- os modelos usam 8 features numéricas e 4 categóricas, das cerca de 50 geradas;
- a sensibilidade fixa `entity_new` e `panel_fixed` como falsos.

### Valor para o usuário e para a apresentação

Nenhum resultado preditivo existe ainda. A evidência mostra que o gargalo é de
engenharia de dados, não de modelagem, e sustenta a narrativa de rigor: não se
reduziu o protocolo nem se inventou amostragem para declarar conclusão.

### Próximos passos

Decidir com o responsável se a geração de features e baselines e o carregamento da
campanha serão reescritos de forma vetorizada, com testes de igualdade contra a
implementação atual. Depois, repetir preflight, datasets, pilotos, V1–V4 e +24h, uma run
pesada por vez. Evidências operacionais ficam no diretório `execucao/` da raiz externa
do computador dedicado.

## 2026-09-22 - Etapa 2B: consolidação da sessão 01 e falha do verificador na continuação

### Contexto e pergunta

Retomar a execução no Windows dedicado, conferir o dataset eólico e somente então iniciar
piloto, medir populações e submeter uma única decisão de contingência. O responsável
passou a autorizar desenvolvimento e commits locais com TDD, sem push ou merge em main,
e exigiu executor durável, um processo pesado por vez e nenhuma edição do worktree
durante runs. Essa autorização prevalece sobre a separação Mac/Windows do protocolo.

### Fatos e evidências da sessão 01

Os fatos retrospectivos abaixo foram recuperados do handoff externo
`execucao/HANDOFF-sessao-01.md`; não são medições repetidas nesta continuação.

- Portabilidade: `07116b9` tornou a medição de pico de memória portável; `747d69c`
  normalizou checksums com `/`; `9589843` corrigiu leitura UTF-8. O import Unix de
  `resource` impedia inclusive o preflight no Windows.
- Os alvos foram preparados nos dois cenários em 60,5 s e 50,9 s: 7.951.920 linhas
  eólicas e 2.854.800 solares. Os alvos permaneceram inalterados depois desses commits.
- O desenho original não concluiu um dia eólico em 544,7 s, nem um único t0 em mais
  de 20 minutos. As interrupções e resultados incompletos foram preservados.
- `0ad6be4` vetorizou features/baselines com oráculo em `tests/reference_stage2b.py`
  e testes de paridade. `70a181d` acrescentou partições diárias paralelas. A medição
  vetorizada reportou 0,20 s por t0, 156 entidades e 7.488 linhas por emissão;
  uma sonda de sete dias levou 67 s com seis workers.
- Divergências intencionais testadas: volume indeterminado/restrição nula no baseline
  retorna nulo em vez de TypeError; schema estável mesmo com colunas inteiramente
  nulas; timestamps de ns para us; observações duplicadas rejeitadas (`a187150`).
  O handoff registra zero duplicatas e zero restrições nulas nos quatro caches reais.
- `f3cca8b` vetorizou categorias e limiar F2 usando oráculo específico. `f039347`,
  `064a064` e `f33c5b1` tornaram campanha/sensibilidade preguiçosas e particionadas,
  com oráculo `tests/reference_campaign_stage2b.py`. Foram integrados pelo merge
  explícito `ce73b6d`. Leitura preguiçosa reduz materialização desnecessária; não
  elimina a necessidade de cada estimador materializar seus exemplos de ajuste.
- Geração eólica principal em `70a181d`: 339.738.048 features, 1.358.952.192 baselines,
  1.884 arquivos e 943 dias percorridos. O `end.json` foi reconferido nesta sessão:
  exit 0, 8.105,6 s e pico amostrado da árvore de 4.622.155.776 bytes. Houve disputa
  de CPU durante a geração; isso não mede a taxa sem concorrência.
- A suíte reportada no handoff teve 187 aprovados e um skip no worktree sem Parquet.
  Não confundir esse resultado anterior com a validação desta continuação.

### Fatos e evidências da continuação

O checkout inicial estava limpo em main, `48f99230da6f6919c08259c18909aec939856d6d`,
e não no HEAD esperado. Foram lidos AGENTS e os documentos da 2B diretamente da
referência autorizada. A referência `etapa-2-experimental` apontava exatamente para
`ce73b6da02a009a49a71d928fc47f636687fcc38`. Não havia processos Python/uv experimentais
ativos nem passos iniciados sem end.json. Foi selecionada essa branch, sem alterar a
referência de main. Confirmou-se `f33c5b1` ancestral de HEAD; só então foram removidos
o worktree travado já integrado e sua branch, conforme solicitado.

O executor externo só aceitava o CLI experimental. Em ciclo Red–Green, acrescentou-se
`UvArgumentsPrefix`, mantendo o padrão anterior, para também executar o comando exato
`uv run python ...check_dataset.py...` com logs, PID, commit e amostras. O teste Red
rejeitou o parâmetro ausente; o Green verificou ambiente e argumentos com espaços
(exit 0, 1,7 s). O preflight original passou (exit 0, 4,6 s, ready=true), reconheceu
os dois Parquet e 620.980.277.248 bytes livres. Script anterior e evidências foram
preservados em `execucao/verificacoes/`.

O passo `check-noturno_dia_util-eolica-sessao02-001` executou o verificador original,
sem modificá-lo, com intervalo 01/10/2023 inclusivo a 01/05/2026 exclusivo. Terminou
em 188,8 s com exit **-1073740791**, sem produzir o JSON esperado e sem diagnóstico
em stderr. Pico de working set por processo: **29.270.798.336 bytes (27,3 GiB)**;
pico simultâneo da árvore capturado por amostragem: 11.545.206.784 bytes. São medidas
diferentes; a amostragem de 30 s pode perder picos. Uma inspeção intermediária registrou
52.914.651.136 bytes privados no Python. Isso evidencia pressão de memória, mas não
estabelece a causa da terminação nativa.

### Interpretação, limites do contrato e decisão

A listagem somente leitura confirmou **942 partições**, começando em 02/10/2023.
O gerador percorre 943 dias, mas `_write_feature_day` retorna sem criar arquivos se
não houver nenhuma feature. Pelo cenário noturno, o primeiro dia observado (domingo,
01/10) só é liberado em 02/10 às 19h30; não há entidade conhecida em 01/10. A ausência
da partição desse dia é coerente com o contrato de conhecimento, como já previsto no
handoff. O verificador, entretanto, exige partição em todos os dias civis e reprovaria
`all_partitions_present`. Não alteramos esse critério nem declaramos aprovação.

As demais checagens não têm resultado recuperável: schema único, t0 no intervalo e fora
do reservado, 48 horizontes, relação tau/t0 e grade, idade mínima do histórico, liberação
dos alvos depois de t0, ausência de PAR, quatro baselines por requisição e valores finitos.
O processo só grava o relatório no final. Não inferir aprovação dessas checagens das
contagens reportadas no handoff.

A contagem de linhas com `tau >= 01/05/2026` **não foi apurada**. A existência esperada
vem dos horizontes das emissões de 30/04. A proteção de pontuação foi conferida no código:
`_range` e `_validation_filter` exigem `t0 + 24h <= fim`, e `tau = t0 + (h - 1)*30min`.
Em V4, o último t0 permitido é 30/04 às 00h e o maior tau é 30/04 às 23h30. Os segmentos
internos terminam antes da validação e aplicam também disponibilidade dos rótulos. Assim,
os horizontes que cruzam maio ficam fora desses segmentos; nenhuma pontuação foi executada
nesta sessão. Isso é inspeção dos limites, não validação empírica do dataset completo.

Por determinação explícita do responsável, a continuação **parou na etapa 1**, antes de
piloto, projeção de memória por população, pergunta sobre amostragem e outros datasets.
As 18 runs permanecem não iniciadas; `execucao/run-index.json` registra o bloqueio e o
commit da geração eólica. Nenhum run recebeu falsamente um commit de execução. O índice
anterior foi preservado antes da atualização. Não houve amostragem, escolha de vencedor,
uso de métricas de piloto, execução do teste reservado, push ou merge em main.

### Alternativas, limitações e valor para o usuário

Não repetir automaticamente a varredura que falhou, nem corrigir o verificador para
produzir um sinal verde e prosseguir sem reportar. Uma correção técnica possível é
reduzir a memória da verificação por partições/streaming e distinguir dia sem população
conhecida de partição perdida, com testes antes; isso permanece proposta, não implementação.

Continuam registradas para a 2C as limitações do handoff: baselines com limiar fixo 0,5;
`threshold or 0.5` substitui limiar zero; só oito numéricas e quatro categóricas usadas;
recortes entity_new/panel_fixed falsos na sensibilidade; elegibilidade usa t0 em vez de
c(t0); avaliação condicional de volume contra toda a validação; warnings de bibliotecas.
Não corrigimos metodologia ou candidatos nesta continuação.

A distinção entre geração concluída e contrato ainda não validado impede apresentar
artefatos existentes como evidência de qualidade preditiva. O próximo passo é resolver
a falha técnica do verificador e reportar as checagens e a contagem tau de fronteira antes
de retomar a sequência solicitada. A decisão de contingência de treino continua pendente.

### Validação desta entrada e fechamento local

A primeira execução de `uv run pytest`, pelo executor com env.ps1 carregado, teve
187 aprovados e uma falha em `test_default_paths_are_local`: o teste espera `data/`
e `models/`, mas herdou os caminhos externos. Essa falha foi preservada. Sem alterar
código ou testes, um subprocesso repetiu exatamente `uv run pytest` removendo somente
`CURTAMAP_DATA_DIR` e `CURTAMAP_MODEL_DIR` do seu ambiente; os temporários permaneceram
externos. Resultado: **188 aprovados, 81 warnings, 109,31 s**. Os warnings foram
Polars is_in, LightGBM eval_set e event loop do ZMQ no Windows. `uv run ruff check .`
e `uv run ruff format --check .` passaram (75 arquivos formatados). Logs estão nos
passos `pytest-docs-sessao02-001`, `pytest-docs-sessao02-isolated-001`,
`ruff-check-docs-sessao02-001` e `ruff-format-docs-sessao02-001`. Nenhuma suíte rodou
junto com geração, treino ou verificação do dataset. O commit desta entrada é apenas
documental; a extensão do executor reside na raiz operacional externa e foi registrada
acima com cópia anterior e testes próprios.

## 2026-09-23 - Etapa 2B: verificador diário com progresso durável

### Contexto e decisão

Após a falha nativa do verificador externo, o responsável autorizou sua correção com
TDD e nova execução. A causa da terminação anterior continua não confirmada; a leitura
agregada de todo o dataset tinha pico observado de 27,3 GiB. A correção limita o trabalho
a uma partição diária e preserva a tentativa anterior, sem alterar Parquet, metodologia,
grade, candidatos ou filtros da campanha.

### Implementação e evidências

O novo módulo versionado `curtamap.experimental.dataset_verification` projeta somente
as colunas necessárias, lê um dia de cada vez e agrega contagens exatas. Cada partição
tem eventos de início e conclusão persistidos com flush/fsync em JSONL. A deduplicação
global de alvos indeterminados usa SQLite externo, com cache de 2 MiB, sem manter todos
os alvos em RAM. O JSON final, o progresso e o ledger têm nomes exclusivos; nova
tentativa não sobrescreve evidência. Erros de leitura geram resultado parcial explícito;
terminações nativas deixam ao menos os eventos já persistidos.

A liberação inicial é derivada do primeiro registro do cache e do calendário do cenário,
e comparada com o menor timestamp de liberação do próprio cache. Somente dias completos
anteriores a esse instante justificam ausência. Partição perdida após o primeiro
conhecimento, arquivo ausente, schema divergente ou dia incorreto continuam reprovados.
As 12 checagens originais foram preservadas, com a correção semântica de dia vazio; foram
acrescentadas verificações de chave/nulos, fonte, partição, primeira liberação e fronteira.
A checagem de 48 horizontes inclui agora limites 1–48, e quatro baselines por requisição
é verificado por chave, não apenas pelo total. Listas completas de causas/baselines
substituem a extração antiga de apenas uma linha, que podia dividir strings em letras.

As linhas com tau no reservado são contadas, sem calcular métricas ou abrir o teste.
O módulo usa `_validation_filter` da campanha para conferir as quatro validações reais
e registra os limites internos calculados por `internal_boundaries`. A desigualdade
`t0 + 24h <= fim` e o contrato de tau fundamentam também a exclusão nas faixas internas.

### TDD, limites e próximos passos

Red: `verifier-tdd-red-001` falhou na coleta por módulo ausente. Green: 17 testes
passaram; após ampliar os casos de contrato, 20 passaram em 3,55 s no passo
`verifier-tdd-refactor-001`. Há cobertura de leitura diária, calendário/feriado/+24h,
liberação adulterada, agregação exata, deduplicação entre dias, fronteira de maio,
horizontes duplicados/inválidos, chaves nulas, NaN/infinito, volume negativo, baseline
faltante apesar do total correto, schema, arquivos ausentes/corrompidos, progresso e
recusa de sobrescrita. Esses resultados são sintéticos e não aprovam o dataset real.

A implementação não determina se o dataset eólico está correto: isso exige a nova
varredura. O uso de memória passa a depender de um dia, incluindo agrupamentos e joins
de chaves; seu pico real ainda será medido. O checker externo original permanece intacto.
O valor desta correção é transformar uma falha opaca em evidência auditável, sem escolher
modelos nem reduzir dados. Próximo passo: concluir a suíte/Ruff, commitar a correção e
executar o novo verificador pelo executor durável, com novos identificadores e artefatos.

Validação antes do commit: **208 testes aprovados, 81 warnings, 109,13 s** no passo
`verifier-pytest-full-001`. Foi usado o mesmo isolamento documentado de Settings:
`uv run pytest` em subprocesso sem CURTAMAP_DATA_DIR/MODEL_DIR, mantendo temporários
externos. `uv run ruff check .`, `uv run ruff format --check .` (77 arquivos) e
`git diff --check` passaram. Nenhuma métrica experimental foi calculada.

## 2026-09-23 - Etapa 2B: contrato eólico aprovado pelo verificador diário

### Execução e proveniência

O módulo corrigido foi commitado em `a5b4a87c829e410ffcbf84c379bc7200709587c8`.
O primeiro despacho `check-noturno_dia_util-eolica-v2-001` encerrou antes de criar o
passo ou iniciar Python; o fato foi preservado em `verificacoes/check-v2-001-falha-despacho.txt`.
Não há resultado de verificação dessa tentativa. O despacho seguinte usou um script
PowerShell de lançamento, mantendo `run-step.ps1` como executor e preservando seus logs.

O passo `check-noturno_dia_util-eolica-v2-002` concluiu com **exit 0**, em **272,2 s**,
sem stderr. Pico por processo: **1.291.628.544 bytes (1,20 GiB)**. Pico amostrado da
árvore: **1.209.815.040 bytes (1,13 GiB)**. A verificação anterior tinha pico por
processo de 29.270.798.336 bytes (27,3 GiB) e terminou sem relatório; ela permanece
preservada. A redução observada foi de cerca de 95,6% no pico por processo, sem amostrar
os dados. São execuções de verificadores diferentes, não comparação de modelos.

Artefatos na raiz externa: `execucao/verificacoes/dataset-noturno_dia_util-eolica-v2-002.json`,
`.progress.jsonl` e `.targets.sqlite`; logs em `execucao/passos/check-noturno_dia_util-eolica-v2-002/`.
O JSON identifica o código de verificação `a5b4a87` e o código de geração `70a181d`.
Nenhum arquivo do dataset foi reescrito e não houve outro processo pesado concorrente.

### Análise de todas as checagens

As **18 checagens passaram**:

- Partições: 942 presentes dos 943 dias civis; somente 01/10/2023 é vazio esperado.
  Nenhuma partição inesperadamente ausente, nenhum arquivo faltante ou partição extra.
- Schema: um único schema de features e um único schema de baselines.
- Intervalo: t0 mínimo 02/10/2023 19h30, máximo 30/04/2026 23h30; zero t0 no reservado.
- Horizontes: **7.077.876 emissões por entidade**, todas com 48 linhas e 48 horizontes
  distintos em 1–48, somando **339.738.048 features**.
- Contrato tau/grade: zero divergências da relação tau = t0 + (h−1)×30min, zero t0 fora
  da grade de meia hora e zero linhas no dia de partição incorreto.
- Histórico: zero idades abaixo de 30 minutos ou não finitas.
- Rótulos: zero alvos observados já liberados em ou antes de t0.
- Causas: CNF, ENE e REL; nenhuma linha PAR.
- Baselines: **1.358.952.192 linhas**, exatamente quatro por chave e no agregado.
  Identidades: historico, mesmo_horario_dia_anterior, mesmo_horario_recente, ultimo_valor.
- Valores: zero probabilidades não finitas, volumes esperados negativos/não finitos,
  chaves obrigatórias nulas ou fallback_level ausente.
- Fonte: uma fonte eólica e 180 entidades distintas.
- Primeiro conhecimento: primeiro registro no cache em 01/10/2023 00h; primeira liberação
  em 02/10/2023 19h30, idêntica à derivada do calendário. Zero emissão antes disso.
- Fronteira: zero tau no reservado depois dos filtros reais de validação V1–V4.

Contagens adicionais: 325.435.632 linhas elegíveis por histórico; 2.207.736 linhas sem
alvo observado; zero alvo observado com volume indeterminado neste dataset. Esse zero
não revoga os 21 volumes indeterminados do snapshot completo: as populações são distintas,
e não foi feita investigação adicional desses 21 casos ou pontuação de maio–agosto.

### Primeiro dia e linhas de fronteira

A ausência de 01/10 não é perda de arquivo: antes de 02/10 às 19h30 nenhuma observação
estava liberada. A verificação usou o primeiro registro e a liberação real do cache,
comparados com o calendário congelado; não aceitou uma exceção de data arbitrária.

Foram contadas **172.584 linhas com tau >= 01/05/2026**, das últimas emissões de 30/04.
O tau máximo do dataset é 01/05/2026 23h. Elas não são pontuadas: o filtro real exige
`t0 + 24h <= fim`. Em V4, t0 máximo aceito é 30/04 00h e tau máximo é 30/04 23h30.
As contagens após esse filtro foram 42.851.184 linhas em V1, 43.830.768 em V2,
43.109.184 em V3 e 42.194.016 em V4; em todas, **zero tau no reservado**. São contagens
de população anterior aos filtros específicos de tarefa, não métricas nem as contagens
de treino ainda pendentes.

O relatório registra U/K/C das rodadas: V1 = 04/11, 02/12, 30/12/2024;
V2 = 05/03, 02/04, 30/04/2025; V3 = 04/07, 01/08, 29/08/2025;
V4 = 04/11, 02/12, 30/12/2025. `_range` também exige janela inteira anterior ao fim do
segmento e aplica liberação do rótulo; seus limites são anteriores a maio/2026. Essa
última afirmação é prova pelos limites do código, não varredura de treino por tarefa.

### Decisão, limitações e próximos passos

O bloqueio de verificação do dataset eólico principal foi resolvido. `run-index.json`
foi atualizado com aprovação, commit, tempo, memória e contagem de fronteira. As 18 runs
experimentais continuam não iniciadas. Contrato aprovado não demonstra qualidade de
previsão, viabilidade de treino completo nem conformidade metodológica de toda a campanha.
As limitações registradas anteriormente permanecem para a 2C. Não houve amostragem,
métricas de seleção, vencedor, teste reservado, push ou merge em main.

Próximo marco: piloto técnico eólico, declarando o recorte head(2M) nos primeiros dias
de outubro/2023, seguido das contagens exatas V1–V4 por segmento/tarefa e pergunta única
sobre contingência antes de qualquer amostragem. Os demais datasets e pilotos seguem
na ordem já definida pelo responsável.

Validação do registro de resultados antes do commit documental: **208 testes aprovados,
81 warnings, 108,32 s**, no passo `verifier-report-pytest-001`, com o isolamento de Settings
já documentado. `uv run ruff check .`, `uv run ruff format --check .` e `git diff --check`
aprovados. Relatório de leitura com cópia do JSON foi entregue na pasta outputs da sessão.

## 2026-09-23 - Etapa 2B: piloto técnico eólico e conferência dos artefatos

### Contexto e conferência da retomada

O prompt de retomada foi lido integralmente. Branch `etapa-2-experimental`, HEAD
`48bc71a39c411c2c8725a744cdf3548baf7e3b9e`, árvore limpa, somente o worktree principal,
`main` em `48f9923`, ausência de processos experimentais e de passos sem `end.json`
coincidiam com o handoff. As 18 runs estavam não iniciadas. O JSON aprovado continuava
com 18 contratos satisfeitos. Não houve evidência de alteração que justificasse refazer
a geração ou a verificação eólica; ambas foram preservadas.

### Fatos observados e validação técnica

O passo e run `pilot-eolica-001` executou no mesmo commit pelo executor durável, com
ambiente e temporários externos. `end.json` registra exit 0 e **60,5 s** (inclui a
granularidade de monitoramento de 30 s); os timestamps do manifesto delimitam cerca
de 35,5 s entre criação e finalização do run. Pico por processo: **1.719.541.760 bytes
(1,60 GiB)**; pico amostrado da árvore: **1.666.011.136 bytes (1,55 GiB)**.

As duas famílias produziram os oito ajustes: 500.000 exemplos para cada ocorrência,
191.505 para volume condicional e 269.514 para causa, por família. O relatório contém
zero falhas, nenhuma classe de causa ausente e `selection_metrics_emitted=false`.
Não há diretório de falhas nem conteúdo no stderr do piloto. As durações dos ajustes
ficaram entre 1,60 e 10,01 s; não são estimativas do custo do treinamento completo.

A auditoria externa `audit-pilot-eolica-001`, também pelo executor, verificou os dez
hashes do inventário, recarregou os oito modelos joblib e testou 256 saídas por modelo:
probabilidades finitas em [0,1], volume finito não negativo, causas reconhecidas e soma
unitária das probabilidades de causa. Todas passaram; exit 0, sem stderr. A auditoria
não recalculou os contratos do dataset nem produziu métricas preditivas. Tamanho real
do run após finalização: **3.706.035 bytes**. Espaço livre em Y na largada: cerca de
620,3 GB decimais.

Artefatos externos: `experimentos/pilot-eolica-001/`,
`execucao/passos/pilot-eolica-001/`, `execucao/passos/audit-pilot-eolica-001/` e
`execucao/verificacoes/audit-pilot-eolica-001.{py,json}`. A auditoria preserva parâmetros
efetivos e iterações dos estimadores; LightGBM efetivamente usa **n_jobs=1**, enquanto
o manifesto/configuração declara `threads=6`. Nenhum parâmetro foi alterado.

### Interpretação, alternativas e limitações

O `head(2.000.000)` do CLI cobre **02/10/2023 19h30 a 08/10/2023 11h30**, com
**zero linhas elegíveis por histórico**. O piloto filtra alvos por tarefa, mas não
aplica a elegibilidade de histórico usada na campanha. Portanto, o resultado comprova
apenas execução, persistência, recarga e contratos técnicos nesse passado curto.
Não comprova capacidade para todo o treino elegível, convergência em outras populações,
qualidade de previsão ou suficiência operacional; não permite escolher candidatos.
O pico reportado por ajuste é o pico acumulado do processo, não uma medição independente.

Repetir o piloto ou ampliar sua população agora foi descartado: não remove a necessidade
de contar os segmentos reais. A próxima decisão deve se apoiar nas populações exatas e
na projeção de memória, incluindo trechos simultâneos e matrizes temporárias. A divergência
de threads será preservada e apresentada na decisão consolidada, sem correção silenciosa.

### Valor para o usuário e próximos passos

O piloto remove a incerteza de portabilidade e serialização para o caminho exercitado.
Pode sustentar a demonstração de rastreabilidade técnica, nunca uma alegação de ganho
energético. Próximos passos: medir V1–V4 por segmento/tarefa com os filtros reais;
fundamentar uma pergunta consolidada de contingência; continuar os datasets restantes
sequencialmente. Treino completo segue condicionado à decisão de recursos. Teste
reservado, seleção de vencedor, push e merge em main permanecem bloqueados.

Validação antes do commit documental: **208 testes aprovados, 81 warnings, 118,39 s**
no passo `pilot-report-pytest-001`, com o isolamento de Settings do launcher externo.
`uv run ruff check .`, `uv run ruff format --check .` (77 arquivos) e `git diff --check`
passaram. Esses warnings da suíte não são warnings do piloto, cujo stderr ficou vazio.
