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

## 2026-09-23 - Etapa 2B: populações exatas de treino e validação da eólica

### Contexto e pergunta

O piloto eólico validou somente contratos técnicos, com `head(2.000.000)` inelegível.
Antes de decidir qualquer contingência de treino era preciso saber, com os filtros reais,
quantas linhas entram em cada rodada V1–V4, segmento interno e tarefa, e distinguir a
população usada no ajuste da população avaliada na validação externa.

A retomada conferiu HEAD `7f56c88`, `main` em `48f9923`, árvore limpa, ausência de
processos experimentais e `end.json` em todos os passos. Nada foi regenerado ou reverificado.

### Implementação e validação do medidor

O módulo `curtamap.experimental.population_measurement`, desenvolvido em worktree
isolado, foi revisado: reutiliza `_range`, `_task_filter`, `_validation_filter` e
`internal_boundaries`; os limites de initial/tuning/refit/calibration coincidem com
`campaign.run_campaign_round`; a validação usa só o filtro de painel aberto, sem
`eligible_history`. Não foi encontrado defeito técnico, e nenhuma correção foi feita.
Um smoke do CLI em três partições reais (01–03/01/2025, saída no scratchpad da sessão)
confirmou o caminho `main()`, calendário com hash e commit de medição.

Verificações: no worktree, passo `medidor-populacoes-pytest-worktree-001` com **232
aprovados, 1 skip** (`test_notebook`: Parquet ausentes em `data/raw` do worktree),
Ruff check/format e `git diff --check` aprovados. Commit `cbb7605`, integrado por
`git merge --no-ff` em `ea88fe7`. No resultado integrado, passo
`medidor-populacoes-pytest-merge-001`: **233 aprovados, 81 warnings**, exit 0; Ruff aprovado.

### Execução e fatos observados

Passo `populacoes-noturno_dia_util-eolica-001`, commit `ea88fe7`, árvore limpa:
exit 0, **150,9 s**, stderr vazio, pico por processo **821.321.728 bytes (0,76 GiB)**.
Relatório: `execucao/medicoes/populacoes-noturno_dia_util-eolica-001.json` e
`.progress.jsonl` (942 eventos `partition_completed` e evento `completed`).

Conferência cruzada com a verificação aprovada: 96 de 96 checagens passaram:
942 partições; 339.738.048 linhas; somente 01/10/2023 sem partição; primeiro t0 em
02/10/2023 19h30; 180 entidades; 48 horizontes com 7.077.876 linhas cada; `prediction_rows`
iguais às contagens de validação da verificação; U/K/C idênticos; t0 máximo de V4 em
30/04/2026 00h; refit ≥ initial em todas as células; calibração de volume e causa `used=false`.

Linhas de ajuste (`fonte+id_ons+t0+horizonte`, não alvos `tau` distintos). Ocorrência
principal e secundária têm a mesma contagem em todos os segmentos:

| Rodada | Segmento | Ocorrências (cada) | Volume condicional | Causa |
|---|---|---:|---:|---:|
| V1 | initial | 132.692.040 | 18.803.053 | 27.728.833 |
| V1 | tuning | 8.480.256 | 1.537.899 | 2.154.617 |
| V1 | refit | 142.386.336 | 20.818.621 | 30.533.665 |
| V1 | calibration | 9.518.400 | não usada | não usada |
| V2 | initial | 174.755.520 | 28.257.206 | 40.046.603 |
| V2 | tuning | 9.066.528 | 1.077.117 | 1.310.236 |
| V2 | refit | 185.795.136 | 30.160.873 | 42.312.202 |
| V2 | calibration | 9.527.424 | não usada | não usada |
| V3 | initial | 218.732.808 | 39.295.138 | 53.696.964 |
| V3 | tuning | 9.348.816 | 3.762.084 | 4.454.373 |
| V3 | refit | 228.613.584 | 43.239.394 | 58.360.175 |
| V3 | calibration | 9.532.224 | não usada | não usada |
| V4 | initial | 262.143.984 | 60.746.233 | 78.160.184 |
| V4 | tuning | 9.406.320 | 4.256.360 | 4.725.090 |
| V4 | refit | 272.078.832 | 65.106.121 | 83.010.440 |
| V4 | calibration | 9.587.424 | não usada | não usada |

O primeiro t0 elegível de treino é 28/10/2023 23h30 em todas as rodadas. Validação
externa (painel aberto): linhas previstas V1 42.851.184, V2 43.830.768, V3 43.109.184,
V4 42.194.016; suporte potencial de ocorrência e volume 42.687.648, 43.503.696, 42.945.648
e 42.030.480 (diferença = linhas sem alvo); suporte potencial de causa 10.205.443,
20.290.779, 22.867.317 e 13.743.836; linhas com histórico elegível para ocorrência
42.024.336, 43.174.032, 42.825.072 e 41.473.584. A validação não é filtrada por elegibilidade:
as inelegíveis recebem fallback e continuam avaliadas.

Prevalência natural de `corte_positivo` no refit: 0,146 (V1), 0,162 (V2), 0,189 (V3),
0,239 (V4); no tuning varia de 0,119 (V2) a 0,453 (V4) e na calibração de 0,163 a 0,475.
Os segmentos internos curtos têm prevalências distintas do histórico longo.

### Interpretação: projeção de memória

Projeção com os coeficientes históricos do handoff da sessão 01 (estimativas, não
medidas nesta execução): 84 B/linha de trecho, 148 B/linha de CSR e 556 B/linha no pico
de `fit_transform`. Modelo: `_split` mantém initial, tuning, refit e calibração da tarefa
juntos (84 B × soma); a esse residente soma-se o maior entre o ajuste inicial
(556 × initial + 148 × tuning, porque o LightGBM recebe o eval) e o reajuste (556 × refit).
Picos de ajustes diferentes não se somam. O acúmulo dos modelos finais é pequeno: os oito
modelos do piloto somaram cerca de 3,7 MB em disco.

| Rodada | Ocorrência (cada) | Volume | Causa |
|---|---:|---:|---:|
| V1 | ≈96,7 GiB | ≈14,0 GiB | ≈20,5 GiB |
| V2 | ≈125,9 GiB | ≈20,3 GiB | ≈28,5 GiB |
| V3 | ≈154,9 GiB | ≈29,1 GiB | ≈39,3 GiB |
| V4 | ≈184,2 GiB | ≈43,9 GiB | ≈56,0 GiB |

Só o residente das ocorrências de V4 é ≈43,3 GiB. Mesmo desconsiderando o pico de
`fit_transform`, o treino completo não cabe na máquina de 32 GB nem no orçamento de
referência de ≈22 GiB do §12.1. Isso confirma, agora com contagens exatas, a inviabilidade
apontada pelo handoff. A decisão de contingência é metodológica e foi levada ao responsável
em uma pergunta consolidada; nenhuma amostragem foi implementada.

### Alternativas consideradas

Ler os dados preguiçosamente já está implementado e não reduz o ajuste do estimador.
Reduzir cópias (liberar initial antes do refit, não manter os quatro splits) diminui o
residente, mas o pico de 556 B/linha do refit de V4 (≈141 GiB) continua inviável.
Remover rodadas ou usar só períodos recentes é proibido pelo §12.2.

