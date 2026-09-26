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

## 2026-09-22 - Contrato de saída, preditor provisório e plano de trabalho paralelo

### Contexto e pergunta

Terça-feira, com a Etapa 2 ainda em andamento. O presencial vai de 25 a 27/09 e a apresentação
é no domingo, com três desenvolvedores e a maior parte do trabalho concentrada no responsável.
Pergunta: dá para adiantar as etapas 3 a 6 sem esperar a decisão de modelo da Etapa 2C, e sem
retrabalho quando ela sair?

### Fatos e evidências observados

- Recomendação, interface e deploy dependem do formato da previsão, não do algoritmo. O
  protocolo da Etapa 2A (§2.1, §5 e §7) já define unidade, horizontes, tarefas e baselines.
- A 2C pode declarar uma tarefa `inelegivel` (por exemplo, causa) ou preferir um baseline. O
  handoff da 2C também prevê uma Etapa 2D, o que pode atrasar a decisão para depois de sexta.
- Com o cenário noturno do protocolo, a observação de `tau − 24h` quase nunca está liberada no
  instante da previsão: numa terça às 10h, o último dia liberado é domingo.
- Execução real em 14/10/2025 às 10h (corte `nightly_cutoff` = 13/10 00h): leitura de 28 dias
  (299.376 linhas) em 0,2 s e previsão em 0,08 s; 154 entidades eólicas e 69 solares, 10.704
  linhas, nenhuma sem previsão. Alertas: 58,6% das janelas eólicas e 32,2% das solares. Energia
  somada nas 48 janelas: ≈183 GWh eólica e ≈48 GWh solar.

### Interpretação e decisão

- O formato da saída foi fixado antes do modelo em `src/curtamap/contracts.py`
  (`FORECAST_SCHEMA`, `RECOMMENDATION_SCHEMA` e validadores). Causa e previsão podem ser nulas,
  sempre com motivo, para que uma inelegibilidade decidida na 2C não mude o contrato.
- O preditor provisório é o baseline "mesmo horário mais recente disponível, até 28 dias"
  (§7.2), e não o "mesmo horário do dia anterior". Pela latência, este último cairia quase
  sempre no fallback.
- O teste reservado (a partir de 01/05/2026) é recusado por padrão na leitura e na previsão.
- Trabalho dividido em trilhas por branch (`docs/parallel-plan.md`): o responsável segue na
  Etapa 2, o Dev 2 fica com a Etapa 3 e o Dev 3 com a Etapa 4 e a preparação local da Etapa 5.
  Prompts autossuficientes em `docs/handoffs/stage3-prompt.md` e `stage4-prompt.md`.
- Interface em Streamlit, decidida pelo responsável: menos código, um único container e
  contrato só em Python. Para evitar conflitos, a interface será multipágina, com um arquivo
  por tela.

### Alternativas consideradas

- **Esperar a 2C:** adiada. Custaria dias para evitar poucas horas de ajuste; o contrato já
  absorve as decisões possíveis da 2C.
- **Mock sintético em vez de baseline:** descartado. O baseline usa dados reais e é
  explicitamente rotulado.
- **React + FastAPI:** preferência inicial do responsável, trocada por Streamlit pelo prazo.
- **Fallback regional do protocolo no preditor provisório:** adiado. Sem observação no
  horário, a previsão fica nula com motivo, em vez de um número de baixa evidência.

### Implementação e validação

TDD em ambos os módulos: `tests/test_contracts.py` e `tests/test_forecasting.py` falharam na
coleta antes da implementação e passaram depois. Os testes cobrem vazamento após o corte, janela
de 28 dias, volume inválido, causas não aprendíveis, identidade por fonte, grade de 30 minutos e
bloqueio do teste reservado.

Uma verificação adversarial independente não encontrou vazamento temporal. Ela conferiu as
fronteiras do corte noturno (inclusive exatamente às 19h30), a janela de 28 dias até o
microssegundo, o bloqueio do teste reservado e a execução com Parquet real de mar–abr/2026.
Encontrou, porém, lacunas no validador: comparações com nulo escondiam alerta sem `p_corte`,
`tau` nulo, energia nula com volume preenchido e energia ausente em recomendações. Também
apontou que faltavam campos de proveniência exigidos pelo protocolo. Tudo foi corrigido com
testes antes, e o contrato ganhou `cenario_disponibilidade`, `instante_observacao` e
`cobertura_historico`. `causa_base` nula foi mantida de propósito: significa causa
indeterminada. Suíte completa: 149 testes aprovados com `PYTHONUTF8=1`.
`ruff check` e `ruff format --check` limpos. Sem essa variável, `test_feature_inventory` falha no
Windows porque lê o Markdown sem `encoding="utf-8"`. É um defeito anterior e fora deste escopo.
`.gitattributes` passou a usar `merge=union` no diário, para unir entradas de branches paralelas.

### Limitações e incertezas

- O corte de disponibilidade considera só fins de semana; os feriados do calendário da Etapa 2
  ainda não estão no `main`.