### Limitações

Os coeficientes vêm de medições anteriores do executor e podem variar por família e
tarefa; a projeção é ordem de grandeza. A fase de métricas da validação, que relê as
previsões de um modelo por vez, não foi medida. Contagens são linhas, não observações
independentes. O medidor só cobre o cenário principal eólico.

### Valor e próximos passos

As contagens sustentam na apresentação o tamanho real do problema (centenas de milhões
de exemplos por rodada) e a necessidade de uma contingência registrada. Próximos passos:
resposta explícita do responsável; enquanto isso, gerar e verificar solar principal,
eólica +24h e solar +24h, um processo pesado por vez. Teste reservado, vencedor, push e
merge em main continuam bloqueados.

## 2026-09-24 - Etapa 2B: correção e retomada da fila sequencial

### Contexto e pergunta

Após `main-eolica-v1-002` terminar, a fila operacional deveria iniciar as demais rodadas
sem supervisão, mas nenhum treino permaneceu ativo. A pergunta foi se o problema estava
nos modelos ou no encadeamento e como retomar sem repetir a V1, que consumiu 3,8 horas.

### Fatos e evidências observados

O `fila.log` registrou a V1 como `ok` às 22h53 de 23/09 e tentou iniciar sete campanhas
principais e duas gerações de features; todas terminaram em aproximadamente 20 segundos,
sem criar diretório de passo. Os nove arquivos `*.runner.stderr.log` tinham o mesmo erro
de binding: `run-step.ps1` recebeu `-run-id` ou `-scenario` como se fossem parâmetros
próprios. Apesar disso, a versão anterior percorreu os demais itens e escreveu `fila
concluída`, enquanto o status mostrava 19 passos pendentes.

### Interpretação e decisão

O fato observado é compatível com perda do limite do valor de `-Arguments` quando
`Start-Process -ArgumentList` recompôs a linha de comando. A decisão foi substituir essa
fronteira por `System.Diagnostics.ProcessStartInfo.ArgumentList`, que preserva cada
argumento, e fazer a fila encerrar com erro no primeiro passo inválido. A V1 permanece
fora da lista de novos passos: seu artefato é apenas validado como dependência concluída.

### Alternativas consideradas

Escapar mais aspas na string de `Start-Process` foi descartado por continuar dependente
das regras de remontagem de linha de comando do Windows. Reexecutar ou renomear a V1 foi
descartado porque seu `end.json` e manifesto já estavam completos. Também não se removeu
nenhum artefato: as tentativas do lançador falharam antes da criação dos passos pendentes.

### Implementação e validação

Foram alterados os scripts operacionais `execucao/fila/fila-2b.ps1` e
`execucao/status-fila.ps1` no volume dedicado. Além da passagem estruturada de argumentos,
a fila agora rejeita passo existente que não esteja `ok`, interrompe ao encontrar
dependência inválida e só registra `fila concluída com sucesso` após todos os passos. O
status considera o evento de ciclo mais recente e não uma conclusão antiga no arquivo.

Os dois scripts passaram no parser do PowerShell. Um probe isolado confirmou, byte a byte,
a preservação de um argumento composto de 215 caracteres com espaços, aspas e glob. Na
retomada às 01h57, a fila registrou `main-eolica-v1-002 terminou -> ok` e iniciou diretamente
`main-eolica-v2-001`. O novo `start.json` registra commit `560ae70`, árvore limpa e o comando
esperado; os processos `run-step`, `uv`, `curtamap-experiment` e Python permaneceram ativos,
sem conteúdo no stderr da fila.

### Limitações e incertezas

A validação confirma o lançador e o início da V2, não a conclusão do treino longo nem as
métricas do modelo. A fila continua sujeita a falhas reais de dados, modelo, disco ou
memória; nesses casos agora deve parar no primeiro erro, preservando evidência para retomada.

### Valor para o usuário e para a apresentação

A correção evita repetir uma execução cara já concluída e reduz o risco de horas perdidas
com uma fila que aparenta sucesso. O registro também separa claramente uma falha operacional
do lançador de uma falha metodológica ou dos modelos.

### Próximos passos

Monitorar `main-eolica-v2-001` pelo `status-fila.ps1`; ao término, confirmar a transição
para V3 e, ao fim da sequência, auditar manifests, métricas e uso de recursos de cada passo.

### Correção subsequente da retomada

A checagem posterior corrigiu a conclusão provisória acima: `main-eolica-v2-001` chegou ao
CLI, mas o preflight encerrou antes do treino porque o worktree estava na branch
`execucao/fila-2b`, enquanto o código exige literalmente `etapa-2-experimental`. O passo
durou 30,4 segundos, teve exit 1 e não produziu manifesto; V3 não foi iniciada, confirmando
o novo comportamento fail-fast.

O `start.json` da V1 mostrou que ela havia sido executada no workspace principal, na branch
exigida, e não no worktree inicialmente configurado para a fila. Como ambos apontavam para
o mesmo commit `560ae70`, o worktree de execução foi associado à branch
`etapa-2-experimental` com a opção explícita do Git para branch compartilhada entre
worktrees; ele permaneceu limpo e no mesmo commit. Para preservar a tentativa falha como
evidência, a retomada passou a usar o novo ID `main-eolica-v2-002`, e as sensibilidades de
V2 foram atualizadas implicitamente pelo mapa de dependências para consumir esse novo run.

O preflight isolado passou (`ready=true`) antes da segunda retomada. `main-eolica-v2-002`
ultrapassou a janela da falha anterior, permaneceu com a cadeia completa de processos ativa,
stderr vazio e amostra de aproximadamente 10,3 GB de working set da árvore às 02h00. O
status também passou a consultar o PID gravado no evento de início, pois a inicialização
durável por `EncodedCommand` não expõe o nome do script na linha de comando do processo.

Limitação operacional: enquanto dois worktrees compartilham a mesma branch, não se deve
alterar o HEAD por commit, merge ou switch durante os treinos. O workspace dedicado é o
executor congelado; qualquer evolução de código deve aguardar a fila ou usar outra branch.


## 2026-09-24 - Reduza o custo das métricas da validação completa

### Contexto e pergunta

O responsável informou 3,8 horas para a V1 eólica e pediu uma otimização pontual para
viabilizar as rodadas restantes e oito sensibilidades. Não foi alterada a população de
validação, a metodologia, os modelos, os limiares ou as previsões.

### Fatos e evidências observados

`cause_metrics` chamava confusion_matrix uma vez, recall_score e f1_score por classe e
f1_score novamente para a macro: até oito chamadas sobre os mesmos vetores de texto por
recorte. Cada chamada repetia validação, identificação de classes e contagens. Baselines
copiavam também colunas sem uso ao materializar recortes.