- As probabilidades do baseline são 0 ou 1, sem calibração nem intervalo de volume.
- Como o baseline copia o último dia liberado, a energia prevista herda o perfil desse dia.
  Nos ≈231 GWh do exemplo, o último dia liberado era um domingo, e a média diária de 2025 é
  ≈102 GWh. **Interpretação, não medida:** fins de semana com carga baixa podem inflar a
  previsão. Isso não foi quantificado.
- O esquema de recomendação é uma versão inicial. A Etapa 3 pode propor extensões por PR
  separado.

### Valor para o usuário e para a apresentação

Permite demonstrar o fluxo previsão → recomendação → decisão com dados reais antes da escolha do
modelo. O baseline também é o comparador que o modelo final precisa superar, o que sustenta a
narrativa de credibilidade: "comparamos com a regra simples que o gerador já poderia usar".

### Próximos passos

1. Responsável: fazer push do `main` e distribuir os prompts; seguir na 2B/2C.
2. Dev 2 e Dev 3: abrir as branches a partir do `origin/main` e trabalhar pelos prompts.
3. Depois da 2C: implementar o preditor escolhido atrás do `Predictor` e trocar na interface.
4. Corrigir a leitura sem encoding de `test_feature_inventory` num commit próprio.

## 2026-09-26 - Nova Etapa 2 (1/n): recomeço, trava de setembro, calendário e diagnóstico

### Contexto e pergunta

O responsável decidiu refazer a modelagem do zero, sem partir da receita da Etapa 2 anterior
(só 2 das 6 células usavam modelo, com ganho pequeno sobre o baseline). A pergunta de abertura
é: **o problema é tão complexo quanto o pipeline anterior (100+ M de linhas, ~50 features,
picos de 33 GB) sugeria?** O trabalho roda num notebook de 8 GB de RAM e 8 núcleos, sem
LightGBM, com o `HistGradientBoosting` do scikit-learn, que já é dependência.

### Fatos e evidências observados

- A base compacta (uma linha por usina × meia hora, com os alvos de `derive_targets`) tem
  7,95 M de linhas na eólica e 2,85 M na solar. O DuckDB a gera em ~2 s, com 1,2 GB de RSS.
- Com a emissão diária às 20h da véspera, o último dia liberado (L) fica 2 dias antes do
  dia-alvo (T) em 67% dos dias, 3–4 dias em 30% e até 7 dias perto de feriados.
- Diagnóstico em jan–ago/2026, com o alvo sendo o corte positivo por usina × meia hora
  (script exploratório; os números serão refeitos pelo módulo testado):

  | Preditor (mesmas linhas) | AP eólica | AP solar |
  |---|---|---|
  | `historico`: frequência da usina no slot, 28 d até L | 0,780 | 0,783 |
  | mesmo slot do último dia liberado | 0,595 | 0,560 |
  | oráculo: fração **realizada** de usinas do estado cortadas em T × slot | 0,945 | 0,943 |
  | oráculo: `historico` × nível estadual diário **realizado** em T | 0,879 | 0,909 |

  Correlação do nível estadual diário entre L e T: 0,57 na eólica e 0,28 na solar.
- Modelo só do nível diário estadual (HGB com nível em L, médias de 7 e 28 d, fração ENE,
  idade, dia da semana e feriado nacional; dobras mensais jan–ago/2026): o MAE cai de 0,124
  para 0,113 na eólica e de 0,092 para 0,082 na solar, contra a média de 28 d. O ganho é real,
  mas de apenas ~10%.

### Interpretação e decisão

- **Interpretação:** a estrutura do problema é simples. O perfil horário da usina já vem do
  próprio histórico, e o corte é regional e simultâneo. A parte difícil é o **nível** do
  dia-alvo, que depende de vento, sol e carga daqui a 2–4 dias, sinais que o dataset não traz
  como previsão. Sem previsão meteorológica, o teto de ganho sobre o `historico` é limitado.
  Complexidade de pipeline não compra esse sinal.
- **Decisão:** manter o desenho pequeno. Uma linha por usina × slot × dia-alvo, emitida uma
  vez por dia; features indexadas pelo último dia liberado L, nunca por T; poucas features
  com significado físico ou operacional.
- **Regra de decisão, registrada antes dos resultados do modelo:** em cada célula
  (fonte × corte/volume/causa), o modelo só substitui o melhor baseline se vencer nas mesmas
  linhas na média das dobras mensais jan–ago/2026 **e** em pelo menos 6 dos 8 meses. Caso
  contrário, a célula usa o melhor baseline, com `tipo_saida = baseline`. Maio–agosto/2026 já
  foi visto pela receita anterior e aqui é período de desenvolvimento, não teste.

### Alternativas consideradas

- Retomar o pipeline emissão × horizonte: descartado pelo responsável e pelas medições do §2.2
  do prompt, já que as 48 emissões diárias são redundantes.
- LightGBM: adiado. Exige libomp no macOS e teve bug com categóricas no volume. O HGB do
  sklearn basta para começar.