Medição única local (seed 42, 500.000 exemplos sintéticos; igualdade exata dos dicionários):
causa 5,589139 s antes / 0,091910 s depois; ocorrência 0,235608 s / 0,161516 s.
Confirmação em 500.000 linhas reais válidas de
`Y:/CurtaMap Etapa 2B/experimentos/main-eolica-v1-002/predictions/eolica-V1-causa-lightgbm.parquet`:
6,772911 s / 0,037027 s, igualdade exata. Leitura do Parquet fora do cronômetro;
amostra obtida por select(true_cause, prediction), filtro REL/CNF/ENE e head(500000).
Estes são tempos das funções, não ganhos medidos na rodada completa.

### Interpretação e decisão

Calcular uma única tabela de contagens inteiras de causa, derivando suporte, recall e F1.
Uma quarta posição interna preserva falsos positivos/negativos de classes externas, sem
incluí-las na matriz pública. Entradas externas ao domínio mantêm validação pelo sklearn.
Para ocorrência binária, contar TP/FP/FN/TN diretamente e dispensar unique do alvo;
AP, Brier e bins continuam com o mesmo cálculo. Selecionar apenas alvo, previsão e colunas
dos recortes antes de copiá-los. A mesma implementação serve campanhas e sensibilidades.

### Alternativas consideradas

Reduzir a validação ou remover recortes alteraria a avaliação e foi descartado. Reescrever
AP, agregar somas em blocos ou alterar inferência adicionaria risco numérico e foi adiado.
Priorizou-se remover trabalho redundante, com equivalência exata e mudança pequena.

### Implementação e validação

33 testes direcionados passaram (métricas, paridade de métricas, campanha e paridade de
campanha/sensibilidade); Ruff check e format --check passaram nos cinco arquivos Python.
Os testes estruturais falharam antes da mudança pela repetição de contagens e cópia de
colunas desnecessárias. `tests/reference_metrics_stage2b.py` congela o código anterior;
o oráculo da campanha usa explicitamente essas funções, evitando comparar código novo
consigo mesmo. Paridade inclui classes ausentes, classes externas, entradas vazias,
probabilidades empatadas e limites 0/1. Avisos de depreciação já existentes permanecem.

A fila executa V2 no worktree dedicado; os dois worktrees inicialmente compartilhavam a
branch. O workspace principal foi separado em `codex/otimize-metricas-validacao`, mantendo
HEAD do executor intacto. `scripts/apply-queued-code.ps1` permite fast-forward solicitado
somente antes do próximo passo, verifica repositório, HEAD esperado e árvore limpa e
consome a solicitação. Teste em repositório temporário confirmou bloqueio de árvore suja,
fast-forward, consumo do marcador e no-op sem solicitação. O lançador operacional receberá
esse hook antes de gravar start.json, para registrar o commit realmente usado. A ativação
fica pendente até a V2 terminar; não se interrompe nem se repete essa rodada.

### Limitações, valor e próximos passos

A aceleração remove um custo repetido em milhões de linhas e conserva os artefatos usados
na apresentação. Não garante término até sexta: inferência, I/O, AP e geração dos datasets
de sensibilidade continuam custando tempo. Ganhos totais precisam ser observados no próximo
run completo. Confirmar o marcador aplicado e code_commit no próximo start.json e comparar
sua duração, sem reexecutar uma rodada apenas para benchmark. O diário já tinha uma entrada
não commitada de outra sessão; ela foi preservada fora deste commit.


## 2026-09-24 - Reinicie V2 com as métricas otimizadas e libere a fila

### Contexto e decisão

O responsável solicitou explicitamente cancelar a V2 ainda em andamento, reiniciá-la com
a otimização c73302e e remover o marcador PARAR para seguir automaticamente até o fim da
fila. A decisão substitui a ativação originalmente planejada apenas entre V2 e V3.

### Fatos observados e implementação

Às 02h22, a árvore da fila PID 5372 foi encerrada, incluindo o runner, uv e Python da
`main-eolica-v2-002`. A tentativa foi preservada com artefatos parciais, INTERRUPCAO.txt
e end.json com exit_code=1 e interrupted_by_user=true; não deve ser usada como run completo.
O executor recebeu fast-forward de 560ae70 para c73302e, com árvore limpa e solicitação
de atualização consumida. O arquivo `execucao/fila/PARAR` foi removido.

O lançador passou a usar `main-eolica-v2-003`, atualizando pelo mesmo mapa a dependência
da sensibilidade de V2. V1 permanece concluída, sem repetição. O status inclui a tentativa
nova e identifica a anterior como CANCEL. Foram preservados backups dos scripts operacionais.

Às 02h23min04s (America/Sao_Paulo), a fila foi reiniciada em segundo plano com PID 34752.
O start.json da V2-003 confirma commit c73302e175e015c20cd6bd7e86276ff5920da344 e git_status_short
vazio. O manifesto também confirma esse commit. Aos 30 segundos, a árvore consumia cerca
de 10,3 GB de working set; fila e uv estavam ativos, stderr vazio e nenhum end.json existia.
Os 19 passos incluem as campanhas restantes, geração/verificação dos datasets +24h e as
oito sensibilidades. Não há parada programada entre V2 e V3; falhas reais ainda param a fila.

### Validação, limitações e próximos passos

Os scripts alterados passaram no parser do PowerShell; foram verificados início real,
commit, manifesto, processos, amostra de recursos e ausência de PARAR. Não se repetiram
os testes de modelos: este ajuste é operacional e o código otimizado não mudou.
Os resultados parciais antigos não foram excluídos ou apresentados como concluídos.
O status running do manifesto antigo não foi reescrito; seu cancelamento está documentado
no end.json e INTERRUPCAO.txt do passo, consultados pelo status da fila.

O benefício é aplicar a redução do custo das métricas já na V2 e dispensar intervenção
entre rodadas. A aceleração do cálculo de causa não é um fator de aceleração do treino
inteiro. Próximo passo: observar as conclusões reais e a transição automática, sem prometer
horário de término antes de uma rodada completa com a otimização.


## 2026-09-24 - Corrija o diagnóstico de duração da V2: execução desapareceu

Às 06h09–06h10, a pedido do responsável, foram consultados logs, artefatos, processos e
os eventos do Windows. A V2-003 NÃO estava em execução: não havia fila PID 34752, uv PID
21600 ou processos Python/curtamap. O início foi 02h23min04,855s e a última amostra foi
02h26min36,324s (3min31,469s depois). Não existe end.json, relatório, modelo persistido ou
previsão; apenas manifest.json com status running, que está desatualizado. O stderr contém
somente aviso de depreciação do LightGBM, gravado às 02h26min19s. Não é possível recuperar
o tempo exato de treino nem o instante exato de encerramento a partir desses registros.

O evento System/WindowsUpdateClient 43 registra início de instalação de uma atualização
OpenAI.Codex às 02h26min55s; o evento 19 confirma conclusão às 02h28min29s. O último boot
foi 15/09/2026, portanto não houve reinício do Windows nesse intervalo. Interpretação:
a proximidade temporal é compatível com encerramento da árvore por atualização do app,
mas não prova a causa. O desaparecimento sem end.json e a interrupção conjunta das amostras
indicam encerramento externo, não lentidão comprovada das métricas. Não houve intervenção
para reiniciar nesta consulta de diagnóstico.