### Implementação e validação

- `RESERVED_TEST_START` passou para 01/09/2026, num commit dedicado. **Atenção na
  integração:** `etapa-3-recomendacao` e `etapa-4-interface` importam a mesma constante.
- `curtamap.previsao.calendario` calcula o corte de publicação com o calendário de feriados
  (todos os tipos, inclusive os do Rio) e oferece a consulta de feriado nacional para a
  feature de carga baixa. `forecasting.nightly_cutoff` passou a delegar a ele, que vira a
  fonte única do corte usada pela interface. Os testes cobrem terça, 19h/19h30, sábado,
  domingo, segunda, o feriado de 07/09/2026 e a falta de cobertura.

### Limitações e incertezas

- Os números acima são exploratórios e usam uma janela de 28 d calculada por `rolling_by` em
  dias com dado. Serão refeitos pelo módulo testado.

### Valor para o usuário e para a apresentação

É a base da narrativa "problema simples na estrutura, difícil no sinal": o corte é regional e
previsível no perfil, e o que falta para acertar o nível do dia é previsão do tempo. Isso
prepara o experimento oráculo (H5), que mede quanto valeria um feed meteorológico.

### Próximos passos

Modelo direto por usina × slot contra os baselines; volume e causa; módulo testado; setembro.

## 2026-09-26 - Nova Etapa 2 (2/n): backtest jan–ago/2026 e decisão por célula

### Contexto e pergunta

O modelo diário por usina × slot supera os baselines nas mesmas linhas? A regra de decisão
foi registrada na entrada anterior e implementada em `curtamap.previsao.relatorio` (commit
`b4aa4a8`) antes de qualquer resultado do backtest oficial.

### Fatos e evidências observados

Backtest de `curtamap.previsao.avaliacao`: 8 dobras mensais, jan–ago/2026, ~3,6 min por dobra
no notebook de 8 GB, com pico de ~1,5 GB. Métricas em
`docs/reports/nova-abordagem/metricas_backtest.csv`; decisão em `decisao_celulas.csv`.

| Célula | Modelo (média) | Melhor baseline (média) | Meses vencidos* | Decisão |
|---|---|---|---|---|
| Corte eólico, AP | 0,788 | `historico` 0,740 | 8/8 | modelo |
| Corte solar, AP | 0,813 | `historico` 0,747 | 8/8 | modelo |
| Volume solar, WAPE meia-hora | 0,851 | `historico` 0,950 | 7/8 | modelo |
| Volume eólico, WAPE meia-hora | 1,083 | `ultimo_valor` 1,097 | 5/8 | baseline |
| Causa eólica, macro-F1 | 0,631 | moda da usina 28 d 0,649 | 2/8 | baseline |
| Causa solar, macro-F1 | 0,504 | moda da usina 28 d 0,462 | 5/8 | baseline |

\* contra o melhor baseline **de cada mês**, que é a leitura operacionalizada no código.

Outros fatos:

- **Brier:** o modelo é melhor que o `historico` na maioria dos meses, mas ligeiramente pior
  na eólica em março (0,105 contra 0,104) e em junho (0,159 contra 0,152).
- **Alerta:**
  - limiar F1-ótimo escolhido fora da amostra em jan–abr: 0,30 na eólica e 0,32 na solar;
  - com ele, em mai–ago (fora da amostra), o recall vai de 0,73 a 0,95 na eólica e de 0,85 a
    0,94 na solar, com precisão de 0,58 a 0,82;
  - em jan–abr, recall e precisão estão dentro da amostra usada na escolha;
  - limiar final, escolhido com jan–ago: 0,346 na eólica e 0,321 na solar.
- **Volume:**
  - o WAPE diário por usina (a métrica de planejamento) também favorece o modelo na solar
    (0,49–0,78 contra 0,59–0,91 do `historico`, fora fevereiro);
  - o preditor "zero" tem WAPE 1,0 por construção e vence **todos** os preditores da eólica em
    fevereiro, março, abril e junho;
  - WAPE e MAE premiam a mediana, que é zero num alvo inflado de zeros, enquanto a
    recomendação consome a média (energia esperada);
  - o viés total do modelo fica entre −26% e +86%. Fevereiro, com pouco corte, é o pior mês
    para todos os preditores baseados em média.
- **Intervalo p10–p90:** a cobertura geral de 0,87 a 0,97 é inflada pelas linhas sem corte.
  Nas meias-horas com corte, ela cai para 0,63–0,79 na eólica e 0,69–0,81 na solar, perto
  dos 80% nominais.

### Interpretação e decisão

- **Ocorrência (a saída principal):** o ganho é claro e estável. O modelo vence nos 16
  meses-fonte, com +0,05 a +0,17 de AP sobre o `historico`, e o maior ganho aparece em
  fevereiro, na mudança de regime.
- **Composição servida** (`SERVING` em `curtamap/previsao/modelo.py`), com proveniência por
  linha em `tipo_saida_volume` e `tipo_saida_causa`:
  - ocorrência: modelo nas duas fontes;
  - volume solar: modelo;
  - volume eólico: `historico`;
  - causa: moda da usina no slot em 28 d, com recurso ao estado em 7 d, nas duas fontes.
- **Desvio registrado antes de setembro:** ao pé da letra, a regra escolheria `ultimo_valor`
  para o volume eólico, porque tem a melhor média. Servimos `historico` porque:
  - a média do `ultimo_valor` só é melhor por causa de fevereiro;
  - o `historico` o vence em 7/8 meses no WAPE de meia-hora e no diário;
  - o `ultimo_valor` subestima a energia em 30–98% em todos os meses, o que quebraria a energia
    em risco da Etapa 3.

  Esse desvio é entre baselines e não infla nenhuma alegação sobre o modelo.
- **Sensibilidade da regra, só para divulgação:** com um baseline fixo (`historico`) em vez do
  melhor de cada mês, o volume eólico venceria em 6/8 meses, com margens de 0,002 a 0,07 fora
  de fevereiro. É um empate técnico. A decisão continua a do código. As outras cinco células
  não mudam entre as duas leituras.
- **Não otimizar o volume eólico para WAPE:** ganhar WAPE ali significaria encolher E[v] na
  direção de zero, o que piora a energia esperada que a recomendação consome.

### Alternativas consideradas

- Reinterpretar a regra depois dos resultados: descartado.
- Iterar livremente sobre volume e causa: limitado a uma ou duas tentativas **na causa**,
  todas listadas e feitas antes de abrir setembro.

**Hipótese da tentativa 1, escrita antes de rodar:** o modelo de causa perde para a moda da
usina porque o `class_weight='balanced'` e as features estaduais diluem o sinal dominante da
usina. Diagnóstico: um HGB só com as três participações da usina no slot em 28 d e **sem**
peso balanceado. Se nem ele empatar com a moda, o limite está no aprendiz ou no alvo, e a
iteração para.

### Implementação e validação

- `apply_serving` com testes: o volume eólico servido é igual a `vol_hist_28d`, a causa
  servida é o argmax das participações e a proveniência sai por linha.
- Cobertura p10–p90 em y > 0 acrescentada às métricas.
- Rótulo semanal de setembro corrigido: o `weekday` do Polars vai de 1 a 7.
- Suíte completa verde, com ruff limpo.

### Limitações e incertezas

- Maio–agosto/2026 já tinha sido visto pela receita anterior. Aqui é desenvolvimento.
- O limiar de alerta e a composição foram escolhidos com jan–ago. Só setembro é teste.
- Os hiperparâmetros foram fixados a priori, sem busca. Pode haver ganho não explorado, e
  também não há sobreajuste de busca.

### Valor para o usuário e para a apresentação

- **Frase do pitch, sustentada por evidência nas mesmas linhas:** "prevemos na véspera, às
  20h, em quais meias-horas de amanhã cada usina será cortada, melhor que a frequência
  histórica da própria usina em 16 de 16 meses-fonte".
- O volume e a causa ganham honestidade, não número. O painel mostra de onde vem cada
  componente.

### Próximos passos

Tentativa 1 de causa; congelar o modelo com manifesto; validar em setembro; H5 (oráculo
meteorológico); relatório e handoff.

## 2026-09-26 - Nova Etapa 2 (3/n): tentativa de causa e congelamento antes de setembro

### Contexto e pergunta

Uma tentativa de melhorar a causa, com hipótese registrada antes, e depois o congelamento da
receita para a validação única em setembro.

### Fatos e evidências observados

Diagnóstico de causa: macro-F1 médio de jan–ago/2026, nas mesmas linhas (cache em
`data/interim/cache_causa.parquet`, script exploratório).

| Variante | Eólica | Solar | Meses > moda (eól./sol.) |
|---|---|---|---|
| Moda da usina 28 d (baseline) | 0,649 | 0,462 | — |
| Atual (13 features, balanceado) | 0,625 | 0,498 | 2 / 5 |
| Só participações da usina, sem peso | 0,638 | 0,422 | 3 / 0 |
| Só participações da usina, balanceado | 0,567 | 0,426 | 1 / 3 |
| 13 features, sem peso | 0,630 | 0,483 | 4 / 6 |

### Interpretação e decisão

- **Eólica:** nem o aprendiz restrito às participações da usina empata com a moda. Pelo
  critério registrado, o limite está no aprendiz ou no alvo, não nas features, e a iteração
  para. **Interpretação:** a causa da ordem é quase uma propriedade da usina e do slot, e a
  moda recente já captura isso.
- **Solar:** a variante sem peso venceria em 6/8 meses, mas foi a melhor de 4 variantes nas
  mesmas dobras. Adotá-la seria viés de seleção, com margem de 0,02. **Decisão:** manter a moda
  da usina, como a regra já decidia, e registrar a variante como candidata para uma futura
  validação independente.