Correção da conclusão anterior: processos ativos aos 30 segundos comprovavam somente o
início; não demonstravam sobrevivência da fila ao encerramento/atualização do lançador.
As horas desde 02h23 não representam horas contínuas de processamento. A V2 não produziu
evidência que permita medir o ganho das métricas. A V1 concluída registrou soma de
fit_seconds=1308,886491 s (21min49s, incluindo seleção e calibração dentro de train_family)
e duração total=13835,3 s (3h50min35s). A diferença de 3h28min46s inclui preparação,
leitura, inferência, métricas e escrita; não deve ser chamada somente de tempo de métricas.

Valor e próximos passos: evitar atribuir a perda de tempo à otimização sem medição.
A retomada precisa de um lançador independente do ciclo de vida do app e de detecção
explícita de processos ausentes no status. Preservar V2-003 como tentativa incompleta;
registrar marcos de fase em futuras execuções para separar custos com precisão.


## 2026-09-24 - Torne a fila independente do app e retome a V2 como V2-004

### Contexto e pergunta

A V2-003 desapareceu cerca de 3,5 minutos depois de iniciar, e o diagnóstico das 06h09 deixou
a atualização do Codex como hipótese. As perguntas foram três: o que encerrou a árvore de
processos; como executar a fila de modo que ela não dependa do aplicativo que a lançou; e
como retomar sem sobrescrever tentativas nem repetir a V1.

### Fatos e evidências observados

- Na checagem inicial desta sessão, não havia fila, `uv`, Python nem tarefa agendada ativos. Não havia risco de
  iniciar uma segunda fila.
- Janela do encerramento: a amostragem de `run-step.ps1` gravou a última linha às
  02h26min36,3s. A próxima era esperada por volta de 02h27min06s e não existe.
- Não existe `end.json`. Como `run-step.ps1` o escreve sempre que o `uv` termina, a ausência
  indica que fila, runner, `uv` e Python morreram juntos, e não só o Python.
- `Microsoft-Windows-AppXDeploymentServer/Operational`:
  - 02h26min55,111s: `RegisterByPackageFamilyName` do pacote `OpenAI.Codex`, com a opção
    `ForceTargetApplicationShutdownOption`, atualizando da versão 26.917.8451.0 para a
    26.917.9434.0. Esse horário está dentro da janela do encerramento.
  - 02h28min28,9s: eventos `TerminateApplications`. No mesmo instante,
    `AppModel-Runtime/Admin` registra a destruição dos contêineres Desktop AppX do pacote
    antigo.
- Ao consultar os processos atuais com `IsProcessInJob` e `GetPackageFullName`:
  - `ChatGPT.exe` tem identidade de pacote e está em um Job Object.
  - `codex.exe` e todos os filhos dele (`cmd`, `node`, `conhost`) estão em um Job Object,
    sem identidade de pacote.
  - `Start-Process` não pede breakaway. Por isso a fila anterior, lançada de um shell do
    Codex, herdou esse Job.
- Todos os `ChatGPT.exe` atuais foram criados às 06h07, ou seja, o app ficou fechado desde
  a atualização.
- Não há auditoria de término de processos (`Process Termination`) nem reboot pendente
  (`RebootRequired` e `RebootPending` ausentes).

### Interpretação e decisão

**Causa (hipótese fortemente sustentada, não confirmada):** a atualização forçada do pacote
Codex fechou o app, e a árvore da fila, que estava dentro do Job dos processos do app, foi
encerrada junto. A coincidência de horário (02h26min55 dentro da janela de cerca de 30 s),
o fato de a árvore inteira ter morrido e a herança de Job observada sustentam a hipótese.
Sem auditoria de término, não se pode confirmar qual processo encerrou a árvore nem o
instante exato. Também não foi possível separar "Job fechado com kill-on-close" de
"término forçado do pacote". Isso não muda a correção, que vale para os dois casos.

**Decisão:** a fila passa a rodar pelo Agendador de Tarefas do Windows, cujo pai é o
serviço Schedule, fora de qualquer app. A tarefa `CurtaMap-Fila-2B` é registrada pelo
script `scripts/register-queue-task.ps1`, com cópia em `execucao/`, e tem:

- prioridade 4 (normal): o padrão 7 rebaixaria CPU, I/O e memória e invalidaria a
  comparação de duração com a V1;
- sem limite de execução (o padrão encerraria a fila em 72 h);
- sem restrições de bateria ou ociosidade;
- `IgnoreNew`, que impede duas instâncias simultâneas;
- nenhum gatilho automático;
- logon Interactive, sem senha armazenada;
- a saída do próprio `pwsh` gravada em `fila/fila-tarefa.log`.

### Alternativas consideradas

- **`Start-Process` com `CREATE_BREAKAWAY_FROM_JOB`:** descartado. Depende de o Job do app
  permitir breakaway, e o processo continuaria descendendo do app.
- **Serviço do Windows ou tarefa com S4U/senha:** adiado. Exige privilégio ou credencial
  armazenada; como as unidades são locais, o logon Interactive basta enquanto a sessão
  estiver aberta.
- **Gatilho de logon para retomada automática:** descartado. A fila recusa passo existente
  e incompleto, então uma retomada cega pararia com erro e confundiria o log.

### Implementação e validação

- **Marcos de fase (commit `88634ed`, branch `etapa-2-experimental`):**
  - `run_campaign_round` grava no stderr `[curtamap-fase] <horário> <fase>` para
    `preparacao`, `treino`, `previsao`, `modelos_metricas`, `pipelines`, `baselines`,
    `relatorio` e `fim`.
  - Ciclo TDD: o teste falhou antes da implementação. Depois dela, os 8 testes de campanha
    passaram, incluindo a paridade de artefatos com o oráculo congelado. Ruff sem apontamentos.
  - Modelos, dados, limiares e métricas não mudaram.
- **Scripts operacionais (cópias `.before-v2-004` preservadas):**
  - `run-step.ps1` grava `pid_started_at`, `runner_pid` e `runner_started_at`.
  - `fila-2b.ps1` usa `main-eolica-v2-004`; `delay-eolica-v2-001` passa a depender dela
    pelo mapa de dependências. A fila também grava `fila.lock.json` com PID, hora de
    criação e pai.
  - `status-fila.ps1` só mostra RODANDO quando PID e hora de criação coincidem, com
    tolerância de 2 s nos registros novos e 15 s nos legados. Isso impede que um PID
    reutilizado conte como processo ativo. Passo sem `end.json` e sem processo aparece como
    `INTERROMP`. O status também mostra o estado da tarefa agendada e deixou de procurar
    `fila-2b.ps1` na linha de comando, busca que acertava qualquer shell que citasse o nome.
- **V2-003:** recebeu `INTERRUPCAO.txt` com o diagnóstico. Não foi criado `end.json`
  sintético, porque o horário de fim é desconhecido, e o `manifest.json` em `experimentos`
  não foi alterado.
- **Teste descartável de independência:**
  1. Um `pwsh` lançador registrou e disparou uma tarefa de teste, que gerou um neto via
     `ProcessStartInfo`, como faz a fila. O lançador foi encerrado à força às 06h21min52s.
  2. O neto continuou gravando heartbeat depois disso (até 06h22min17s, na última checagem).
  3. A ancestralidade do neto é `pwsh → pwsh → svchost (Schedule)`, sem `codex` nem `claude`.
  4. O ambiente visto pela tarefa foi conferido: `uv`, `git`, `env.ps1` e prioridade Normal.
  5. A tarefa de teste foi removida.