- **Congelamento:**
  - modelo `diario_hgb_v1_2026-08-30`, treinado com rótulos até 30/08/2026, o último dia
    liberado na emissão que prevê 01/09;
  - 2,71 M linhas eólicas e 1,31 M solares;
  - limiar de alerta de 0,346 na eólica e 0,321 na solar;
  - SHA-256 `6340240d…` e commit da receita `e89be0f`;
  - manifesto em `docs/reports/nova-abordagem/modelo-congelado.json`.

### Alternativas consideradas

Mais tentativas de causa ou de volume eólico: descartadas. A primeira tentativa respondeu à
pergunta, e novas rodadas só aumentariam o risco de sobreajuste às dobras.

### Implementação e validação

- `treinar.py` grava o manifesto.
- O calendário aceita `CURTAMAP_CALENDAR_PATH`, para o container.
- Suíte verde.

### Limitações e incertezas

- A causa servida é um baseline. O pitch não deve atribuir a causa ao modelo.
- A reprodução histórica e a validação de setembro ainda não foram rodadas.

### Valor para o usuário e para a apresentação

- Mostra disciplina: a regra decide, a tentativa é declarada e o congelamento é verificável
  por hash.
- Sustenta a narrativa: "o modelo onde ele ganha e o baseline honesto onde não ganha".

### Próximos passos

1. Baixar setembro.
2. Prever sem rótulo.
3. Avaliar por semana.

## 2026-09-26 - Nova Etapa 2 (4/n): setembro, reprodução para o dashboard e oráculo meteorológico

### Contexto e pergunta

- As escolhas congeladas se sustentam fora da amostra?
- Quanto valeria uma previsão meteorológica?
- Além disso, entregar o recorte histórico para o dashboard.

### Fatos e evidências observados

- **Setembro de 2026**, a validação independente, aberta uma única vez depois do commit
  `7b64b46`:
  - dados baixados às 06:35 UTC de 26/09, com `Last-Modified` de 25/09 às 22h UTC, cobrindo
    01 a 24/09 (manifesto em `docs/reports/nova-abordagem/setembro/`);
  - previsões sem rótulo gravadas antes da avaliação (SHA-256 `b1c8ed21…`);
  - corte: AP de 0,921 contra 0,899 do `historico` na eólica (vence 3/4 semanas) e de 0,907
    contra 0,867 na solar (4/4);
  - volume solar: WAPE 0,607 contra 0,652 e WAPE diário 0,517 contra 0,565;
  - causa: a moda da usina (servida) teve 0,839 contra 0,765 do modelo na eólica e 0,501
    contra 0,447 na solar;
  - alerta com o limiar congelado: recall de 0,94 e 0,90, precisão de 0,82 e 0,81.
- **Reprodução**, em `data/interim/previsao/reproducao_2026-08-03_2026-08-30.parquet`:
  - 28 emissões às 20h e 315.072 linhas no contrato, com `observado_*` ao lado;
  - modelo treinado com rótulos até 30/07;
  - AP de 0,920 contra 0,904 na eólica e de 0,904 contra 0,865 na solar.
- **H5, oráculo em mai–ago:**
  - clima verificado do estado no dia-alvo: AP eólica de 0,826 para 0,872, WAPE diário eólico
    de 0,711 para 0,540, AP solar de 0,860 para 0,869;
  - clima de L, que é legítimo: sem ganho.

### Interpretação e decisão

- **Fato:** setembro confirmou as decisões congeladas. **Interpretação:** o ganho da
  ocorrência é robusto, mas setembro teve prevalência parecida com agosto e não testou uma
  mudança de regime.
- **Interpretação:** o gargalo do volume eólico é meteorológico. O H5 quantifica o valor de um
  feed de previsão de vento como teto, não como garantia.
- **Decisão:** o clima de L não entra no produto, porque não teve ganho.

### Alternativas consideradas

Usar setembro para ajustar a receita: proibido pelo protocolo e não feito.

### Implementação e validação

- Módulos `setembro`, `reproducao` e `produto`, todos com testes.
- Script do H5 versionado em `scripts/experimentos/oraculo_h5.py`.
- Relatório completo em `docs/reports/nova-abordagem/README.md`.
- Handoff em `docs/handoffs/etapa-2-nova-abordagem-handoff.md`.

### Limitações e incertezas

- Setembro tem só 24 dias.
- O H5 usa clima verificado e médio por estado. Uma previsão real teria erro, e a
  granularidade por usina poderia mudar o número.

### Valor para o usuário e para a apresentação

- **Demonstração:** 4 semanas de emissões diárias com a verdade ao lado.
- **Validação independente:** setembro, publicado depois do snapshot.
- **"Por que agora" e evolução do produto:** o próximo ganho vem de previsão meteorológica,
  não de mais complexidade.

### Próximos passos (domingo)

1. Integrar com as Etapas 3 e 4 seguindo o handoff: trava de setembro, 92 dias de histórico
   e proveniência por componente.
2. Containerizar com `configs/`, `models/` e `data/raw/`.

## 2026-09-26 - Nova Etapa 2 (5/n): correções da revisão final

### Contexto e pergunta

A revisão final encontrou um número errado no diário e um defeito de serviço.

### Fatos e evidências observados

- **Correção da entrada 2/n:** ela diz "+0,05 a +0,17 de AP sobre o `historico`". O
  `metricas_backtest.csv` mostra ganhos mensais de **+0,009 a +0,173**:
  - na eólica: +0,074, +0,173, +0,031, +0,027, +0,035, +0,020, +0,009 e +0,018;
  - na solar: de +0,035 a +0,147.

  O ganho médio é de +0,048 na eólica e de +0,066 na solar. A frase "vence em 16 de 16
  meses-fonte" continua correta. Na eólica, porém, a margem fica entre +0,01 e +0,035 em 6 dos
  8 meses. **No pitch, use o ganho médio, não a faixa.**
- Na reprodução de agosto, o volume eólico servido (média de 28 d) ficava acima do p90 do
  modelo em 0,69% das linhas e abaixo do p10 em 0,15%.

### Interpretação e decisão

- **Decisão:** alargar a banda para conter a média servida. É um ajuste de serviço
  pós-congelamento. O artefato congelado e as métricas de setembro não mudam, porque
  `setembro.predict` usa o modelo sem o serviço.
- **Handoff:** a frase sobre `t0` de manhã foi corrigida. Com `nightly_cutoff`, a idade 1 só
  aparece se `t0` for o próprio instante da emissão.
- **Relatório:**
  - a divulgação de que o `SERVING` foi escolhido com dados que incluem agosto foi
    acrescentada;
  - a afirmação "capturam o que há de previsível" foi marcada como interpretação;
  - o texto agora diferencia o commit do código (`e89be0f`) do commit do congelamento
    documental (`7b64b46`).

### Implementação e validação

- Commit `04113b8`, com teste de que a média servida fica dentro da banda.
- Suíte verde, com ruff limpo.
- A reprodução de agosto será regenerada com o serviço corrigido.

### Limitações e próximos passos

Nenhuma decisão de modelo mudou. Próximo passo: a integração de domingo.

## 2026-09-26 - Etapa 4 (nova abordagem): interface de decisão D+1 e preparação do deploy

### Contexto e pergunta

A interface anterior (`etapa-4-interface`) estava desatualizada em relação ao `main`: ela
assumia o teste reservado em maio e 28 dias de histórico, e não sabia do modelo diário da nova
Etapa 2. O responsável pediu uma reconstrução do zero, na branch
`etapa-4-interface-nova-abordagem`. As perguntas foram:

- como abrir o dashboard com a decisão do gerador (quais usinas, quando, quanto, por quê e o
  que fazer), e não com métricas do modelo;
- como fazer isso sem depender de qual preditor gerou a previsão;
- como deixar o deploy da AWS pronto sem passos ocultos.

### Fatos e evidências observados

- **Prazo do teste reservado:** `RESERVED_TEST_START` no `main` é **01/09/2026**, não 01/05
  como dizia o prompt da etapa (mudança da nova Etapa 2, commit `8633122`). A interface usa a
  constante, então a última emissão oferecida é 31/08/2026 00:00, com as 24 h terminando
  antes de setembro.