- **Achado operacional:** `Stop-ScheduledTask` encerrou apenas o processo raiz, e o neto
  continuou vivo. Para parar a fila, continue usando o marcador `fila/PARAR`, nunca
  `Stop-ScheduledTask`.
- **Retomada real às 06h22min54s:**
  - fila no PID 34928, com pai `svchost (Schedule)`;
  - `main-eolica-v2-004` no commit `88634ed`, com árvore limpa;
  - marcos `preparacao` (06h22min58s) e `treino` (06h23min03s) já registrados.

### Limitações e incertezas

- A causa segue como hipótese fortemente sustentada.
- O teste não reproduziu uma atualização do Codex; ele demonstrou independência pela
  ancestralidade e pela sobrevivência ao encerramento do lançador.
- Logoff, reinício do Windows (inclusive por atualização fora das horas ativas, 11h–4h),
  falta de energia ou falta de memória ainda interrompem a fila.
- Os marcos cobrem apenas `campaign-round`, não as sensibilidades.
- Suspensão e hibernação estão desativadas no plano de energia atual (tempo limite 0 na tomada
  e na bateria). O único retorno de suspensão nas últimas 48 h foi em 22/09 às 12h05, antes
  das execuções analisadas. Pausas por suspensão não afetam as durações medidas, desde que o
  plano não mude. Os arquivos de `execucao/verificacoes/teste-duravel/` ficam preservados como
  evidência do teste.
- Nenhuma duração da V2 com a otimização foi medida até aqui. Não há previsão de término.

### Valor para o usuário e para a apresentação

Uma campanha de muitas horas deixa de depender de o app de desenvolvimento continuar aberto.
Os marcos de fase permitirão dizer, com medição, quanto do tempo vai para treino, previsão e
métricas, em vez de atribuir toda a diferença da V1 às métricas. Isso sustenta a narrativa
de engenharia reprodutível e rastreável.

### Próximos passos

- Acompanhar pelo `status-fila.ps1`.
- Ao fim da V2-004, comparar as durações por fase com a V1: a V1 só tem o total e
  `fit_seconds`, então a comparação por fase só estará completa a partir da V2-004.
- Confirmar a transição automática para V3.
- Estender os marcos às sensibilidades se o custo delas se mostrar relevante.

## 24/09/2026 — Fila parada no check noturno_mais_24h eólico por erro de passagem de argumento

### Contexto e pergunta

A fila parou logo depois de `features-noturno_mais_24h-eolica-development-001`. O status mostrava
essa geração como `OK`, mas com `status=-`. O log de `check-noturno_mais_24h-eolica-001` registrava
`terminou -> ` sem resultado. As perguntas eram: a geração de features terminou? Por que a fila parou?

### Fatos e evidências observados

- `passos/features-noturno_mais_24h-eolica-development-001/end.json`: `exit_code` 0, de 13h26min54
  a 15h30min22, 7.407,9 s. O stdout informa 1.882 arquivos e 1.357.293.312 linhas de baseline.
  `status=-` só indica que passos de features não têm `manifest.json`, então não é falha.
- `fila/check-noturno_mais_24h-eolica-001.runner.stderr.log`: `run-step.ps1: Falta um argumento
  para o parâmetro 'Arguments'`. O diretório `passos/check-...` não foi criado, e o `end.json`
  também não. Por isso o resultado ficou vazio e a fila parou em 15h30min44.
- Reprodução em script descartável: sob `pwsh -File`, o valor `-m curtamap.experimental...`
  passado como item separado depois de `-Arguments` foi lido como nome de parâmetro, e o erro se
  repetiu. Com a forma `-Arguments:<valor>`, o valor chegou intacto.

### Interpretação e decisão

**Causa (confirmada por reprodução):** a troca de `Start-Process` por
`ProcessStartInfo.ArgumentList`, feita para preservar argumentos, expôs uma regra do `pwsh -File`:
um valor iniciado por `-` vira nome de parâmetro. Só o check usa argumentos que começam com `-m`,
porque roda `uv run python -m ...`. Por isso os passos `campaign-round` e `build-features` não
foram afetados.

**Decisão:** `fila-2b.ps1` passa a enviar `-Arguments:<valor>` em um único item. O backup ficou em
`fila-2b.ps1.before-check-fix`.

### Alternativas consideradas

Colocar `-m` no prefixo (`run python -m`) também resolveria, mas só para esse caso. A forma com
dois-pontos vale para qualquer passo futuro.

### Implementação e validação

- O script alterado não tem erros de parse.
- A tarefa `CurtaMap-Fila-2B` foi religada às 17h08min52. Os 8 passos concluídos foram pulados
  como `ok`, e `check-noturno_mais_24h-eolica-001` foi iniciado. Desta vez o diretório do passo
  foi criado, então o `run-step.ps1` aceitou os parâmetros.
- O resultado do check ainda não é conhecido.

### Limitações e incertezas

- `check-noturno_mais_24h-fotovoltaica-001` usa a mesma forma e deve se beneficiar da correção,
  mas ainda não rodou.
- Perdeu-se cerca de 1h38min de fila ociosa, de 15h30 a 17h08.

### Valor para o usuário e para a apresentação

É um detalhe operacional sem efeito sobre modelos ou métricas. Ele reforça a prática de exigir um
`end.json` por passo: a fila parou em vez de seguir para as sensibilidades com um dataset não
verificado.

### Próximos passos

- Acompanhar o check eólico e, em seguida, as sensibilidades `delay-eolica-*`.

## 24/09/2026 — Fila 2B concluída após a correção do check

### Contexto e pergunta

Esta entrada continua a anterior. A dúvida era se os passos restantes da fila (checks e
sensibilidades `delay-*`) rodariam sem nova falha depois da correção de `-Arguments:<valor>`.

### Fatos e evidências observados

Horários de término e resultados vêm de `execucao/fila/fila.log`. As durações foram calculadas
entre o início e o fim registrados no log.

| Passo | Término | Duração | Resultado |
|---|---|---|---|
| `check-noturno_mais_24h-eolica-001` | 17h14 | 5 min | ok |
| `delay-eolica-v1-001` | 17h34 | 20 min | ok |
| `delay-eolica-v2-001` | 17h59 | 26 min | ok |
| `delay-eolica-v3-001` | 18h24 | 25 min | ok |
| `delay-eolica-v4-001` | 18h47 | 23 min | ok |
| `features-noturno_mais_24h-fotovoltaica-development-001` | 19h24 | 37 min | ok |
| `check-noturno_mais_24h-fotovoltaica-001` | 19h26 | 2 min | ok |
| `delay-fotovoltaica-v1-001` | 19h36 | 11 min | ok |
| `delay-fotovoltaica-v2-001` | 19h47 | 10 min | ok |
| `delay-fotovoltaica-v3-001` | 19h59 | 12 min | ok |
| `delay-fotovoltaica-v4-001` | 20h11 | 13 min | ok |

Às 20h11min47 o log registrou `fila concluída com sucesso`.

### Interpretação e decisão

- A correção valeu para os dois checks.
- As sensibilidades `sensitivity-round` rodaram pela primeira vez com o volume real e terminaram
  sem erro.
- Nenhuma métrica de sensibilidade foi analisada nesta entrada.

### Implementação e validação

Um monitor de sessão acompanhou `fila.log` e o estado da tarefa agendada. Não houve queda, parada
por `PARAR` nem intervenção da vigia de memória.

### Limitações e incertezas

- `ok` significa `exit_code` 0 e, quando existe `manifest.json`, `status=complete`. Isso não valida
  o conteúdo científico dos resultados.

### Valor para o usuário e para a apresentação

Os artefatos principais e de sensibilidade da Etapa 2B estão completos para as duas fontes. Com
isso, a análise de robustez ao atraso de dados pode entrar no pitch.

### Próximos passos

- Analisar os relatórios `delay-*` contra os runs `main-*` congelados.
- Comparar as durações por fase da V2-004 com as da V1.

## 24/09/2026 — Registro tardio (23/09): dataset solar, contingência de treino, V1 eólica e verificação da amostragem

> Registro tardio, redigido na sessão 05 a partir do rascunho da sessão 04
> (`execucao/rascunhos/diario-sessao04-contingencia.md`) e dos artefatos das runs. Os fatos são
> de 23/09/2026. As entradas de 24/09 já cobrem a fila, as tentativas da V2 e o check +24h;
> aqui elas só são citadas.

### Contexto e pergunta

Com as populações eólicas medidas, a pergunta consolidada
(`execucao/PERGUNTA-contingencia-treino-sessao04.md`) pediu decisão sobre amostragem,
aplicação à solar, threads, orçamento de 12 h e uso da V1 eólica como porta medida. O
responsável respondeu "Siga com o que você faria (ações recomendadas)" e acrescentou que as
sessões anteriores gastaram tempo demais com verificações redundantes, enquanto só um modelo
havia sido treinado. A partir daí a prioridade explícita passou a ser o treino.

### Fatos: dataset e populações solares

- Geração `features-noturno_dia_util-fotovoltaica-development-001`, commit `2e79475`: exit 0,
  2.424,2 s, stderr vazio, 759 partições, 1.518 arquivos, 457.531.776 linhas de baseline.
- Verificação `check-noturno_dia_util-fotovoltaica-001`, mesmo commit: 18/18 checagens, exit 0,
  121,1 s, pico 1,07 GB. 114.382.944 linhas de features, 82 entidades, 2.382.978 emissões de
  48 horizontes. Só 01/04/2024 ficou sem partição (primeira liberação em 02/04/2024 19h30,
  igual ao calendário). 87.984 linhas têm tau ≥ 01/05/2026 e nenhuma sobrevive aos filtros
  V1–V4. Causas presentes: CNF, ENE, REL e DESCONHECIDA; nenhuma PAR.
- Medição `populacoes-noturno_dia_util-fotovoltaica-001`: exit 0, 106,4 s, 59/59 checagens
  cruzadas. Refit de ocorrências: V1 29.088.288, V2 46.912.152, V3 64.939.512 e V4 83.666.856
  linhas. Validação: 17.781.648, 18.273.840, 19.344.336 e 20.417.904 linhas. Pico projetado do
  treino completo de ocorrências: de 19,9 GiB (V1) a 56,7 GiB (V4).

### Decisão aplicada (desvio registrado do §12.1, "todos os elegíveis")

- **Amostragem `t0_sistematico_diario_v1`, semente 42.** Em cada dia, `k` das 48 meias-horas
  igualmente espaçadas, deslocadas por SHA-256(`42|data`). Emissões inteiras (todas as
  entidades e os 48 horizontes). Aplicada **só em initial e refit**; tuning, calibração e
  validação ficam completos. A mesma seleção vale para famílias, candidatos e rodadas, com
  initial ⊂ refit.
- **Taxa única por fonte e tarefa em todas as rodadas:** a maior fração de 48 cujo pico
  projetado fique ≤ 20 GiB na rodada mais pesada. Eólica: ocorrências 4/48, volume e causa
  14/48. Solar: ocorrências 16/48, volume e causa 48/48 (completo).
- **LightGBM:** `n_jobs=6`, `deterministic=True`, `force_row_wise=True`. É repetível com o mesmo
  número de threads, mas não é numericamente igual ao piloto em `n_jobs=1`.
- **Orçamento de 12 h:** revisto implicitamente; a duração real seria medida pela V1.
- **Porta medida:** a V1 eólica mede pico e duração antes das demais runs.
- **Piloto solar dispensado:** a primeira campanha solar exercita o mesmo caminho técnico com a
  população real. No `run-index.json` ele consta como `dispensada`.

Alternativas descartadas: hash puro por t0 (variação de ±12% por meia-hora a 8%); taxa por
rodada (mudaria a fração entre rodadas); treino completo (até 184 GiB projetados).

### Implementação e validação

- Commits `40cb438` (amostragem, campanha, CLI, configuração) e `f36d5f6` (threads). TDD com
  testes de espaçamento, SHA-256 estável, emissões inteiras, aninhamento, semente, leitura por
  fonte, segmentos e parâmetros do LightGBM.
- Suíte `contingencia-pytest-001`: 241 aprovados e 2 falhas de paridade, causadas apenas pelas
  chaves novas `training_sampling`/`training_rows` do relatório. A normalização passou a
  removê-las e a exigir `training_sampling=None` quando não há amostragem; depois disso a
  paridade passou (3/3). Ruff e `git diff --check` aprovados.

### Fato: `main-eolica-v1-001` interrompida e corrigida

- Commit `f36d5f6`. Aos 458 s o agente interrompeu a run (exit −1): 41–46 GB de memória
  comprometida, commit livre de até 1,1 GB e working set caindo a 0,1 GB, ou seja, thrashing
  durante a montagem dos splits. Evidência em `execucao/passos/main-eolica-v1-001/INTERRUPCAO.txt`
  e `main-eolica-v1-001-memoria-privada.csv`. O diretório da run só tem o manifest, que
  continua `running` e não foi reescrito.
- **Causa confirmada pelo código:** a máscara de amostragem (`replace_strict`) ficava acima do
  scan do Parquet, e o refit inteiro era materializado antes de amostrar.
- **Correção `560ae70`:** lista explícita dos t0 selecionados, com a mesma seleção, levada ao
  `SELECTION` do scan. Um teste com cadeia realista verifica o pushdown.

### Fato: `main-eolica-v1-002` concluída (porta medida)

Commit `560ae70`, árvore limpa: exit 0, **13.835,3 s** (3h50min35s), soma de `fit_seconds` de
1.308,9 s, pico de working set do processo de 12,61 GiB (10,61 GiB na árvore amostrada),
`failures=[]`, 54 arquivos com checksums. A porta de memória (≤ 20 GiB) foi respeitada. A
V1 rodou **antes** da otimização de métricas `c73302e` e sem marcadores de fase; a comparação
de fases com as demais rodadas é, portanto, parcial.