- **Download no Windows:** o `download_data` terminava sem baixar nada nem avisar. O `gdown`
  lista os caminhos com `\`, e o `PurePosixPath` não os separava. Corrigido com teste (commit
  `8b96281`).
- **Desempenho com dados reais** (t0 = 25/08/2026 00:00, corte em 24/08):
  - leitura de 92 dias (1.028.304 linhas) em 0,4 s;
  - previsão em 1,1 s com o modelo diário e 0,2 s com o baseline (11.328 linhas, 236 usinas);
  - 6 meses de histórico observado (2.021.712 linhas, ~196 MB) em 0,5 s;
  - pico de memória do processo Streamlit de ~2,1 GB com o modelo e a visão tática de 6 meses.
- **Emissão de 31/08/2026 00:00** (dados liberados até 28/08):
  - com o modelo diário (treinado localmente com os limiares `final_jan_ago`): 231 de 236
    usinas em alerta e 163.653 MWh de energia em risco nas janelas em alerta. Maior risco:
    CONJ. CAJU (RN), 5.953 MWh a partir de 00:00, causa provável CNF, p(corte) média de 86%;
  - com o baseline: 224 de 236 usinas em alerta e 100.175 MWh. A mesma usina lidera, com
    4.853 MWh.
  - Esses números **não foram comparados com o observado**: são só o que a tela mostra.
- **Fusos de `gerado_em` diferentes:** o baseline grava hora local sem fuso e o modelo diário,
  UTC sem fuso (`datetime.now(UTC)` em `previsao/modelo.py`). O contrato fala em horário de
  Brasília. Num contêiner na AWS, que roda em UTC, o baseline também passaria a gravar UTC.
- **Proveniência por componente** na emissão de 31/08 (modelo): volume de 7.344 janelas vem
  do baseline histórico de 28 dias e de 3.984 do modelo; a causa vem sempre de baseline (usina
  em 28 dias ou estado em 7 dias). Isso bate com o `SERVING` do handoff.
- O ambiente de desenvolvimento não tinha Docker, WSL, Node nem `uv`. Instalei `uv` (pip,
  escopo do usuário) e Node 24 LTS portátil com checagem de SHA-256, mais `pnpm` 10. Docker
  exige administrador e ficou de fora.
- A lista de serviços confirmados em `aws-environment.md` **não inclui Elastic Load
  Balancing**.

### Interpretação e decisão

- **Separação estrita entre cálculo e desenho.**
  - `src/curtamap/painel/` (sem Streamlit, com testes) calcula:
    - limites de emissão;
    - ranking, filtros e perfil das 48 janelas;
    - proveniência;
    - perdas históricas;
    - totais e resumo em texto;
    - rótulos e formatos numéricos.
  - `src/curtamap/ui/` só desenha.
  - O `app.py` configura a página, calcula o contexto comum (emissão e previsão em cache) e
    registra as três telas com `st.navigation`.
- **Preditor:** a interface chama `product_predictor()` (handoff da nova Etapa 2): usa o
  modelo mais recente em `models/previsao/` ou, sem artefato, o baseline. Ela não sabe qual
  dos dois veio. O histórico carregado é `HISTORY_DAYS` = 92 dias.
- **Selo em todas as telas:** amarelo para "preditor provisório (baseline)" e azul para
  "modelo treinado", com a proveniência por componente.
- **Regras de exibição que viraram código testado:**
  - Energia em risco = soma da energia esperada das janelas em alerta, a mesma regra dos
    episódios da Etapa 3.
  - Alerta com volume desconhecido deixa a energia da usina desconhecida. Usina sem nenhuma
    janela prevista fica "sem evidência", com o motivo, e fora das somas. Usina sem alerta,
    mas com previsão, tem zero **conhecido**.
  - Causa provável = a causa com mais energia nas janelas em alerta, com uma marca de "causa
    mista" quando há mais de uma. Não é eleição de causa dominante para a recomendação, que
    segue as regras da Etapa 3.
  - Confiança = p(corte) médio nas janelas em alerta. Com o baseline, a coluna é omitida,
    porque 0 ou 1 não é confiança.
  - Visão tática: só meias-horas com limitação; volume inválido é contado à parte; períodos
    cortados pela janela ficam translúcidos; recortes com muitos grupos juntam o resto em
    "Outros", pelo total do recorte inteiro, para que a cor siga o grupo.
- **Fuso de `gerado_em`:** a interface passa `generated_at` em horário de Brasília aos dois
  preditores. `modelo.py` e `forecasting.py` são do responsável e não foram alterados.
- **Recomendações:** até a Etapa 3 chegar ao `main`, o painel de ações usa três linhas
  escritas à mão, `simulado` no contrato, com usinas fictícias `EXEMPLO-*` que nunca casam
  com uma usina real e um aviso "EXEMPLO SIMULADO" na tela. A coluna "Ação sugerida" do
  ranking mostra "aguarda Etapa 3". Quando o módulo real chegar, só
  `ui/dados.recommendations_for` muda, para `build_recommendations(forecast)`.
- **Deploy:**
  - Dockerfile com `uv` e o lock congelado;
  - dados e modelo baixados do S3 na inicialização (`curtamap.s3_sync`);
  - CDK em Python, no extra `infra`, com duas pilhas. As restrições de IAM são testadas no
    template;
  - variante sem ALB (`-c semAlb=true`), porque o ELB não está confirmado.

### Alternativas consideradas

- **Reaproveitar a branch `etapa-4-interface`:** descartada a pedido do responsável.
- **`url_path` na página padrão:** o Streamlit ignora; a página inicial fica na raiz.
- **Juntar as recomendações de exemplo às usinas reais do ranking:** descartada. Números
  simulados ao lado de usinas reais pareceriam reais.
- **Script shell de inicialização:** trocado por um `CMD` direto. Com `autocrlf=true`, um
  `.sh` extraído no Windows chegaria à imagem com CRLF.
- **`cdk bootstrap` com o sintetizador padrão:** descartado. O bootstrap cria papéis passados
  ao CloudFormation, o que o ambiente não permite. O `BootstraplessSynthesizer` exige
  pilhas sem assets, e a imagem vai ao ECR pelo Docker.
- **`Vpc.from_lookup`:** descartado, porque exigiria credenciais no `synth`. A VPC existente
  entra por contexto, e sem ela a pilha cria uma VPC pública sem NAT.
- **Camada LLM do assistente:** adiada. O resumo em texto é determinístico e testado; um
  provedor (Bedrock ou NIM) ficaria atrás de uma interface, desligado por padrão, e ainda não
  foi implementado.

### Implementação e validação

- TDD em todos os módulos de `painel/`, em `s3_sync` e no download do Windows: os testes
  foram escritos antes, com falha de coleta ou de asserção confirmada. Os casos cobrem:
  - limites de emissão;
  - mesmo `id_ons` em fontes diferentes;
  - usina sem evidência;
  - alerta com volume nulo;
  - atributos nulos nos filtros;
  - período reservado;
  - períodos parciais;
  - chaves S3 inseguras.
- `tests/test_app.py` usa o `AppTest` do Streamlit:
  - sem dados, a tela mostra instruções e nenhuma métrica;
  - com dados reais, cada tela renderiza sem exceção e com o selo;
  - a Operação abre com "Usinas em risco" e "Energia em risco".
- `tests/test_infra.py` (precisa do Node) verifica:
  - nenhuma Lambda ou recurso customizado;
  - todos os papéis assumidos só por `ecs-tasks`;
  - porta 8501, health check `/_stcore/health`, bucket privado e logs de 7 dias;
  - nenhum parâmetro de bootstrap;
  - região fora do hackathon recusada;
  - VPC existente sem lookup;
  - variante sem ALB.
- `pnpm dlx aws-cdk@2 synth` roda sem credenciais, com e sem `semAlb`. Templates: 18 kB (app)
  e 4 kB (base), abaixo do limite de 51.200 bytes para deploy sem bucket.
- Verificação visual com o Streamlit rodando de verdade, capturada com o Playwright (Edge
  headless), com o modelo (porta 8501) e sem ele (porta 8502, `CURTAMAP_MODEL_DIR` vazio).
  As capturas mostraram três problemas, todos corrigidos:
  - legenda sobre o título;
  - datas em inglês;
  - "Page not found" na URL da página padrão.
- **Fluxo da demo:**
  1. A barra lateral escolhe o dia e a hora de t0 (padrão 31/08/2026 00:00).
  2. O selo diz modelo ou baseline e até quando os dados estavam liberados.
  3. Os quatro números do topo: usinas em risco, energia em risco, primeiro alerta e usinas
     sem evidência.
  4. O "Resumo do dia" em texto.
  5. O ranking, que pode ser filtrado por fonte, UF e subsistema.
  6. O perfil das 48 janelas da usina escolhida: energia com p10–p90 e p(corte) com o limiar,
     em gráficos separados.
  7. As ações, que por enquanto são o exemplo simulado.
  8. A Visão tática: 6 meses de perdas observadas por causa.
  9. A tela de Metodologia e limites.
- Suíte completa: **277 testes aprovados** com `PYTHONUTF8=1` e Node no PATH. Sem o Node, os
  8 testes de infraestrutura são pulados. Sem `PYTHONUTF8=1`, `test_feature_inventory` falha
  por encoding (defeito anterior, já registrado). `ruff check` e `ruff format --check` estão
  limpos.

### Limitações e incertezas

- `docker build` e `docker run` **não foram executados** (sem Docker na máquina). Há testes
  estáticos do Dockerfile, e o `CMD` foi exercitado fora do contêiner.
- `cdk deploy` sem bootstrap e a criação de VPC e ALB na conta do evento são **hipóteses**.
  `docs/deploy.md` traz um plano B para cada caso.
- A demo local sem rede não foi testada com o Wi-Fi desligado.
- Em agosto de 2026, quase todas as usinas ficam em alerta (231 de 236 na emissão de 31/08).
  **Interpretação:** em mês de corte generalizado, o status "em risco" discrimina pouco e o
  que ordena a decisão é a energia e a janela. Não foi medido se a ordenação por energia
  prevista acerta a ordem observada.
- O modelo local foi treinado nesta máquina. O SHA-256 não foi comparado com o do manifesto
  versionado, e o HGB pode variar no último dígito.
- A agregação tática é mínima; a da Etapa 3 (`summarize_history`) ainda recusa datas a
  partir de maio e precisará seguir a nova trava.

### Valor para o usuário e para a apresentação

- **Solução/demonstração:** o gerador abre a tela e vê primeiro a decisão ("231 usinas em
  alerta; a de maior risco é a CONJ. CAJU, a partir de 00:00, por CNF"), com o caminho até a
  proveniência a um clique.
- **Credibilidade:** o selo e a tela de metodologia deixam explícito o que é modelo, o que é
  baseline e o que é exemplo simulado. Nulo nunca vira zero.
- **Implantação:** a infraestrutura respeita as restrições de IAM da conta por construção, com
  testes, e existe uma demo local que não depende da AWS.

### Próximos passos

1. **Responsável:**
   - revisar o PR da branch `etapa-4-interface-nova-abordagem`;
   - decidir se `generated_at` entra no protocolo `Predictor` e se o modelo e o baseline devem
     gravar `gerado_em` em horário de Brasília.
2. **Etapa 3:** ao integrar, trocar `recommendations_for` por `build_recommendations` e
   remover o aviso de exemplo; atualizar a trava de maio em `summarize_history`.
3. **Sábado:** seguir `docs/deploy.md`, começando por `docker build` e `docker run`.
4. **Sexta:** ensaiar a demo com a rede desligada.
5. **Opcional:** provedor LLM atrás de interface, desligado por padrão, que só reescreve o
   resumo determinístico.