### Verificação posterior da amostragem (auditoria `auditoria-runs-2b-001`, sessão 05)

Esta seção compara o `training_rows` de cada run com as populações medidas:

- **Tuning e calibração:** linhas **idênticas** às medidas nas 8 runs. A amostragem ficou
  restrita a initial e refit, como decidido.
- **Initial e refit, eólica:** razão de 0,0833 nas ocorrências (esperado 4/48 = 0,0833) e de
  0,2911 a 0,2916 em volume e causa (esperado 14/48 = 0,2917).
- **Initial e refit, solar:** razão de 0,3333 a 0,3334 nas ocorrências (esperado 16/48); volume
  e causa idênticos à população completa.
- **Prevalência amostrada vs. completa:** diferença absoluta ≤ 0,0004 em todas as rodadas,
  fontes e tarefas de ocorrência (por exemplo, V4 eólica `corte_positivo` 0,2320 vs. 0,2317).
- **Validação:** `validation_rows` igual ao `prediction_rows` medido nas 8 runs, ou seja,
  validação completa.

### Limitações e incertezas

- A amostragem reduz os exemplos de ajuste e pode reduzir o desempenho; toda comparação da 2C
  deve citá-la.
- A proximidade das prevalências vale para a média global, não para cada entidade ou mês.
- A V1 eólica usa código de métricas anterior ao das demais rodadas. Os resultados são
  equivalentes por teste de paridade (`c73302e`), mas os tempos não são comparáveis.

### Valor para o usuário e para a apresentação

A decisão tornou o treino viável em uma máquina de 32 GB, dentro do prazo, sem mudar a
validação. É um exemplo de engenharia sob restrição com o desvio registrado e verificado por
números, útil para a seção de limitações do pitch.

### Próximos passos

Levar a amostragem como desvio explícito ao handoff da 2C (feito na entrada da sessão 05).

## 24/09/2026 — Etapa 2B: auditoria pós-fila, integração Git, inventário e handoff da 2C (sessão 05)

### Contexto e pergunta

A fila terminou às 20h11 com todas as 19 etapas em `ok`. A pergunta era se os 16 artefatos
(8 principais e 8 sensibilidades) estavam íntegros e coerentes com a decisão de amostragem, e
como fechar a 2B com rastreabilidade, sem repetir verificações já aprovadas.

### Fatos e evidências observados

- **Estado inicial:** o repositório principal estava na branch `codex/otimize-metricas-validacao`
  (`089cd9b`), com 7 commits de diário e script operacional sobre `c73302e`. A branch
  `etapa-2-experimental` estava em `88634ed`, com checkout no worktree executor. Não havia
  processos da fila nem Python ativos.
- **Auditoria `auditoria-runs-2b-001`:** 181,5 s, exit 0, via `run-step.ps1`, script
  `execucao/verificacoes/auditar_runs_2b.py`.
  - Checksums recalculados nas 16 runs: 54 arquivos por principal e 26 por sensibilidade,
    sem divergência, ausência ou arquivo fora da lista.
  - As 8 sensibilidades congelam a principal correta: SHA-256 dos 8 modelos igual ao da
    principal, limiares e calibração idênticos, `models_retrained=false`, sem pasta `models/`
    e sem `fit_seconds`.
  - Tuning e calibração com linhas idênticas às populações medidas; `validation_rows` igual ao
    `prediction_rows` medido nas 8 principais. As razões de amostragem e prevalências estão na
    entrada de registro tardio acima.
- **Duração e memória das principais:** eólica V2–V4 de 4.072 a 5.067 s; solar V1–V4 de 1.840
  a 4.340 s. Pico máximo de processo de 24,06 GiB (solar V4), acima do alvo de 20 GiB da
  projeção, sem acionar a vigia de memória. Nas 7 runs com marcadores, preparação e treino
  ocupam de 58% a 82% da duração.
- **Checks +24h:** eólica e solar com 18/18.
- **Relatórios `delay-*`:** faltam 6 recortes, mas o recorte global está presente.
- **Inventário `inventario-2b-001`:** 90,8 s; 8.133 arquivos e 67,3 GB; 640 hashes
  reaproveitados dos checksums verificados e 7.493 calculados.
- **Achados factuais para a 2C (não interpretados):**
  - `volume_condicional-lightgbm` solar selecionou `n_estimators=1` em V3 e V4;
  - recall de REL dos modelos de causa próximo de zero;
  - baselines de causa `ultimo_valor` e `mesmo_horario_recente` idênticos nas 8 runs;
  - métricas nulas sem motivo gravado em recortes de classe única.

### Interpretação e decisão

- **Integração:** desde `c73302e`, a branch codex não altera Python. O worktree da fila foi
  removido (nenhuma run depende dele), a branch `execucao/fila-2b` foi apagada (sem commits
  próprios) e o merge `--no-ff` `1fba2f6` integrou a branch em `etapa-2-experimental`.
  `git diff 88634ed HEAD -- src tests configs` saiu vazio. Por isso **não** se reexecutou
  pytest nem ruff: o código é o mesmo já testado, conforme a orientação de evitar
  verificações redundantes.
- **Pico de 24,06 GiB:** registrado como fato. A regra de 20 GiB era uma projeção para escolher
  a taxa; a execução real não falhou nem entrou em thrashing.
- **Relatório factual:** fica em `handoff/relatorio-etapa-2b.md`, com cópia em
  `docs/reports/stage2b/execution-report.md`. Ele traz as tabelas globais por tarefa, família e
  baseline, sem ranking, e não aplica o §11.

### Alternativas consideradas

- **Recalcular os hashes das runs no inventário:** descartado, porque a auditoria acabara de
  verificá-los.
- **Rodar de novo a suíte após o merge:** descartado, porque o código Python é idêntico.
- **Calcular as médias e os estados do §11:** adiado para a 2C, porque é decisão de análise.

### Implementação e validação

- `execucao/run-index.json` atualizado com as 22 entradas: 16 concluídas, 4 tentativas com
  status próprio, piloto eólico e piloto solar `dispensada`. Backup em
  `verificacoes/run-index.pre-sessao05.json`.
- Commits: `1fba2f6` (merge), `0452d68` (registro tardio da contingência) e `dba5fe4`
  (relatório e prompt versionados).
- Hashes do handoff em `handoff/SHA256SUMS-handoff.txt`.

### Limitações e incertezas

- A auditoria confirma a integridade e a coerência das populações, não a qualidade científica
  dos modelos.
- Faltam as agregações por entidade, a energia diária, a incerteza semanal e a interseção
  principal/+24h.
- As extensões recomendadas não foram executadas.
- O teste reservado continua fechado.

### Valor para o usuário e para a apresentação

- A 2B entrega 16 runs completas e verificadas, com proveniência por commit e hash, para as
  duas fontes e as quatro rodadas.
- Os achados factuais (causa REL, regressor solar com uma árvore) indicam onde o pitch deve ser
  cauteloso até a análise da 2C.

### Próximos passos

Executar a 2C com `handoff/PROMPT-analise-etapa-2c.md`.

### Adendo (mesma sessão 05): inventário substituído

- **Problema:** o `inventario-2b-001` incluiu arquivos que continuaram sendo gravados depois do
  cálculo do hash: o checkpoint externo e os logs e o `end.json` do próprio passo. Uma
  conferência posterior acusaria divergências falsas.
- **Correção:** o `inventario-2b-002` (60,6 s, exit 0, script `inventariar_2b_v2.py`) exclui
  `handoff/` (coberto por `SHA256SUMS-handoff.txt`), `execucao/CHECKPOINT-*.md` e o diretório
  do próprio passo. Resultado: 8.133 arquivos, 67.348.497.296 bytes, SHA-256 do CSV
  `99920bab92ba…`.
- **O -001 fica preservado** como `handoff/inventario-etapa-2b-001.*` e não deve ser usado para
  conferência.
- **Relatório e prompt (commit `f193088`):**
  - o relatório registra que os picos reais superaram a meta de 20 GiB (24,06 e 22,02 GiB);
  - o prompt passa a citar os commits de referência e avisa que, fora do Windows, a checagem
    de congelamento do auditor dá falso negativo, porque os caminhos gravados são absolutos
    `Y:\…`.
- **Hashes:** `configuration_sha256` e `data_hashes` foram conferidos nos 16 manifests (antes,
  só nas 8 principais e em uma sensibilidade).

### Adendo (sessão 05): prompt único da 2C

- **Situação:** havia dois prompts. `docs/handoffs/stage2c-prompt.md` era o original, escrito
  antes da execução e dono do método de decisão. `docs/handoffs/stage2c-analysis-prompt.md`
  era o da sessão 05, com os fatos da execução.
- **Conflitos do prompt novo com o original**, que prevalece:
  - estados: o novo usava os estados do §11.2 (`aprovado_preliminar`, `requer_analise`); o
    original define `aprovado_para_teste`, `baseline_preferido`, `inconclusivo`, `inelegivel`
    e `requer_2d`;
  - teste reservado: o novo proibia abri-lo de forma absoluta; o original atribui à 2C a
    decisão explícita de liberá-lo depois de congelar a receita. A proibição absoluta valia
    para a 2B.
- **Decisão**, a pedido do responsável:
  - consolidar tudo em `docs/handoffs/stage2c-prompt.md`, com o texto original preservado e
    uma seção "Fatos da execução 2B";
  - apagar `stage2c-analysis-prompt.md` e a cópia `handoff/PROMPT-analise-etapa-2c.md` da raiz
    externa;
  - apontar o relatório para o prompt consolidado e regenerar `SHA256SUMS-handoff.txt`.

## 24/09/2026 — Etapa 2B: raiz operacional unificada no repositório

### Contexto e pergunta

O desenvolvimento acontecia em dois lugares: no Mac e no computador Windows dedicado ao
treino. Neste último, scripts, logs, métricas e relatórios ficavam na raiz externa
`Y:\CurtaMap Etapa 2B`, fora do Git. O responsável pediu que tudo o que deve ser versionado
volte ao repositório e que o worktree separado deixe de existir, sem recriar nenhum artefato
(tudo é caro de gerar).

### Fatos observados

- **Tamanho no `Y:`:** cerca de 68 GB, dos quais 58,7 GB são previsões Parquet e 8,2 GB
  datasets de features. O disco `M:` tem 42 GB livres.
- **Material leve:** manifests, checksums, reports, metrics, diagnostics, `execucao/` e
  `handoff/` somam cerca de 49 MB em texto e JSON.
- **Ambiente:** o Git deste computador usa `core.autocrlf=true`, que converteria os fins de
  linha e mudaria os bytes dos JSON de runs verificados por checksum.
- **Junctions:** o Git trata junctions como diretórios comuns.

### Decisão

- **`experiments/stage2b/` espelha a raiz externa com a mesma estrutura**, para que continuem
  válidos os caminhos relativos do relatório, do prompt e do `run-index`.
- **No Git:** os arquivos leves, cerca de 930.
- **No disco externo, via junction e ignorados:**
  - previsões, modelos, datasets, cache, dados brutos, sondas e temporários;
  - modelos ficam fora mesmo sendo pequenos, pela regra do `AGENTS.md`;
  - `env.ps1` também fica fora; `env.example.ps1` é versionado no lugar dele.
- **Progresso intermediário** (`*.progress.jsonl` e `*.sqlite`, 72 MB): copiado para o
  repositório, mas ignorado pelo Git.
- **Nada foi apagado.** `Y:\…\execucao` e `handoff` foram apenas renomeados para
  `_migrado-para-repo-20260924-*`, para que ninguém volte a gravar neles.
- **`.gitattributes`** (`experiments/stage2b/** -text`) preserva os bytes exatos.
- **Ruff:** exclui `experiments/`, porque os scripts históricos são evidência e não devem ser
  reformatados.
- **`run-step.ps1`:** passa a resolver `env.ps1` e `passos/` pelo próprio diretório.

### Alternativas consideradas

- **Mover tudo para o `M:`:** inviável por espaço.
- **Mover tudo para outro disco:** não unificaria nada.
- **Apagar as previsões depois da 2C:** descartado pelo responsável, porque não haverá
  recriação.

### Implementação e validação

- **Commits:** `51b71d6` (estrutura, `.gitignore` e scripts `migrar-para-repo.ps1` e
  `conferir_migracao.py`), `f0e4e5a` (cópia verbatim) e `89221e2` (run-step parametrizado).
- **Conferência da cópia:** 941 arquivos com SHA-256 igual à origem; 650 entradas de checksum
  resolvidas pelas junctions com o mesmo tamanho.
- **Conferência dos blobs:** todos os blobs de `experiments/` foram comparados com
  `git hash-object --no-filters`, sem diferença.
- **Teste do run-step:** o passo `smoke-run-step-repo-001` rodou a partir do repositório
  (exit 0) e gravou em `experiments/stage2b/execucao/passos/`.
- **Limpeza:** worktree `medicao-populacoes` removido; branches `codex/*` integradas e apagadas.
- **Espaços em branco:** o `git diff --check` acusa espaços finais nos logs copiados. Eles
  foram mantidos, por serem evidência verbatim.

### Limitações e riscos

- **`git clean -x` apagaria dados reais do `Y:`** através das junctions. O alerta está no
  `AGENTS.md` e no `experiments/stage2b/README.md`.
- **Runs futuras** continuam gravando previsões no `Y:`. Depois de cada uma, é preciso rodar de
  novo a migração e a conferência.
- **Fila da 2B:** `fila-2b.ps1` e `status-fila.ps1` ainda apontam para o `Y:` e para o
  worktree removido; ficam como registro histórico.
- **Cópia única:** os artefatos pesados existem só no `Y:`. Uma cópia de segurança em outro
  disco é recomendável, já que não serão recriados.

### Valor e próximos passos

- A partir de agora, o repositório é a fonte única do que é versionável nas duas máquinas.
- No Mac, basta colocar previsões, modelos e datasets nos mesmos caminhos relativos.
- Próximo passo: a Etapa 2C, pelo prompt `docs/handoffs/stage2c-prompt.md`.
